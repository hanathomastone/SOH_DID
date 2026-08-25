import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask, jsonify

from myapp.routes import token


class TokenRetrieveTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(token.token_api, url_prefix='/token')
        self.client = self.app.test_client()
        self.temp_dir = tempfile.TemporaryDirectory()
        data_dir = Path(self.temp_dir.name)
        self.keys_dir = data_dir / 'keys'
        self.keys_dir.mkdir()
        self.index_path = data_dir / 'index.json'
        self.holder = '0xLegacyWallet'
        self.wallet_private_key = 'wallet-signing-key-pr'
        fingerprint = 'zLegacyFingerprint'
        self.index_path.write_text(json.dumps({
            'did:key:zLegacyFingerprint': {
                'fingerprint': fingerprint,
                'account_address': self.holder,
            },
        }), encoding='utf-8')
        (self.keys_dir / f'{fingerprint}.key.json').write_text(json.dumps({
            'd': 'ed25519-did-key',
            'wallet': {
                'address': self.holder,
                'privatekey': self.wallet_private_key,
            },
        }), encoding='utf-8')
        self.path_patch = patch.multiple(
            token,
            INDEX_PATH=self.index_path,
            KEYS_DIR=self.keys_dir,
            OWNER_ADDR='0xOwner',
            OWNER_PRIVATE='owner-private-key',
        )
        self.path_patch.start()

    def tearDown(self):
        self.path_patch.stop()
        self.temp_dir.cleanup()

    def _payload(self):
        return {
            'contract_address': '0xContract',
            'sender': '0xOwner',
            'sender_pkey': 'owner-private-key',
            'holder': self.holder,
            'receiver': '0xOwner',
            'amount': 1,
        }

    def test_retrieve_approves_legacy_wallet_then_transfers_without_exposing_key(self):
        with patch.object(token, 'post_dchain', return_value=(200, {'state': 'OK'})) as approve, \
                patch.object(token, 'proxy_response') as transfer:
            transfer.side_effect = lambda path, payload: (jsonify({'state': 'OK'}), 200)

            response = self.client.post('/token/retrieve', json=self._payload())

        self.assertEqual(response.status_code, 200)
        approve.assert_called_once_with(token.TOKEN_ENDPOINTS['approve'], {
            'cont_addr': '0xContract',
            'holder': self.holder,
            'holder_pkey': self.wallet_private_key,
            'approved': '0xOwner',
            'amount': 1,
        })
        transfer.assert_called_once_with(token.TOKEN_ENDPOINTS['transfer_from'], self._payload())
        self.assertNotIn(self.wallet_private_key, response.get_data(as_text=True))

    def test_retrieve_rejects_request_without_owner_secret(self):
        payload = self._payload()
        payload['sender_pkey'] = 'wrong-key'

        with patch.object(token, 'post_dchain') as approve, patch.object(token, 'proxy_response') as transfer:
            response = self.client.post('/token/retrieve', json=payload)

        self.assertEqual(response.status_code, 403)
        approve.assert_not_called()
        transfer.assert_not_called()

    def test_retrieve_finds_legacy_wallet_when_index_has_no_account_address(self):
        self.index_path.write_text('{}', encoding='utf-8')
        with patch.object(token, 'post_dchain', return_value=(200, {'state': 'OK'})) as approve, \
                patch.object(token, 'proxy_response') as transfer:
            transfer.side_effect = lambda path, payload: (jsonify({'state': 'OK'}), 200)

            response = self.client.post('/token/retrieve', json=self._payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(approve.call_args.args[1]['holder_pkey'], self.wallet_private_key)

    def test_approval_failure_does_not_echo_wallet_private_key(self):
        upstream = {
            'state': 'OOPS',
            'rcode': {'bcode': 'B0102'},
            'msg': f'invalid holder_pkey: {self.wallet_private_key}',
        }
        with patch.object(token, 'post_dchain', return_value=(406, upstream)), \
                patch.object(token, 'proxy_response') as transfer:
            response = self.client.post('/token/retrieve', json=self._payload())

        self.assertEqual(response.status_code, 406)
        transfer.assert_not_called()
        self.assertNotIn(self.wallet_private_key, response.get_data(as_text=True))
        self.assertEqual(response.get_json()['stage'], 'approve')


if __name__ == '__main__':
    unittest.main()
