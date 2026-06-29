from myapp.USER_db import normalize_token_column
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
            SELECT
                daegu_credential_jwt,
                daegu_credential_status,
                daegu_credential_valid_from,
                daegu_credential_valid_until
            FROM `user`
            WHERE DID = %s
            """,
            (DID,),
        )
        return self.cursor.fetchall()

    def check_token_has(self, DID, token_name):
        token_name = normalize_token_column(token_name)
        self.cursor.execute(
            f"SELECT `{token_name}` FROM `user` WHERE DID = %s",
            (DID,),
        )
        return self.cursor.fetchall()
