import base64
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import stat
import threading

from flask import Blueprint, jsonify, request
import os
import sys

from myapp.dchain import post_dchain, proxy_response, request_json
from myapp.utils import (
    COMMON_ENDPOINTS,
    DID_ENDPOINTS,
    LOGIN_CREDENTIAL_TEMPLATE_ID,
    LOGIN_CREDENTIAL_VALID_FROM,
    LOGIN_CREDENTIAL_VALID_UNTIL,
)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import DID_db
import DID_db_get
import USER_db
import USER_db_get

did_api = Blueprint('did', __name__)

user_db = USER_db.User()
get_user_info_db = USER_db_get.get_User_Info()
did_db = DID_db.DID()
get_did_info_db = DID_db_get.get_DID_Info()

DATA_DIR = Path(os.getenv('DID_DATA_DIR', './data'))
DIDS_DIR = DATA_DIR / 'dids'
KEYS_DIR = DATA_DIR / 'keys'
INDEX_PATH = DATA_DIR / 'index.json'

for directory in (DIDS_DIR, KEYS_DIR):
    directory.mkdir(parents=True, exist_ok=True)

_index_lock = threading.Lock()
_ED25519_PUB_CODEC_PREFIX = bytes([0xED, 0x01])
_BASE58_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'


def _base58_encode(raw):
    number = int.from_bytes(raw, 'big')
    encoded = ''
    while number:
        number, remainder = divmod(number, 58)
        encoded = _BASE58_ALPHABET[remainder] + encoded
    padding = 0
    for byte in raw:
        if byte == 0:
            padding += 1
        else:
            break
    return ('1' * padding) + (encoded or '1')


def _to_base58btc(raw):
    return 'z' + _base58_encode(raw)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _chmod_600(path):
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass


def _read_index():
    if not INDEX_PATH.exists():
        return {}
    with INDEX_PATH.open('r', encoding='utf-8') as file:
        return json.load(file)


def _write_index(index):
    tmp_path = INDEX_PATH.with_suffix('.tmp')
    with tmp_path.open('w', encoding='utf-8') as file:
        json.dump(index, file, ensure_ascii=False, indent=2)
    tmp_path.replace(INDEX_PATH)


def _make_did_key_and_doc(label=None):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    fingerprint = _to_base58btc(_ED25519_PUB_CODEC_PREFIX + public_bytes)
    did = f'did:key:{fingerprint}'
    verification_method_id = f'{did}#{fingerprint}'
    did_document = {
        '@context': [
            'https://www.w3.org/ns/did/v1',
            'https://w3id.org/security/multikey/v1',
        ],
        'id': did,
        'verificationMethod': [
            {
                'id': verification_method_id,
                'type': 'Multikey',
                'controller': did,
                'publicKeyMultibase': _to_base58btc(public_bytes),
            }
        ],
        'authentication': [verification_method_id],
        'assertionMethod': [verification_method_id],
        'capabilityInvocation': [verification_method_id],
        'capabilityDelegation': [verification_method_id],
        'keyAgreement': [],
    }
    private_export = {
        'kty': 'OKP',
        'crv': 'Ed25519',
        'd': private_bytes.hex(),
        'x': public_bytes.hex(),
        'alg': 'EdDSA',
    }
    meta = {
        'did': did,
        'fingerprint': fingerprint,
        'label': label,
        'created_at': _now_iso(),
    }
    return did, fingerprint, did_document, private_export, meta


def _persist_local_did(fingerprint, did_document, private_export, meta, wallet_account=None):
    did_path = DIDS_DIR / f'{fingerprint}.did.json'
    key_path = KEYS_DIR / f'{fingerprint}.key.json'
    stored_private_export = dict(private_export)
    if wallet_account:
        stored_private_export['wallet'] = wallet_account

    with did_path.open('w', encoding='utf-8') as file:
        json.dump(did_document, file, ensure_ascii=False, indent=2)
    with key_path.open('w', encoding='utf-8') as file:
        json.dump(stored_private_export, file, ensure_ascii=False, indent=2)
    _chmod_600(key_path)

    with _index_lock:
        index = _read_index()
        index[meta['did']] = {key: meta[key] for key in ('created_at', 'label', 'fingerprint')}
        if wallet_account:
            index[meta['did']]['account_address'] = wallet_account.get('address')
        _write_index(index)

    return str(did_path), str(key_path)


def _extract_wallet_account(body):
    data = body.get('data') or {}
    key_pair = data.get('key_pair') or {}
    return {
        'address': key_pair.get('address'),
        'privatekey': key_pair.get('privatekey') or key_pair.get('private_key'),
        'publickey': key_pair.get('publickey') or key_pair.get('public_key'),
    }


