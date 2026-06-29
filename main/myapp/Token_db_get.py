from myapp.mysql_db import MySQLStore


class get_Token_info(MySQLStore):
    def get_addr_by_name(self, token_name):
        self.cursor.execute(
            "SELECT contract_addr FROM Token WHERE UPPER(token_name) = UPPER(%s)",
            (token_name,),
        )
        return self.cursor.fetchall()

    def all_list(self):
        self.cursor.execute("SELECT token_name, token_symbol, contract_addr, issued, supply FROM Token")
        return self.cursor.fetchall()
