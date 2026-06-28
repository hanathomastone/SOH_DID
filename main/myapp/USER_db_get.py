from myapp.USER_db import ALLOWED_TOKEN_COLUMNS
from myapp.mysql_db import MySQLStore


class get_User_Info(MySQLStore):
    def get_user_info_all(self):
        self.cursor.execute("SELECT * FROM `user`")
        return self.cursor.fetchall()

    def get_user_info_by_did(self, DID):
        self.cursor.execute("SELECT * FROM `user` WHERE DID = %s", (DID,))
        return self.cursor.fetchall()

    def get_credential_by_did(self, DID):
        self.cursor.execute(
            """
            SELECT credential_jwt, credential_status, credential_valid_from, credential_valid_until
            FROM `user`
            WHERE DID = %s
            """,
            (DID,),
        )
        return self.cursor.fetchall()

    def check_token_has(self, DID, token_name):
        if token_name not in ALLOWED_TOKEN_COLUMNS:
            raise ValueError(f'Unsupported token column: {token_name}')
        self.cursor.execute(
            f"SELECT `{token_name}` FROM `user` WHERE DID = %s",
            (DID,),
        )
        return self.cursor.fetchall()