def _create_wallet_account():
    status_code, body = post_dchain(COMMON_ENDPOINTS['acc_create'], {})
    if status_code != 200 or body.get('state') != 'OK':
        return None, {
            'status_code': status_code,
            'state': body.get('state'),
            'msg': body.get('msg'),
            'rcode': body.get('rcode'),
            'cid': body.get('cid'),
        }

    wallet_account = _extract_wallet_account(body)
    if not wallet_account.get('address'):
        return None, {
            'status_code': status_code,
            'state': body.get('state'),
            'msg': 'wallet address not found in acc_create response',
            'response': body,
        }

    return wallet_account, None


def _extract_account(data):
    key_pair = data.get('key_pair') or {}
    return {
        'did': data.get('did'),
        'private_key': key_pair.get('privatekey') or key_pair.get('private_key'),
        'public_key': key_pair.get('publickey') or key_pair.get('public_key'),
        'address': key_pair.get('address'),
    }


def _find_first_text(value, field_name):
    if isinstance(value, dict):
        current = value.get(field_name)
        if isinstance(current, str) and current:
            return current
        if isinstance(current, list):
            for item in current:
                if isinstance(item, str) and item:
                    return item
        for child in value.values():
            found = _find_first_text(child, field_name)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_first_text(child, field_name)
            if found:
                return found
    return None


def _extract_credential_jwt(body):
    return _find_first_text(body.get('data') if isinstance(body, dict) else body, 'jwt')


def _resolve_user_identifier(payload):
    subject = payload.get('subject') if isinstance(payload, dict) else None
    if isinstance(subject, dict) and subject.get('value'):
        return subject.get('value')
    return (
        payload.get('userIdentifier')
        or payload.get('userLoginIdentifier')
        or payload.get('id')
        or payload.get('user_id')
    )


def _build_login_credential_payload(did, user_identifier, payload):
    return {
        'did': did,
        'template_id': payload.get('template_id') or LOGIN_CREDENTIAL_TEMPLATE_ID,
        'subject': {
            'key': 'id',
            'value': user_identifier,
        },
        'validfrom': payload.get('validfrom') or LOGIN_CREDENTIAL_VALID_FROM,
        'validuntil': payload.get('validuntil') or LOGIN_CREDENTIAL_VALID_UNTIL,
    }


def _store_credential(did, jwt, payload):
    if not did or not jwt:
        return
    try:
        user_identifier = _resolve_user_identifier(payload)
        user_db.update_user_identifier(did, user_identifier)
        user_db.update_credential(
            did,
            jwt,
            payload.get('validfrom'),
            payload.get('validuntil'),
        )
        user_db.commit()
    except Exception:
        logging.exception('Local DID credential cache update failed. did=%s', did)


def _attach_credential_response(data, credential_jwt, credential_payload, credential_data=None):
    data['credentialJwt'] = credential_jwt
    data['daeguCredentialJwt'] = credential_jwt
    data['credentialValidFrom'] = credential_payload.get('validfrom')
    data['credentialValidUntil'] = credential_payload.get('validuntil')
    data['daeguCredentialValidFrom'] = credential_payload.get('validfrom')
    data['daeguCredentialValidUntil'] = credential_payload.get('validuntil')
    if credential_data is not None:
        data['credential'] = credential_data


def _decode_jwt_payload(jwt):
    if not jwt or not isinstance(jwt, str):
        return {}
    parts = jwt.split('.')
    if len(parts) < 2:
        return {}
    payload = parts[1]
    payload += '=' * (-len(payload) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload.encode('utf-8')).decode('utf-8'))
    except (ValueError, TypeError):
        return {}


def _subject_value(subject):
    if not isinstance(subject, dict):
        return None
    key = subject.get('key')
    value = subject.get('value')
    if key is None or value is None:
        return None
    return f'{key}|{value}'


def _matches_subject(jwt, subject):
    expected = _subject_value(subject)
    if not expected:
        return True
    return _decode_jwt_payload(jwt).get('val') == expected


def _credential_already_issued(body):
    rcode = body.get('rcode') or {}
    msg = body.get('msg') or ''
    return rcode.get('bcode') == 'B0712' or '이미 발행' in msg or 'already' in msg.lower()


def _disclose_existing_credential(payload):
    did = payload.get('did')
    template_id = payload.get('template_id')
    if not did or not template_id:
        return None

    status_code, body = post_dchain(DID_ENDPOINTS['disclosure'], {
        'did': did,
        'template_id': template_id,
    })
    if status_code != 200 or body.get('state') != 'OK':
        return None

    jwts = ((body.get('data') or {}).get('jwts')) or []
    for item in jwts:
        jwt = item.get('jwt') if isinstance(item, dict) else None
        jwt_revoke = item.get('jwt_revoke') if isinstance(item, dict) else None
        if jwt and not jwt_revoke and _matches_subject(jwt, payload.get('subject')):
            return {
                'jwt': jwt,
                'disclosure': body.get('data'),
            }
    return None


