from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import threading
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from flask import Blueprint, abort, jsonify, request
import jwt
from jwt import ExpiredSignatureError, InvalidAudienceError
import requests
from requests import exceptions as request_exceptions

from myapp.dchain import dchain_url
from myapp.utils import API_TOKEN, CHAIN_NAME, DCHAIN_TIMEOUT, HEADERS


did_api = Blueprint('did', __name__)

DATA_DIR = Path(os.getenv('DID_DATA_DIR') or os.getenv('DATA_DIR', './data'))
DIDS_DIR = DATA_DIR / 'dids'
KEYS_DIR = DATA_DIR / 'keys'
INDEX_PATH = DATA_DIR / 'index.json'

for directory in (DIDS_DIR, KEYS_DIR):
    directory.mkdir(parents=True, exist_ok=True)

_index_lock = threading.Lock()
_ED25519_PUB_CODEC_PREFIX = bytes([0xED, 0x01])
_BASE58_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
_BASE58_INDEX = {char: index for index, char in enumerate(_BASE58_ALPHABET)}


def _request_json():
    return request.get_json(silent=True) or {}


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


def _base58_decode(value):
    number = 0
    for char in value:
        if char not in _BASE58_INDEX:
            raise ValueError(f'invalid base58 character: {char}')
        number = number * 58 + _BASE58_INDEX[char]

    raw = number.to_bytes((number.bit_length() + 7) // 8, 'big') if number else b''
    padding = 0
    for char in value:
        if char == '1':
            padding += 1
        else:
            break
    return (b'\x00' * padding) + raw


def _to_base58btc(raw):
    return 'z' + _base58_encode(raw)


def _from_base58btc(value):
    if not value or not value.startswith('z'):
        raise ValueError('expected base58btc value')
    return _base58_decode(value[1:])


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _jwt_now():
    return int(time.time())


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


def _fingerprint_from_did(did):
    if not isinstance(did, str) or not did.startswith('did:key:'):
        raise ValueError('Only did:key is supported')
    return did.split(':')[-1]


def _fingerprint_from_did_or_fingerprint(value):
    if not value or not isinstance(value, str):
        abort(400, description='did or fingerprint is required')
    value = value.strip()
    if value.startswith('did:key:'):
        return _fingerprint_from_did(value), value
    return value, f'did:key:{value}'


def make_did_key_and_doc(label=None):
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


def _create_wallet_account():
    url = dchain_url('/com/acc_create')
    payload = {
        'token': API_TOKEN,
        'chain': CHAIN_NAME,
    }
    try:
        response = requests.post(url, headers=HEADERS, json=payload, timeout=DCHAIN_TIMEOUT)
    except request_exceptions.Timeout as exc:
        return None, {
            'status_code': 504,
            'state': 'ERROR',
            'msg': 'DChain wallet account generation timed out',
            'url': url,
            'timeout': DCHAIN_TIMEOUT,
            'error_type': exc.__class__.__name__,
        }
    except request_exceptions.ConnectionError as exc:
        return None, {
            'status_code': 502,
            'state': 'ERROR',
            'msg': 'DChain wallet account connection failed',
            'url': url,
            'timeout': DCHAIN_TIMEOUT,
            'error_type': exc.__class__.__name__,
        }
    except request_exceptions.RequestException as exc:
        return None, {
            'status_code': 502,
            'state': 'ERROR',
            'msg': 'DChain wallet account request failed',
            'url': url,
            'timeout': DCHAIN_TIMEOUT,
            'error_type': exc.__class__.__name__,
        }
    try:
        body = response.json()
    except ValueError:
        body = {'state': 'ERROR', 'msg': response.text}

    if response.status_code != 200 or body.get('state') != 'OK':
        return None, {
            'status_code': response.status_code,
            'state': body.get('state'),
            'msg': body.get('msg'),
            'rcode': body.get('rcode'),
            'cid': body.get('cid'),
            'response': body,
        }

    key_pair = (body.get('data') or {}).get('key_pair') or {}
    wallet_account = {
        'address': key_pair.get('address'),
        'privatekey': key_pair.get('privatekey') or key_pair.get('private_key'),
        'publickey': key_pair.get('publickey') or key_pair.get('public_key'),
    }
    if not wallet_account.get('address'):
        return None, {
            'status_code': response.status_code,
            'state': body.get('state'),
            'msg': 'wallet address not found in acc_create response',
            'response': body,
        }

    return wallet_account, None


def persist_to_disk(fingerprint, did_document, private_export, meta, wallet_account=None):
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
        index[meta['did']] = {
            key: meta[key]
            for key in ('created_at', 'label', 'fingerprint')
        }
        if wallet_account:
            index[meta['did']]['account_address'] = wallet_account.get('address')
        _write_index(index)

    return str(did_path), str(key_path)


def _load_private_key_by_did(did):
    fingerprint = _fingerprint_from_did(did)
    key_path = KEYS_DIR / f'{fingerprint}.key.json'
    if not key_path.exists():
        raise FileNotFoundError('private key not found on server')

    with key_path.open('r', encoding='utf-8') as file:
        data = json.load(file)
    private_bytes = bytes.fromhex(data['d'])
    return Ed25519PrivateKey.from_private_bytes(private_bytes), fingerprint


def _load_public_key_from_diddoc(did):
    fingerprint = _fingerprint_from_did(did)
    did_path = DIDS_DIR / f'{fingerprint}.did.json'
    if not did_path.exists():
        raise FileNotFoundError('issuer DID document not found on server')

    with did_path.open('r', encoding='utf-8') as file:
        did_document = json.load(file)

    verification_methods = did_document.get('verificationMethod', [])
    if not verification_methods:
        raise ValueError('No verificationMethod in DID document')

    public_key_multibase = verification_methods[0].get('publicKeyMultibase')
    public_bytes = _from_base58btc(public_key_multibase)
    return Ed25519PublicKey.from_public_bytes(public_bytes)


def verify_vc_token(vc_jwt, aud=None):
    try:
        unverified = jwt.decode(vc_jwt, options={'verify_signature': False})
        issuer = unverified.get('iss')
        if not issuer:
            return False, 'No iss in VC'
    except Exception as exc:
        return False, f'malformed token: {exc}'

    try:
        public_key = _load_public_key_from_diddoc(issuer)
    except Exception as exc:
        return False, f'issuer key load failed: {exc}'

    try:
        payload = jwt.decode(
            vc_jwt,
            public_key,
            algorithms=['EdDSA'],
            options={
                'require': ['iss', 'sub', 'exp', 'nbf', 'iat'],
                'verify_aud': bool(aud),
            },
            audience=aud if aud else None,
        )
        return True, payload
    except ExpiredSignatureError:
        return False, 'expired'
    except InvalidAudienceError:
        return False, 'audience mismatch'
    except Exception as exc:
        return False, str(exc)


@did_api.route('/create', methods=['POST'])
@did_api.route('/create_account', methods=['POST'])
@did_api.route('/signup', methods=['POST'])
def create_did():
    body = _request_json()
    label = body.get('label') or body.get('userIdentifier') or body.get('id') or body.get('user_id')

    did, fingerprint, did_document, private_export, meta = make_did_key_and_doc(label=label)
    wallet_account, wallet_error = _create_wallet_account()
    if wallet_error:
        return jsonify({
            'state': 'ERROR',
            'msg': 'wallet account generation failed',
            'walletError': wallet_error,
        }), wallet_error.get('status_code', 502)

    did_path, key_path = persist_to_disk(
        fingerprint,
        did_document,
        private_export,
        meta,
        wallet_account=wallet_account,
    )

    return jsonify({
        'state': 'OK',
        'msg': '',
        'data': {
            'did': did,
            'fingerprint': fingerprint,
            'label': label,
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
    }), 201


@did_api.get('/dids')
def list_dids():
    with _index_lock:
        index = _read_index()
    items = [
        {'did': did, **meta}
        for did, meta in sorted(
            index.items(),
            key=lambda item: item[1].get('created_at', ''),
            reverse=True,
        )
    ]
    return jsonify({'count': len(items), 'items': items})


@did_api.route('/resolve', methods=['POST'])
def resolve_did():
    body = _request_json()
    did_or_fingerprint = body.get('did') or body.get('fingerprint') or body.get('label')
    fingerprint, _did = _fingerprint_from_did_or_fingerprint(did_or_fingerprint)

    did_path = DIDS_DIR / f'{fingerprint}.did.json'
    if not did_path.exists():
        abort(404, description='DID not found on server')
    with did_path.open('r', encoding='utf-8') as file:
        return jsonify(json.load(file))


@did_api.route('/delete', methods=['POST'])
def delete_did():
    body = _request_json()
    did_or_fingerprint = body.get('did') or body.get('fingerprint') or body.get('label')
    fingerprint, did = _fingerprint_from_did_or_fingerprint(did_or_fingerprint)

    did_path = DIDS_DIR / f'{fingerprint}.did.json'
    key_path = KEYS_DIR / f'{fingerprint}.key.json'
    removed = {'didDocument': False, 'privateKey': False}

    if did_path.exists():
        did_path.unlink()
        removed['didDocument'] = True
    if key_path.exists():
        key_path.unlink()
        removed['privateKey'] = True

    with _index_lock:
        index = _read_index()
        if did in index:
            del index[did]
            _write_index(index)

    if not any(removed.values()):
        abort(404, description='Nothing to delete; DID not found')

    return jsonify({'state': 'OK', 'deleted': removed, 'did': did})


@did_api.route('/issue-vc', methods=['POST'])
def issue_vc():
    body = _request_json()
    issuer = body.get('issuer')
    subject = body.get('subject')
    claims = body.get('claims', {})
    ttl = int(body.get('ttl', 3600))
    aud = body.get('aud')

    if not issuer or not subject:
        abort(400, description='issuer and subject are required')

    private_key, _fingerprint = _load_private_key_by_did(issuer)
    now = _jwt_now()
    exp = now + ttl

    payload = {
        'iss': issuer,
        'sub': subject,
        'nbf': now,
        'iat': now,
        'exp': exp,
        'vc': {
            '@context': ['https://www.w3.org/2018/credentials/v1'],
            'type': ['VerifiableCredential'],
            'credentialSubject': claims,
        },
    }
    if aud:
        payload['aud'] = aud

    vc_jwt = jwt.encode(payload, private_key, algorithm='EdDSA')
    return jsonify({'vc_jwt': vc_jwt, 'exp': exp})


@did_api.route('/verify-vc', methods=['POST'])
def verify_vc():
    body = _request_json()
    token = body.get('vc_jwt')
    aud = body.get('aud')
    if not token:
        abort(400, description='vc_jwt is required')

    ok, data = verify_vc_token(token, aud=aud)
    if ok:
        return jsonify({'valid': True, 'payload': data})
    return jsonify({'valid': False, 'reason': data}), 400


@did_api.route('/present-vp', methods=['POST'])
def present_vp():
    body = _request_json()
    holder = body.get('holder')
    vc_jwts = body.get('vc_jwts', [])
    aud = body.get('aud')
    ttl = int(body.get('ttl', 300))

    if not holder or not vc_jwts or not aud:
        abort(400, description='holder, vc_jwts, aud are required')

    private_key, _fingerprint = _load_private_key_by_did(holder)
    now = _jwt_now()
    exp = now + ttl

    payload = {
        'iss': holder,
        'aud': aud,
        'nbf': now,
        'iat': now,
        'exp': exp,
        'vp': {
            '@context': ['https://www.w3.org/2018/credentials/v1'],
            'type': ['VerifiablePresentation'],
            'verifiableCredential': vc_jwts,
        },
    }

    vp_jwt = jwt.encode(payload, private_key, algorithm='EdDSA')
    return jsonify({'vp_jwt': vp_jwt, 'exp': exp})


@did_api.route('/verify-vp', methods=['POST'])
def verify_vp():
    body = _request_json()
    token = body.get('vp_jwt')
    expected_aud = body.get('aud')
    if not token or not expected_aud:
        abort(400, description='vp_jwt and aud are required')

    try:
        unverified = jwt.decode(token, options={'verify_signature': False})
        holder = unverified.get('iss')
        if not holder:
            raise ValueError('No iss in VP')
    except Exception as exc:
        return jsonify({'valid': False, 'reason': f'malformed token: {exc}'}), 400

    try:
        public_key = _load_public_key_from_diddoc(holder)
        payload = jwt.decode(
            token,
            public_key,
            algorithms=['EdDSA'],
            options={'require': ['iss', 'aud', 'exp', 'nbf', 'iat']},
            audience=expected_aud,
        )
    except ExpiredSignatureError:
        return jsonify({'valid': False, 'reason': 'expired'}), 400
    except InvalidAudienceError:
        return jsonify({'valid': False, 'reason': 'audience mismatch'}), 400
    except Exception as exc:
        return jsonify({'valid': False, 'reason': str(exc)}), 400

    vcs = []
    for vc_jwt in payload.get('vp', {}).get('verifiableCredential', []):
        ok, data = verify_vc_token(vc_jwt, aud=None)
        if ok:
            vcs.append({'valid': True, 'iss': data.get('iss'), 'sub': data.get('sub')})
        else:
            vcs.append({'valid': False, 'reason': data})

    return jsonify({
        'valid': all(item.get('valid') for item in vcs),
        'holder': holder,
        'vcs': vcs,
        'payload': payload,
    })
