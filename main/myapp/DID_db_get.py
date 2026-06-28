from myapp.mysql_db import MySQLStore


class get_DID_Info(MySQLStore):
    def get_DID_info_all(self):
        self.cursor.execute("SELECT DID, private_key, public_key, account_address FROM DID")
        return self.cursor.fetchall()

    def get_DID_info_by_did(self, DID):
        self.cursor.execute(
            "SELECT DID, private_key, public_key, account_address FROM DID WHERE DID = %s",
            (DID,),
        )
        return self.cursor.fetchall()
