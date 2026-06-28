from myapp.mysql_db import MySQLStore


class DID(MySQLStore):
    def add_did(self, did, prikey, pubkey, address):
        self.cursor.execute(
            """
            INSERT INTO DID (DID, private_key, public_key, account_address)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                private_key = VALUES(private_key),
                public_key = VALUES(public_key),
                account_address = VALUES(account_address)
            """,
            (did, prikey, pubkey, address),
        )
        print('did added ', did)

    def remove(self, did):
        self.cursor.execute("DELETE FROM DID WHERE DID = %s", (did,))
