from myapp.mysql_db import MySQLStore


ALLOWED_TOKEN_COLUMNS = {
    'ESSENTIAL_VIDEO_1',
    'ESSENTIAL_VIDEO_2',
    'ESSENTIAL_VIDEO_3',
    'ESSENTIAL_VIDEO_4',
    'ESSENTIAL_VIDEO_5',
    'OPTIONAL_VIDEO_1',
    'OPTIONAL_VIDEO_2',
    'OPTIONAL_VIDEO_3',
    'OPTIONAL_VIDEO_4',
    'OPTIONAL_VIDEO_5',
    'OPTIONAL_VIDEO_6',
    'OPTIONAL_VIDEO_7',
}


def normalize_token_column(token_name):
    if not isinstance(token_name, str):
        raise ValueError(f'Unsupported token column: {token_name}')
    normalized = token_name.strip().replace('-', '_').replace(' ', '_').upper()
    if normalized not in ALLOWED_TOKEN_COLUMNS:
        raise ValueError(f'Unsupported token column: {token_name}')
    return normalized


class User(MySQLStore):
    def add_user(self, DID, user_identifier=None):
        self.reconnect()
        self.cursor.execute(
            """
            INSERT IGNORE INTO `user` (
                DID,
                user_identifier,
                ESSENTIAL_VIDEO_1,
                ESSENTIAL_VIDEO_2,
                ESSENTIAL_VIDEO_3,
                ESSENTIAL_VIDEO_4,
                ESSENTIAL_VIDEO_5,
                OPTIONAL_VIDEO_1,
                OPTIONAL_VIDEO_2,
                OPTIONAL_VIDEO_3,
                OPTIONAL_VIDEO_4,
                OPTIONAL_VIDEO_5,
                OPTIONAL_VIDEO_6,
                OPTIONAL_VIDEO_7
            ) VALUES (%s, %s, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
            ON DUPLICATE KEY UPDATE
                user_identifier = COALESCE(VALUES(user_identifier), user_identifier)
            """,
            (DID, user_identifier),
        )
        print('user added ', DID)

    def update_user_identifier(self, DID, user_identifier):
        if not DID or not user_identifier:
            return
        self.reconnect()
        self.cursor.execute(
            """
            UPDATE `user`
            SET user_identifier = %s
            WHERE DID = %s
            """,
            (user_identifier, DID),
        )

    def update_credential(self, DID, jwt, valid_from=None, valid_until=None, status='ISSUED'):
        self.reconnect()
        self.cursor.execute(
            """
            UPDATE `user`
            SET credential_jwt = %s,
                credential_status = %s,
                credential_valid_from = %s,
                credential_valid_until = %s,
                daegu_credential_jwt = %s,
                daegu_credential_status = %s,
                daegu_credential_valid_from = %s,
                daegu_credential_valid_until = %s
            WHERE DID = %s
            """,
            (jwt, status, valid_from, valid_until, jwt, status, valid_from, valid_until, DID),
        )

    def mark_credential_failed(self, DID):
        self.reconnect()
        self.cursor.execute(
            """
            UPDATE `user`
            SET credential_status = %s,
                daegu_credential_status = %s
            WHERE DID = %s
            """,
            ('FAILED', 'FAILED', DID),
        )

    def increase_balance(self, DID, token_name):
        token_name = normalize_token_column(token_name)
        self.reconnect()
        self.cursor.execute(
            f"UPDATE `user` SET `{token_name}` = 1 WHERE DID = %s",
            (DID,),
        )
        return token_name, self.cursor.rowcount

    def remove(self, DID):
        self.reconnect()
        self.cursor.execute("DELETE FROM `user` WHERE DID = %s", (DID,))
