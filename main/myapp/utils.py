import os

BASE_URL = os.getenv('DCHAIN_BASE_URL', 'https://daegu.go.kr/daeguchain')
API_TOKEN = os.getenv('DCHAIN_API_TOKEN', '234f2b655e789914a7574f607f0f9ebd')
CHAIN_NAME = os.getenv('DCHAIN_CHAIN_NAME', 'dchain')
LOGIN_CREDENTIAL_TEMPLATE_ID = os.getenv('DCHAIN_LOGIN_CREDENTIAL_TEMPLATE_ID', 'VLVSWVRSOPZJMPINTBNA')
LOGIN_CREDENTIAL_VALID_FROM = os.getenv('DCHAIN_LOGIN_CREDENTIAL_VALID_FROM', '2026-06-01')
LOGIN_CREDENTIAL_VALID_UNTIL = os.getenv('DCHAIN_LOGIN_CREDENTIAL_VALID_UNTIL', '2026-12-01')
MYSQL_HOST = os.getenv('MYSQL_HOST', 'db-mysql-saas-dev.cfq0uo8ms95m.ap-southeast-1.rds.amazonaws.com')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', '3306'))
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'soh_did')
MYSQL_USER = os.getenv('MYSQL_USER', 'thomastone')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'dPqkd0923!')
HEADERS = {
    'Content-Type': 'application/json',
    'Accept' : 'application/json'
    }
OWNER_ADDR = os.getenv('DCHAIN_OWNER_ADDR', '0x65e00aBd9782cf12839acd07B7D13f7E23D08432fca')
OWNER_PRIVATE = os.getenv('DCHAIN_OWNER_PRIVATE', '59c191aba12df1ce59cae76c1c22399fa25e43350880f9595d9bf55e23b3f9cafpr')
OWNER_DID = os.getenv('DCHAIN_OWNER_DID', "did:mitum:minic:0x65e00aBd9782cf12839acd07B7D13f7E23D08432fca")

DID_ENDPOINTS = {
    'create_account': '/did/create_account',
    'accounts': '/did/accounts',
    'projects': '/did/projects',
    'templates': '/did/templates',
    'issue': '/did/issue',
    'revoke': '/did/revoke',
    'verification': '/did/verification',
    'disclosure': '/did/disclosure',
    'qrcode': '/did/qrcode',
    'get_key': '/did/get_key',
    'regist_project': '/did/regist_project',
    'edit_template': '/did/edit_template',
}

TOKEN_ENDPOINTS = {
    'create': '/token/create',
    'transfer': '/token/transfer',
    'balance': '/token/balance',
    'approve': '/token/approve',
    'transfer_from': '/token/transfer_from',
    'tokens': '/token/tokens',
    'supply': '/token/supply',
    'allowance': '/token/allowance',
    'mint': '/token/mint',
    'burn': '/token/burn',
    'upload_token': '/upload/upload_token',
}

COMMON_ENDPOINTS = {
    'node_info': '/com/node_info',
    'chain_id': '/com/chain_id',
    'rpc_node': '/com/rpc_node',
    'acc_create': '/com/acc_create',
    'acc_balance': '/com/acc_balance',
    'acc_info': '/com/acc_info',
    'acc_faucet': '/com/acc_faucet',
    'cur_transfer': '/com/cur_transfer',
    'block_number': '/com/block_number',
    'block_by_hash': '/com/block_by_hash',
    'block_by_num': '/com/block_by_num',
    'trx_info': '/com/trx_info',
    'trx_count': '/com/trx_count',
}
