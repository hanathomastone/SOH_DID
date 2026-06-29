import base64
import json
import logging

from flask import Blueprint, jsonify, request
import os
import sys

from myapp.dchain import post_dchain, proxy_response, request_json
from myapp.utils import (
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
    status_code, body = post_dchain(DID_ENDPOINTS['create_account'], payload)
    if status_code == 200 and body.get('state') == 'OK':
        account = _extract_account(body.get('data') or {})
        if all(account.values()):
            did_db.add_did(
                account['did'],
                account['private_key'],
                account['public_key'],
                account['address'],
            )
            did_db.commit()
            user_db.add_user(account['did'], user_identifier)
            user_db.commit()
            if user_identifier:
                credential_payload = _build_login_credential_payload(
                    account['did'],
                    user_identifier,
                    payload,
                )
                credential_status, credential_body = post_dchain(
                    DID_ENDPOINTS['issue'],
                    credential_payload,
                )
                credential_jwt = _extract_credential_jwt(credential_body)
                if credential_status == 200 and credential_body.get('state') == 'OK' and credential_jwt:
                    _store_credential(account['did'], credential_jwt, credential_payload)
                    _attach_credential_response(
                        body.setdefault('data', {}),
                        credential_jwt,
                        credential_payload,
                        credential_body.get('data'),
                    )
                else:
                    user_db.mark_credential_failed(account['did'])
                    user_db.commit()
                    body.setdefault('data', {})['credentialError'] = {
                        'status_code': credential_status,
                        'state': credential_body.get('state'),
                        'msg': credential_body.get('msg'),
                        'rcode': credential_body.get('rcode'),
                        'cid': credential_body.get('cid'),
                    }
    return jsonify(body), status_code


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
