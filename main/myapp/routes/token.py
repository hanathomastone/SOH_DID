from flask import Blueprint, current_app, jsonify, request
import hmac
import json
import os
from pathlib import Path
import sys

from myapp.dchain import post_dchain, proxy_response, request_json
from myapp.utils import OWNER_ADDR, OWNER_PRIVATE, TOKEN_ENDPOINTS

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import DID_db_get
import Token_db
import Token_db_get
import USER_db
import USER_db_get

token_api = Blueprint('token', __name__)

token_db = Token_db.Token()
get_token_info = Token_db_get.get_Token_info()
get_did_info_db = DID_db_get.get_DID_Info()
user_db = USER_db.User()
get_user_info_db = USER_db_get.get_User_Info()


SENSITIVE_LOG_KEYS = {
    'holder_pkey',
    'owner_pkey',
    'owner_private',
    'private_key',
    'privatekey',
    'sender_pkey',
}

DATA_DIR = Path(os.getenv('DID_DATA_DIR') or os.getenv('DATA_DIR', './data'))
KEYS_DIR = DATA_DIR / 'keys'
INDEX_PATH = DATA_DIR / 'index.json'


def _redact_for_log(value):
    if isinstance(value, dict):
        return {
            key: '***REDACTED***' if key in SENSITIVE_LOG_KEYS else _redact_for_log(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_for_log(item) for item in value]
    return value


def _log_transfer_failure(reason, received_payload, dchain_payload=None, status_code=None, response_body=None):
    log_data = {
        'reason': reason,
        'received_payload': _redact_for_log(received_payload),
    }
    if dchain_payload is not None:
        log_data['dchain_payload'] = _redact_for_log(dchain_payload)
    if status_code is not None:
        log_data['status_code'] = status_code
    if response_body is not None:
        log_data['response_body'] = _redact_for_log(response_body)
    current_app.logger.warning(
        'token transfer failed payload=%s',
        json.dumps(log_data, ensure_ascii=False, default=str),
    )


def _with_owner(payload):
    data = dict(payload)
    data.setdefault('owner_addr', OWNER_ADDR)
    data.setdefault('owner_pkey', OWNER_PRIVATE)
    return data


def _legacy_wallet_private_key(holder):
    """Loads a locally issued wallet key without returning or logging it."""
    if not holder:
        return None

    normalized_holder = str(holder).strip().lower()
    candidate_paths = []
    if INDEX_PATH.exists():
        try:
            with INDEX_PATH.open('r', encoding='utf-8') as file:
                index = json.load(file)
        except (OSError, ValueError):
            current_app.logger.warning('Unable to read DID wallet index for legacy token reclaim')
            index = {}
        for meta in index.values():
            if str(meta.get('account_address') or '').strip().lower() != normalized_holder:
                continue
            fingerprint = meta.get('fingerprint')
            if fingerprint and str(fingerprint).isalnum():
                candidate_paths.append(KEYS_DIR / f'{fingerprint}.key.json')

    # Older DID records may predate account_address in index.json. Their wallet key
    # remains nested in the protected key file, so scan only that private directory.
    if KEYS_DIR.exists():
        candidate_paths.extend(KEYS_DIR.glob('*.key.json'))

    visited_paths = set()
    for key_path in candidate_paths:
        normalized_path = str(key_path.resolve())
        if normalized_path in visited_paths:
            continue
        visited_paths.add(normalized_path)
        try:
            with key_path.open('r', encoding='utf-8') as file:
                key_data = json.load(file)
        except (OSError, ValueError):
            continue
        wallet = key_data.get('wallet') or {}
        wallet_address = str(wallet.get('address') or '').strip().lower()
        if wallet_address == normalized_holder:
            return wallet.get('privatekey') or wallet.get('private_key')
    return None


def _contract_from_create_response(body):
    data = body.get('data') or {}
    contract = data.get('contract') or {}
    contract_data = contract.get('data') or {}
    token = data.get('token') or {}
    token_response = token.get('response') or {}
    token_fact = token_response.get('fact') or {}
    token_receipt = token.get('receipt') or {}
    receipt_operation = token_receipt.get('operation') or {}
    receipt_fact = receipt_operation.get('fact') or {}
    return (
        contract_data.get('address')
        or contract.get('address')
        or token_fact.get('contract')
        or receipt_fact.get('contract')
    )


def _issued_from_create_response(body):
    data = body.get('data') or {}
    contract = data.get('contract') or {}
    token = data.get('token') or {}
    return token.get('issued') or contract.get('issued')


@token_api.route('/create', methods=['POST'])
def create_token():
    payload = _with_owner(request_json())
    if payload.get('token_name'):
        try:
            payload['token_name'] = USER_db.normalize_token_column(payload['token_name'])
        except ValueError:
            pass
    payload.setdefault('decimals', 9)
    status_code, body = post_dchain(TOKEN_ENDPOINTS['create'], payload)
    if status_code == 200 and body.get('state') == 'OK':
        contract_addr = _contract_from_create_response(body)
        issued = _issued_from_create_response(body)
        if contract_addr:
            token_db.add_token(
                token_name=payload.get('token_name'),
                token_symbol=payload.get('token_symbol'),
                contract_addr=contract_addr,
                issued=issued,
                supply=payload.get('supply'),
                meta_data=json.dumps(body, ensure_ascii=False),
            )
            token_db.commit()
            body.setdefault('local_db', {})['saved'] = True
            body['local_db']['token_name'] = payload.get('token_name')
            body['local_db']['contract_addr'] = contract_addr
        else:
            body.setdefault('local_db', {})['saved'] = False
            body['local_db']['reason'] = 'contract address not found in create response'
    return jsonify(body), status_code


@token_api.route('/transfer', methods=['POST'])
def transfer():
    received_payload = request_json()
    payload = dict(received_payload)
    if 'token_name' in payload:
        try:
            payload['token_name'] = USER_db.normalize_token_column(payload['token_name'])
        except ValueError as exc:
            _log_transfer_failure('unsupported token_name', received_payload)
            return jsonify({'state': 'ERROR', 'msg': str(exc)}), 400
    if 'user_DID' in payload:
        did_rows = get_did_info_db.get_DID_info_by_did(payload['user_DID'])
        if not did_rows:
            _log_transfer_failure('user_DID not found', received_payload, payload)
            return jsonify({'state': 'ERROR', 'msg': 'user_DID not found'}), 404
        payload['receiver'] = did_rows[0][3]
        payload.setdefault('amount', 1)
    if 'token_name' in payload and 'cont_addr' not in payload:
        token_rows = get_token_info.get_addr_by_name(payload['token_name'])
        if token_rows:
            payload['cont_addr'] = token_rows[0][0]
        else:
            _log_transfer_failure('token contract not found', received_payload, payload)
            return jsonify({
                'state': 'ERROR',
                'msg': f"token contract not found: {payload['token_name']}",
            }), 400
    payload.setdefault('sender', OWNER_ADDR)
    payload.setdefault('sender_pkey', OWNER_PRIVATE)
    status_code, body = post_dchain(TOKEN_ENDPOINTS['transfer'], payload)
    if status_code != 200 or body.get('state') != 'OK':
        _log_transfer_failure('DChain token transfer failed', received_payload, payload, status_code, body)
    if status_code == 200 and body.get('state') == 'OK' and payload.get('user_DID') and payload.get('token_name'):
        try:
            updated_column, updated_rows = user_db.increase_balance(payload['user_DID'], payload['token_name'])
        except ValueError as exc:
            _log_transfer_failure('local user token update failed', received_payload, payload, 400, {'msg': str(exc)})
            return jsonify({'state': 'ERROR', 'msg': str(exc)}), 400
        user_db.commit()
        body.setdefault('local_db', {})['user_token_updated'] = True
        body['local_db']['user_DID'] = payload['user_DID']
        body['local_db']['token_column'] = updated_column
        body['local_db']['updated_rows'] = updated_rows
    return jsonify(body), status_code


@token_api.route('/balance', methods=['POST'])
@token_api.route('/balance_list', methods=['POST'])
def balance():
    return proxy_response(TOKEN_ENDPOINTS['balance'], request_json())


@token_api.route('/approve', methods=['POST'])
def approve():
    return proxy_response(TOKEN_ENDPOINTS['approve'], request_json())


@token_api.route('/transfer_from', methods=['POST'])
@token_api.route('/retrieve', methods=['POST'])
def transfer_from():
    payload = request_json()
    if request.path.endswith('/retrieve'):
        owner_address_matches = str(payload.get('sender') or '').lower() == str(OWNER_ADDR).lower()
        receiver_matches = str(payload.get('receiver') or '').lower() == str(OWNER_ADDR).lower()
        owner_key_matches = hmac.compare_digest(
            str(payload.get('sender_pkey') or ''),
            str(OWNER_PRIVATE),
        )
        if not owner_address_matches or not receiver_matches or not owner_key_matches:
            return jsonify({
                'state': 'ERROR',
                'msg': 'token owner authentication is required for reclaim',
            }), 403

        holder_private_key = _legacy_wallet_private_key(payload.get('holder'))
        if holder_private_key:
            contract_address = (
                payload.get('cont_addr')
                or payload.get('contract_address')
                or payload.get('contract')
            )
            approve_payload = {
                'cont_addr': contract_address,
                'holder': payload.get('holder'),
                'holder_pkey': holder_private_key,
                'approved': OWNER_ADDR,
                'amount': payload.get('amount'),
            }
            approve_status, approve_body = post_dchain(TOKEN_ENDPOINTS['approve'], approve_payload)
            if approve_status != 200 or approve_body.get('state') != 'OK':
                current_app.logger.warning(
                    'Legacy reward wallet approval failed before reclaim holder=%s',
                    payload.get('holder'),
                )
                return jsonify({
                    'state': 'ERROR',
                    'msg': 'legacy reward wallet approval failed before reclaim',
                    'stage': 'approve',
                    'rcode': approve_body.get('rcode'),
                    'cid': approve_body.get('cid'),
                }), approve_status
    return proxy_response(TOKEN_ENDPOINTS['transfer_from'], payload)


@token_api.route('/tokens', methods=['GET', 'POST'])
@token_api.route('/token_list', methods=['GET', 'POST'])
def tokens():
    return proxy_response(TOKEN_ENDPOINTS['tokens'], request_json())


@token_api.route('/local_tokens', methods=['GET'])
def local_tokens():
    rows = get_token_info.all_list()
    tokens = [
        {
            'token_name': row[0],
            'token_symbol': row[1],
            'contract_addr': row[2],
            'issued': row[3],
            'supply': row[4],
        }
        for row in rows
    ]
    return jsonify({'tokens': tokens})


@token_api.route('/supply', methods=['POST'])
def supply():
    return proxy_response(TOKEN_ENDPOINTS['supply'], request_json())


@token_api.route('/allowance', methods=['POST'])
def allowance():
    return proxy_response(TOKEN_ENDPOINTS['allowance'], request_json())


@token_api.route('/mint', methods=['POST'])
def mint():
    payload = _with_owner(request_json())
    return proxy_response(TOKEN_ENDPOINTS['mint'], payload)


@token_api.route('/burn', methods=['POST'])
def burn():
    return proxy_response(TOKEN_ENDPOINTS['burn'], request_json())


@token_api.route('/upload_token', methods=['POST'])
def upload_token():
    return proxy_response(TOKEN_ENDPOINTS['upload_token'], request_json())
