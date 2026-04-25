# 数据库连接、长连接、游标上下文、所有建表语句全部原生不动
import sqlite3
from sqlite3 import Connection
from contextlib import contextmanager
from datetime import datetime
from app.core.config import DB_PATH

conn: Connection | None = None

def get_db_connection():
    global conn
    if conn is None or not is_connection_valid(conn):
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
    return conn

def is_connection_valid(conn: Connection):
    try:
        conn.execute("SELECT 1")
        return True
    except:
        return False

@contextmanager
def db_cursor():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except:
        conn.rollback()
        raise

# 全量数据库初始化（含所有表+索引，原版完整）
def init_db():
    with db_cursor() as cur:
        cur.execute('''CREATE TABLE IF NOT EXISTS conversations
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, created_at TIMESTAMP)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS messages
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      conv_id INTEGER,
                      role TEXT,
                      content TEXT,
                      created_at TIMESTAMP)''')

        cur.execute('CREATE INDEX IF NOT EXISTS idx_conv_id ON conversations(id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_msg_conv_id ON messages(conv_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_msg_created ON messages(created_at)')

    init_feedback_db()
    init_good_answers_db()

def init_feedback_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        msg_id INTEGER NOT NULL UNIQUE,
        rate TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

def init_good_answers_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS good_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        msg_id INTEGER NOT NULL UNIQUE,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        rate TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()