@did_api.route('/create', methods=['POST'])
@did_api.route('/create_account', methods=['POST'])
@did_api.route('/signup', methods=['POST'])
def create_did():
    payload = request_json()
    user_identifier = _resolve_user_identifier(payload)
    label = payload.get('label') or user_identifier

    try:
        did, fingerprint, did_document, private_export, meta = _make_did_key_and_doc(label)
    except Exception as exc:
        logging.exception('Local DID generation failed.')
        return jsonify({'state': 'ERROR', 'msg': str(exc)}), 500

    wallet_account, wallet_error = _create_wallet_account()
    if wallet_error:
        logging.error('Wallet account generation failed. did=%s error=%s', did, wallet_error)
        return jsonify({
            'state': 'ERROR',
            'msg': 'wallet account generation failed',
            'walletError': wallet_error,
        }), 502

    try:
        did_path, key_path = _persist_local_did(
            fingerprint,
            did_document,
            private_export,
            meta,
            wallet_account,
        )
    except Exception as exc:
        logging.exception('Local DID file persist failed. did=%s', did)
        return jsonify({'state': 'ERROR', 'msg': str(exc)}), 500

    body = {
        'state': 'OK',
        'msg': '',
        'data': {
            'did': did,
            'fingerprint': fingerprint,
            'key_pair': {
                'privatekey': private_export['d'],
                'publickey': private_export['x'],
                'address': wallet_account.get('address'),
            },
            'wallet': wallet_account,
            'did_document': did_document,
            'stored': {
                'didDocumentPath': did_path,
                'keyPath': key_path,
            },
        },
        'local_db': {
            'saved': False,
            'userIdentifier': user_identifier,
        },
    }

    try:
        did_db.add_did(did, private_export['d'], private_export['x'], wallet_account.get('address'))
        did_db.commit()
        user_db.add_user(did, user_identifier)
        user_db.commit()
        body['local_db']['saved'] = True
    except Exception as exc:
        logging.exception('Local DID cache update failed. did=%s', did)
        body['local_db']['error'] = str(exc)

    return jsonify(body), 201


@did_api.get('/dids')
def list_local_dids():
    dids = [
        {
            'did': row[0],
            'private_key': row[1],
            'public_key': row[2],
            'account_address': row[3],
        }
        for row in get_did_info_db.get_DID_info_all()
    ]
    return jsonify({'dids': dids})


@did_api.route('/delete', methods=['POST'])
def delete_local_did():
    did = request_json().get('did') or request_json().get('label')
    if not did:
        return jsonify({'state': 'ERROR', 'msg': 'did is required'}), 400
    did_db.remove(did)
    did_db.commit()
    return jsonify({'state': 'OK', 'did': did})


@did_api.route('/accounts', methods=['GET', 'POST'])
def accounts():
    return proxy_response(DID_ENDPOINTS['accounts'], request_json())


@did_api.route('/projects', methods=['GET', 'POST'])
def projects():
    return proxy_response(DID_ENDPOINTS['projects'], request_json())


@did_api.route('/templates', methods=['GET', 'POST'])
def templates():
    return proxy_response(DID_ENDPOINTS['templates'], request_json())


@did_api.route('/issue', methods=['POST'])
def issue_credential():
    payload = request_json()
    subject = payload.get('subject') or payload.get('subjects')
    if subject is not None:
        payload['subject'] = subject
        payload.pop('subjects', None)
    status_code, body = post_dchain(DID_ENDPOINTS['issue'], payload)
    if body.get('state') == 'OK':
        credential_jwt = _extract_credential_jwt(body)
        if credential_jwt:
            _store_credential(payload.get('did'), credential_jwt, payload)
            _attach_credential_response(body.setdefault('data', {}), credential_jwt, payload)
        return jsonify(body), status_code

    if _credential_already_issued(body):
        existing_credential = _disclose_existing_credential(payload)
        if existing_credential:
            _store_credential(payload.get('did'), existing_credential.get('jwt'), payload)
            return jsonify({
                'state': 'OK',
                'msg': '',
                'rcode': {},
                'data': existing_credential,
            }), 200

    return jsonify(body), status_code


@did_api.route('/revoke', methods=['POST'])
def revoke_credential():
    return proxy_response(DID_ENDPOINTS['revoke'], request_json())


@did_api.route('/verification', methods=['POST'])
def verification():
    return proxy_response(DID_ENDPOINTS['verification'], request_json())


@did_api.route('/disclosure', methods=['POST'])
def disclosure():
    return proxy_response(DID_ENDPOINTS['disclosure'], request_json())


@did_api.route('/qrcode', methods=['POST'])
def qrcode():
    return proxy_response(DID_ENDPOINTS['qrcode'], request_json())


@did_api.route('/get_key', methods=['POST'])
def get_key():
    return proxy_response(DID_ENDPOINTS['get_key'], request_json())


@did_api.route('/regist_project', methods=['POST'])
def regist_project():
    return proxy_response(DID_ENDPOINTS['regist_project'], request_json())


@did_api.route('/edit_template', methods=['POST'])
def edit_template():
    return proxy_response(DID_ENDPOINTS['edit_template'], request_json())
