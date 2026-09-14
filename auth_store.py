from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import bcrypt
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
import config_data as config


@dataclass(frozen=True)
class User:
    id: int
    username: str
    display_name: str
    role: str
    enabled: bool
    can_upload: bool = False
    can_switch_models: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _token_hash(token: str) -> str:
    secret = str(config.auth_secret_key).encode("utf-8")
    return hmac.new(secret, str(token).encode("utf-8"), hashlib.sha256).hexdigest()


@contextmanager
def _connect():
    path = Path(config.auth_db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _user_from_row(row: sqlite3.Row | None) -> User | None:
    if row is None:
        return None
    return User(
        id=int(row["id"]),
        username=str(row["username"]),
        display_name=str(row["display_name"]),
        role=str(row["role"]),
        enabled=bool(row["enabled"]),
        can_upload=bool(row["can_upload"]),
        can_switch_models=bool(row["can_switch_models"]),
    )


def init_db() -> None:
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                last_login_at TEXT
            );
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL DEFAULT '新对话',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK (role IN ('human', 'ai', 'system')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires
                ON auth_sessions(expires_at);
            CREATE INDEX IF NOT EXISTS idx_chat_sessions_user
                ON chat_sessions(user_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_chat_messages_session
                ON chat_messages(session_id, id);
            """
        )
        columns = {row[1] for row in connection.execute('PRAGMA table_info(users)')}
        for name in ('can_upload', 'can_switch_models'):
            if name not in columns:
                connection.execute(f'ALTER TABLE users ADD COLUMN {name} INTEGER NOT NULL DEFAULT 0')
        _ensure_seed_user(connection, "admin", "admin123", "系统管理员", "admin")
        _ensure_seed_user(connection, "student", "student123", "演示用户", "user")
        connection.commit()
    migrate_legacy_history()


def _ensure_seed_user(
    connection: sqlite3.Connection,
    username: str,
    password: str,
    display_name: str,
    role: str,
) -> None:
    row = connection.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if row:
        return
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    connection.execute(
        """
        INSERT INTO users(username, password_hash, display_name, role, enabled, created_at)
        VALUES (?, ?, ?, ?, 1, ?)
        """,
        (username, password_hash, display_name, role, _now()),
    )


def authenticate(username: str, password: str) -> User | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE username = ? AND enabled = 1",
            (str(username or "").strip(),),
        ).fetchone()
        if row is None:
            return None
        try:
            valid = bcrypt.checkpw(
                str(password or "").encode("utf-8"),
                str(row["password_hash"]).encode("utf-8"),
            )
        except ValueError:
            valid = False
        if not valid:
            return None
        connection.execute(
            "UPDATE users SET last_login_at = ? WHERE id = ?",
            (_now(), row["id"]),
        )
        connection.commit()
        return _user_from_row(row)

def register_user(username: str, password: str, display_name: str = "") -> User:
    username = str(username or "").strip()
    display_name = str(display_name or username).strip() or username
    password_hash = bcrypt.hashpw(str(password or "").encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    try:
        with _connect() as connection:
            cursor = connection.execute(
                "INSERT INTO users(username, password_hash, display_name, role, enabled, created_at) VALUES (?, ?, ?, 'user', 1, ?)",
                (username, password_hash, display_name[:80], _now()),
            )
            connection.commit()
            return _user_from_row(connection.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone())
    except sqlite3.IntegrityError as exc:
        raise ValueError("用户名已存在") from exc


def create_auth_session(user_id: int) -> str:
    token = secrets.token_urlsafe(48)
    token_hash = _token_hash(token)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=config.auth_cookie_max_age)
    ).isoformat(timespec="seconds")
    with _connect() as connection:
        connection.execute(
            "INSERT INTO auth_sessions(token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (token_hash, user_id, expires_at, _now()),
        )
        connection.commit()
    return token


def get_user_by_token(token: str | None) -> User | None:
    if not token:
        return None
    token_hash = _token_hash(token)
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT users.*
            FROM auth_sessions
            JOIN users ON users.id = auth_sessions.user_id
            WHERE auth_sessions.token_hash = ?
              AND auth_sessions.expires_at > ?
              AND users.enabled = 1
            """,
            (token_hash, _now()),
        ).fetchone()
        return _user_from_row(row)


def revoke_auth_session(token: str | None) -> None:
    if not token:
        return
    token_hash = _token_hash(token)
    with _connect() as connection:
        connection.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (token_hash,))
        connection.commit()


def user_payload(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "is_admin": user.role == "admin",
        "can_upload": user.role == "admin" or user.can_upload,
        "can_switch_models": user.role == "admin" or user.can_switch_models,
    }


def list_users() -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute('SELECT * FROM users ORDER BY id DESC').fetchall()
    return [dict(user_payload(_user_from_row(row)), enabled=bool(row['enabled']),
                 created_at=row['created_at'], last_login_at=row['last_login_at']) for row in rows]


def set_user_permissions(user_id: int, can_upload: bool, can_switch_models: bool, enabled: bool | None = None) -> None:
    with _connect() as connection:
        row = connection.execute('SELECT role FROM users WHERE id = ?', (user_id,)).fetchone()
        if row is None:
            raise FileNotFoundError('用户不存在')
        if row['role'] == 'admin':
            raise ValueError('管理员保留全部权限')
        connection.execute('UPDATE users SET can_upload = ?, can_switch_models = ? WHERE id = ?',
                           (int(can_upload), int(can_switch_models), user_id))
        if enabled is not None:
            connection.execute('UPDATE users SET enabled = ? WHERE id = ?', (int(enabled), user_id))
            if not enabled:
                connection.execute('DELETE FROM auth_sessions WHERE user_id = ?', (user_id,))



