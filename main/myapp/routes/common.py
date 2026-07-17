from flask import Blueprint, jsonify

from myapp.dchain import dchain_url, proxy_response, request_json
from myapp.utils import BASE_URL, CHAIN_NAME, COMMON_ENDPOINTS, DCHAIN_TIMEOUT, TOKEN_ENDPOINTS

common_api = Blueprint('common', __name__)


@common_api.route('/endpoints', methods=['GET'])
def endpoints():
    return jsonify(COMMON_ENDPOINTS)


@common_api.route('/dchain_config', methods=['GET'])
def dchain_config():
    return jsonify({
        'base_url': BASE_URL,
        'chain': CHAIN_NAME,
        'timeout': DCHAIN_TIMEOUT,
        'endpoints': COMMON_ENDPOINTS,
        'token_tokens_url': dchain_url(TOKEN_ENDPOINTS['tokens']),
    })


@common_api.route('/node_info', methods=['GET', 'POST'])
def node_info():
    return proxy_response(COMMON_ENDPOINTS['node_info'], request_json())


@common_api.route('/chain_id', methods=['GET', 'POST'])
def chain_id():
    return proxy_response(COMMON_ENDPOINTS['chain_id'], request_json())


@common_api.route('/rpc_node', methods=['GET', 'POST'])
def rpc_node():
    return proxy_response(COMMON_ENDPOINTS['rpc_node'], request_json())


@common_api.route('/acc_create', methods=['POST'])
def acc_create():
    return proxy_response(COMMON_ENDPOINTS['acc_create'], request_json())


@common_api.route('/acc_balance', methods=['POST'])
def acc_balance():
    return proxy_response(COMMON_ENDPOINTS['acc_balance'], request_json())


@common_api.route('/acc_info', methods=['POST'])
def acc_info():
    return proxy_response(COMMON_ENDPOINTS['acc_info'], request_json())


@common_api.route('/acc_faucet', methods=['POST'])
def acc_faucet():
    return proxy_response(COMMON_ENDPOINTS['acc_faucet'], request_json())


@common_api.route('/cur_transfer', methods=['POST'])
def cur_transfer():
    return proxy_response(COMMON_ENDPOINTS['cur_transfer'], request_json())


@common_api.route('/block_number', methods=['GET', 'POST'])
def block_number():
    return proxy_response(COMMON_ENDPOINTS['block_number'], request_json())


@common_api.route('/block_by_hash', methods=['POST'])
def block_by_hash():
    return proxy_response(COMMON_ENDPOINTS['block_by_hash'], request_json())


@common_api.route('/block_by_num', methods=['POST'])
def block_by_num():
    return proxy_response(COMMON_ENDPOINTS['block_by_num'], request_json())


@common_api.route('/trx_info', methods=['POST'])
def trx_info():
    return proxy_response(COMMON_ENDPOINTS['trx_info'], request_json())


@common_api.route('/trx_count', methods=['POST'])
def trx_count():
    return proxy_response(COMMON_ENDPOINTS['trx_count'], request_json())
