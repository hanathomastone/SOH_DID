from myapp.mysql_db import MySQLStore


class Token(MySQLStore):
    def add_token(self, token_name, contract_addr, issued, supply, token_symbol=None, meta_data=None):
        self.reconnect()
        self.cursor.execute(
            """
            INSERT INTO Token
                (token_name, token_symbol, contract_addr, issued, supply, meta_data)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                token_symbol = VALUES(token_symbol),
                contract_addr = VALUES(contract_addr),
                issued = VALUES(issued),
                supply = VALUES(supply),
                meta_data = VALUES(meta_data)
            """,
            (token_name, token_symbol, contract_addr, issued, str(supply), meta_data),
        )
