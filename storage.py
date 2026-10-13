"""Хранение данных бота: настройки пользователей (город по умолчанию, время уведомлений)."""

import sqlite3
from contextlib import contextmanager

DB_PATH = "weather_bot.db"


@contextmanager
def get_db():
    """Контекстный менеджер для работы с базой данных."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Создаёт таблицу пользователей, если её нет."""
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER PRIMARY KEY,
                default_city TEXT NOT NULL DEFAULT '',
                notify_hour INTEGER DEFAULT 7,
                notify_minute INTEGER DEFAULT 0,
                notify_enabled INTEGER DEFAULT 0
            )
        """)


def get_user(chat_id):
    """Получает или создаёт настройки пользователя."""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM users WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        if row is None:
            db.execute("INSERT INTO users (chat_id) VALUES (?)", (chat_id,))
            db.commit()
            return {
                "chat_id": chat_id,
                "default_city": "",
                "notify_hour": 7,
                "notify_minute": 0,
                "notify_enabled": False,
            }
        return dict(row)


def update_user(chat_id, **kwargs):
    """Обновляет (или создаёт) настройки пользователя."""
    if not kwargs:
        return
    keys = list(kwargs.keys())
    values = list(kwargs.values())
    placeholders = ", ".join("?" for _ in keys)
    set_clause = ", ".join(f"{k} = ?" for k in keys)
    # INSERT: chat_id + значения (5 привязок), UPDATE: значения (4 привязки) = 9 всего
    with get_db() as db:
        db.execute(
            f"""INSERT INTO users (chat_id, {', '.join(keys)})
                VALUES (?, {placeholders})
                ON CONFLICT(chat_id) DO UPDATE SET {set_clause}""",
            [chat_id] + values + values,
        )


def get_enabled_users():
    """Возвращает всех пользователей с включёнными ежедневными уведомлениями."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM users WHERE notify_enabled = 1"
        ).fetchall()
        return [dict(r) for r in rows]
