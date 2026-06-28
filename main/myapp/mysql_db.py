from contextlib import closing
import os
import sys

VENDOR_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vendor"))
if VENDOR_DIR not in sys.path:
    sys.path.insert(0, VENDOR_DIR)

import pymysql
from pymysql.err import OperationalError

from myapp.utils import MYSQL_DATABASE, MYSQL_HOST, MYSQL_PASSWORD, MYSQL_PORT, MYSQL_USER


def connect():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset='utf8mb4',
        autocommit=False,
    )


def ensure_tables():
    with closing(connect()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS DID (
                    DID VARCHAR(255) PRIMARY KEY,
                    private_key TEXT,
                    public_key TEXT,
                    account_address VARCHAR(255)
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS `user` (
                    DID VARCHAR(255) PRIMARY KEY,
                    ESSENTIAL_VIDEO_1 INT DEFAULT 0,
                    ESSENTIAL_VIDEO_2 INT DEFAULT 0,
                    ESSENTIAL_VIDEO_3 INT DEFAULT 0,
                    ESSENTIAL_VIDEO_4 INT DEFAULT 0,
                    ESSENTIAL_VIDEO_5 INT DEFAULT 0,
                    OPTIONAL_VIDEO_1 INT DEFAULT 0,
                    OPTIONAL_VIDEO_2 INT DEFAULT 0,
                    OPTIONAL_VIDEO_3 INT DEFAULT 0,
                    OPTIONAL_VIDEO_4 INT DEFAULT 0,
                    OPTIONAL_VIDEO_5 INT DEFAULT 0,
                    OPTIONAL_VIDEO_6 INT DEFAULT 0,
                    OPTIONAL_VIDEO_7 INT DEFAULT 0
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                """
            )
            ensure_column(cursor, 'user', 'user_identifier', 'VARCHAR(255) NULL')
            ensure_column(cursor, 'user', 'credential_jwt', 'TEXT NULL')
            ensure_column(cursor, 'user', 'credential_status', 'VARCHAR(20) NULL')
            ensure_column(cursor, 'user', 'credential_valid_from', 'DATE NULL')
            ensure_column(cursor, 'user', 'credential_valid_until', 'DATE NULL')
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS Token (
                    token_name VARCHAR(255) PRIMARY KEY,
                    token_symbol VARCHAR(255),
                    contract_addr VARCHAR(255),
                    issued VARCHAR(255),
                    supply VARCHAR(255),
                    meta_data JSON NULL
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS keyValue (
                    `key` VARBINARY(255) PRIMARY KEY,
                    `value` LONGBLOB
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                """
            )
        conn.commit()


def ensure_column(cursor, table_name, column_name, definition):
    try:
        cursor.execute(
            f"ALTER TABLE `{table_name}` ADD COLUMN `{column_name}` {definition}"
        )
    except OperationalError as exc:
        if exc.args and exc.args[0] == 1060:
            return
        raise


class MySQLStore:
    def __init__(self):
        ensure_tables()
        self.conn = connect()
        self.cursor = self.conn.cursor()

    def close(self):
        self.conn.commit()
        self.cursor.close()
        self.conn.close()

    def commit(self):
        self.conn.commit()
