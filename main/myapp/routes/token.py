from flask import Blueprint, jsonify
import json
import os
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


def _with_owner(payload):
    data = dict(payload)
    data.setdefault('owner_addr', OWNER_ADDR)
    data.setdefault('owner_pkey', OWNER_PRIVATE)
    return data


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
    payload = request_json()
    if 'token_name' in payload:
        try:
            payload['token_name'] = USER_db.normalize_token_column(payload['token_name'])
        except ValueError as exc:
            return jsonify({'state': 'ERROR', 'msg': str(exc)}), 400
    if 'user_DID' in payload:
        did_rows = get_did_info_db.get_DID_info_by_did(payload['user_DID'])
        if not did_rows:
            return jsonify({'state': 'ERROR', 'msg': 'user_DID not found'}), 404
        payload['receiver'] = did_rows[0][3]
        payload.setdefault('amount', 1)
    if 'token_name' in payload and 'cont_addr' not in payload:
        token_rows = get_token_info.get_addr_by_name(payload['token_name'])
        if token_rows:
            payload['cont_addr'] = token_rows[0][0]
        else:
            return jsonify({
                'state': 'ERROR',
                'msg': f"token contract not found: {payload['token_name']}",
            }), 400
    payload.setdefault('sender', OWNER_ADDR)
    payload.setdefault('sender_pkey', OWNER_PRIVATE)
    status_code, body = post_dchain(TOKEN_ENDPOINTS['transfer'], payload)
    if status_code == 200 and body.get('state') == 'OK' and payload.get('user_DID') and payload.get('token_name'):
        try:
            updated_column, updated_rows = user_db.increase_balance(payload['user_DID'], payload['token_name'])
        except ValueError as exc:
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
    return proxy_response(TOKEN_ENDPOINTS['transfer_from'], request_json())


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
