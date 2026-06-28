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


class User(MySQLStore):
    def add_user(self, DID, user_identifier=None):
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

    def update_credential(self, DID, jwt, valid_from=None, valid_until=None, status='ISSUED'):
        self.cursor.execute(
            """
            UPDATE `user`
            SET credential_jwt = %s,
                credential_status = %s,
                credential_valid_from = %s,
                credential_valid_until = %s
            WHERE DID = %s
            """,
            (jwt, status, valid_from, valid_until, DID),
        )

    def mark_credential_failed(self, DID):
        self.cursor.execute(
            "UPDATE `user` SET credential_status = %s WHERE DID = %s",
            ('FAILED', DID),
        )

    def increase_balance(self, DID, token_name):
        if token_name not in ALLOWED_TOKEN_COLUMNS:
            raise ValueError(f'Unsupported token column: {token_name}')
        self.cursor.execute(
            f"UPDATE `user` SET `{token_name}` = 1 WHERE DID = %s",
            (DID,),
        )
        return self.cursor.fetchall()

    def remove(self, DID):
        self.cursor.execute("DELETE FROM `user` WHERE DID = %s", (DID,))
