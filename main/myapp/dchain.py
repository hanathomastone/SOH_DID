from flask import jsonify, request
import requests

from myapp.utils import API_TOKEN, BASE_URL, CHAIN_NAME, HEADERS


def request_json():
    return request.get_json(silent=True) or {}


def with_auth(payload=None):
    data = dict(payload or {})
    data.setdefault('token', API_TOKEN)
    data.setdefault('chain', CHAIN_NAME)
    return data


def post_dchain(path, payload=None):
    url = BASE_URL + path
    response = requests.post(url, headers=HEADERS, json=with_auth(payload), timeout=20)
    try:
        body = response.json()
    except ValueError:
        body = {'state': 'ERROR', 'msg': response.text}
    return response.status_code, body


def proxy_response(path, payload=None):
    status_code, body = post_dchain(path, payload)
    return jsonify(body), status_code