def ensure_chat_session(user_id: int, session_id: str, title: str = "新对话") -> None:
    normalized = str(session_id or "").strip()
    if not normalized or len(normalized) > 120 or "/" in normalized or "\\" in normalized:
        raise ValueError("无效的会话 ID")
    now = _now()
    with _connect() as connection:
        row = connection.execute(
            "SELECT user_id FROM chat_sessions WHERE id = ?", (normalized,)
        ).fetchone()
        if row is not None:
            if int(row["user_id"]) != user_id:
                raise PermissionError("无权访问该会话")
            return
        connection.execute(
            "INSERT INTO chat_sessions(id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (normalized, user_id, title, now, now),
        )
        connection.commit()


def get_chat_session(user_id: int, session_id: str) -> sqlite3.Row:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
    if row is None:
        raise FileNotFoundError(f"会话不存在：{session_id}")
    return row


def list_chat_sessions(user_id: int) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, title, created_at, updated_at,
                   (SELECT COUNT(*) FROM chat_messages m WHERE m.session_id = s.id) AS message_count
            FROM chat_sessions s
            WHERE user_id = ?
            ORDER BY updated_at DESC
            """,
            (user_id,),
        ).fetchall()
    return [
        {
            "session_id": row["id"],
            "title": row["title"],
            "message_count": int(row["message_count"]),
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def set_session_title(user_id: int, session_id: str, title: str) -> None:
    get_chat_session(user_id, session_id)
    with _connect() as connection:
        connection.execute(
            "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (title, _now(), session_id, user_id),
        )
        connection.commit()


def delete_chat_session(user_id: int, session_id: str) -> None:
    get_chat_session(user_id, session_id)
    with _connect() as connection:
        connection.execute(
            "DELETE FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )
        connection.commit()


def clear_chat_history(user_id: int, session_id: str) -> None:
    get_chat_session(user_id, session_id)
    with _connect() as connection:
        connection.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        connection.execute(
            "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
            (_now(), session_id),
        )
        connection.commit()


def get_messages(session_id: str) -> list[BaseMessage]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    messages: list[BaseMessage] = []
    for row in rows:
        if row["role"] == "human":
            messages.append(HumanMessage(content=row["content"]))
        elif row["role"] == "ai":
            messages.append(AIMessage(content=row["content"]))
    return messages


def append_messages(session_id: str, messages: Iterable[BaseMessage]) -> None:
    items = list(messages)
    if not items:
        return
    with _connect() as connection:
        for message in items:
            if isinstance(message, HumanMessage):
                role = "human"
            elif isinstance(message, AIMessage):
                role = "ai"
            else:
                role = "system"
            content = message.content
            if isinstance(content, list):
                content = "".join(
                    item.get("text", "") if isinstance(item, dict) else str(item)
                    for item in content
                )
            connection.execute(
                "INSERT INTO chat_messages(session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, str(content), _now()),
            )
        connection.execute(
            "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
            (_now(), session_id),
        )
        connection.commit()


def migrate_legacy_history() -> None:
    legacy_dir = Path(config.PROJECT_ROOT) / "chat_history"
    if not legacy_dir.exists():
        return
    with _connect() as connection:
        admin = connection.execute(
            "SELECT id FROM users WHERE username = 'admin'"
        ).fetchone()
        if admin is None:
            return
        admin_id = int(admin["id"])
        title_path = legacy_dir / ".session_titles.json"
        try:
            titles = __import__("json").loads(title_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError, OSError):
            titles = {}
        for path in legacy_dir.iterdir():
            if not path.is_file() or path.name.startswith("."):
                continue
            existing = connection.execute(
                "SELECT 1 FROM chat_sessions WHERE id = ?", (path.name,)
            ).fetchone()
            if existing:
                continue
            try:
                raw_messages = __import__("json").loads(path.read_text(encoding="utf-8"))
            except (FileNotFoundError, ValueError, OSError):
                continue
            now = _now()
            title = str(titles.get(path.name) or "历史对话").strip()[:80] or "历史对话"
            connection.execute(
                "INSERT INTO chat_sessions(id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (path.name, admin_id, title, now, now),
            )
            for raw in raw_messages if isinstance(raw_messages, list) else []:
                data = raw.get("data", {}) if isinstance(raw, dict) else {}
                role = data.get("type", "ai")
                if role not in {"human", "ai"}:
                    continue
                content = data.get("content", "")
                if isinstance(content, list):
                    content = "".join(str(item) for item in content)
                connection.execute(
                    "INSERT INTO chat_messages(session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                    (path.name, role, str(content), now),
                )
        connection.commit()


class SqliteChatMessageHistory(BaseChatMessageHistory):
    def __init__(self, session_id: str):
        self.session_id = session_id

    @property
    def messages(self) -> list[BaseMessage]:
        return get_messages(self.session_id)

    def add_messages(self, messages: Iterable[BaseMessage]) -> None:
        append_messages(self.session_id, messages)

    def clear(self) -> None:
        with _connect() as connection:
            connection.execute("DELETE FROM chat_messages WHERE session_id = ?", (self.session_id,))
            connection.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
                (_now(), self.session_id),
            )
            connection.commit()
