from flask import jsonify, request
import requests
from requests import exceptions as request_exceptions

from myapp.utils import API_TOKEN, BASE_URL, CHAIN_NAME, DCHAIN_TIMEOUT, HEADERS


def request_json():
    return request.get_json(silent=True) or {}


def with_auth(payload=None):
    data = dict(payload or {})
    data.setdefault('token', API_TOKEN)
    data.setdefault('chain', CHAIN_NAME)
    return data


def dchain_url(path):
    return f"{BASE_URL.rstrip('/')}/{path.lstrip('/')}"


def post_dchain(path, payload=None):
    url = dchain_url(path)
    try:
        response = requests.post(
            url,
            headers=HEADERS,
            json=with_auth(payload),
            timeout=DCHAIN_TIMEOUT,
        )
    except request_exceptions.Timeout as exc:
        return 504, {
            'state': 'ERROR',
            'msg': 'DChain request timed out',
            'upstream': {
                'url': url,
                'path': path,
                'timeout': DCHAIN_TIMEOUT,
                'error_type': exc.__class__.__name__,
            },
        }
    except request_exceptions.ConnectionError as exc:
        return 502, {
            'state': 'ERROR',
            'msg': 'DChain connection failed',
            'upstream': {
                'url': url,
                'path': path,
                'timeout': DCHAIN_TIMEOUT,
                'error_type': exc.__class__.__name__,
            },
        }
    except request_exceptions.RequestException as exc:
        return 502, {
            'state': 'ERROR',
            'msg': 'DChain request failed',
            'upstream': {
                'url': url,
                'path': path,
                'timeout': DCHAIN_TIMEOUT,
                'error_type': exc.__class__.__name__,
            },
        }
    try:
        body = response.json()
    except ValueError:
        body = {'state': 'ERROR', 'msg': response.text}
    if response.status_code >= 400:
        body.setdefault('state', 'ERROR')
        body.setdefault('upstream', {})
        body['upstream'].setdefault('url', url)
        body['upstream'].setdefault('path', path)
    return response.status_code, body


def proxy_response(path, payload=None):
    status_code, body = post_dchain(path, payload)
    return jsonify(body), status_code
