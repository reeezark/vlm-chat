"""
会话管理模块
实现多轮对话历史管理、上下文维护、SQLite 持久化存储和多会话管理（P0-2）。

设计：内存中维护 self.sessions 字典以复用既有逻辑，所有变更通过 SQLite 落库，
避免旧方案"每条消息全量重写大 JSON"的性能问题，并支撑并发与水平扩展的演进。
"""
import uuid
import time
import os
import json
import base64
import sqlite3
import threading
from datetime import datetime
from typing import Optional
from .config import MAX_HISTORY_LENGTH, SESSION_TIMEOUT, DEFAULT_SYSTEM_PROMPT, DEFAULT_USER_ID
from .logger import get_chat_logger

# 获取日志器
logger = get_chat_logger()

# 持久化存储目录（保留该名称以兼容既有测试的 monkeypatch）
HISTORY_STORAGE_DIR: str = "data/sessions"


class ChatManager:
    """会话管理器（SQLite 持久化）"""

    def __init__(self) -> None:
        """初始化会话管理器"""
        self.sessions: dict = {}
        self.current_session_id: Optional[str] = None
        self._lock = threading.Lock()

        # 确保存储目录存在；DB 文件位于该目录下
        os.makedirs(HISTORY_STORAGE_DIR, exist_ok=True)
        self.db_path: str = os.path.join(HISTORY_STORAGE_DIR, "sessions.db")
        self._init_db()

        # 加载已有的会话
        self.load_all_sessions()
        logger.info(f"会话管理器初始化完成，加载 {len(self.sessions)} 个会话")

    # ── 数据库底层 ────────────────────────────────────────────────
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """创建表结构（幂等）"""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id   TEXT PRIMARY KEY,
                    name         TEXT,
                    current_image TEXT,
                    system_prompt TEXT,
                    provider     TEXT,
                    model        TEXT,
                    user_id      TEXT,
                    created_at   REAL,
                    last_active  REAL
                )
                """
            )
            self._ensure_column(conn, "sessions", "user_id", "TEXT")
            conn.execute("UPDATE sessions SET user_id = ? WHERE user_id IS NULL OR user_id = ''", (DEFAULT_USER_ID,))
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT,
                    role        TEXT,
                    text        TEXT,
                    content     TEXT,
                    image       TEXT,
                    timestamp   REAL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id    TEXT PRIMARY KEY,
                    username   TEXT UNIQUE,
                    role       TEXT,
                    created_at REAL,
                    last_seen  REAL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id    TEXT,
                    user_id       TEXT,
                    session_id    TEXT,
                    action        TEXT,
                    resource_type TEXT,
                    resource_id   TEXT,
                    provider      TEXT,
                    model         TEXT,
                    success       INTEGER,
                    error_code    TEXT,
                    detail        TEXT,
                    created_at    REAL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_logs_session ON audit_logs(session_id, created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action, created_at)"
            )

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    # ── 会话 CRUD ────────────────────────────────────────────────
    def create_session(
        self,
        session_id: Optional[str] = None,
        name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """创建新会话"""
        user_id = user_id or DEFAULT_USER_ID
        if session_id is None:
            session_id = uuid.uuid4().hex

        if name is None:
            name = f"对话 {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        now = time.time()
        self.sessions[session_id] = {
            'session_id': session_id,
            'name': name,
            'history': [],
            'current_image': None,
            'current_image_thumbnail': None,
            'system_prompt': system_prompt or DEFAULT_SYSTEM_PROMPT,
            'provider': None,
            'model': None,
            'user_id': user_id,
            'created_at': now,
            'last_active': now
        }

        self.current_session_id = session_id
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO sessions
                   (session_id, name, current_image, system_prompt, provider, model, user_id, created_at, last_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, name, None, self.sessions[session_id]['system_prompt'], None, None, user_id, now, now),
            )
        self.add_audit_log(
            action="create_session",
            session_id=session_id,
            resource_type="session",
            resource_id=session_id,
            user_id=user_id,
        )
        logger.info(f"创建新会话: {session_id} ({name})")
        return session_id

    def get_session(self, session_id: str, user_id: Optional[str] = None) -> Optional[dict]:
        """获取会话"""
        session = self.sessions.get(session_id)
        if session and user_id and session.get("user_id") != user_id:
            return None
        return session

    def get_current_session(self) -> Optional[dict]:
        """获取当前活跃会话"""
        if self.current_session_id:
            return self.get_session(self.current_session_id)
        return None

    def set_current_session(self, session_id: str) -> bool:
        """设置当前会话"""
        if session_id in self.sessions:
            self.current_session_id = session_id
            logger.info(f"切换到会话: {session_id}")
            return True
        logger.warning(f"会话不存在: {session_id}")
        return False

    def get_all_sessions(self, user_id: Optional[str] = None) -> list[dict]:
        """获取所有会话列表"""
        session_list: list[dict] = []
        for session_id, session in self.sessions.items():
            if user_id and session.get('user_id') != user_id:
                continue
            session_list.append({
                'session_id': session_id,
                'name': session.get('name', '未命名'),
                'user_id': session.get('user_id'),
                'created_at': session.get('created_at'),
                'last_active': session.get('last_active'),
                'message_count': len(session.get('history', [])) // 2
            })
        session_list.sort(key=lambda x: x['last_active'], reverse=True)
        return session_list

    def delete_session(self, session_id: str, user_id: Optional[str] = None) -> bool:
        """删除会话"""
        session = self.get_session(session_id, user_id=user_id)
        if session:
            del self.sessions[session_id]
            with self._connect() as conn:
                conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            if self.current_session_id == session_id:
                candidates = [
                    sid for sid, item in self.sessions.items()
                    if not user_id or item.get('user_id') == user_id
                ]
                if candidates:
                    latest_session: str = max(candidates, key=lambda k: self.sessions[k]['last_active'])
                    self.current_session_id = latest_session
                else:
                    self.current_session_id = None
            self.add_audit_log(
                action="delete_session",
                session_id=session_id,
                resource_type="session",
                resource_id=session_id,
                user_id=session.get("user_id"),
            )
            logger.info(f"删除会话: {session_id}")
            return True
        logger.warning(f"会话不存在: {session_id}")
        return False

    def rename_session(self, session_id: str, new_name: str) -> bool:
        """重命名会话"""
        session: Optional[dict] = self.get_session(session_id)
        if session:
            session['name'] = new_name
            self._update_session_row(session_id)
            logger.info(f"重命名会话: {session_id} -> {new_name}")
            return True
        logger.warning(f"会话不存在: {session_id}")
        return False

    def set_system_prompt(self, session_id: str, system_prompt: str) -> bool:
        """设置会话的 System Prompt（P0-4）"""
        session: Optional[dict] = self.get_session(session_id)
        if session:
            session['system_prompt'] = system_prompt
            self._update_session_row(session_id)
            logger.info(f"更新会话 System Prompt: {session_id}")
            return True
        return False

    def get_system_prompt(self, session_id: Optional[str] = None) -> str:
        """获取会话的 System Prompt"""
        if session_id is None:
            session_id = self.current_session_id
        session: Optional[dict] = self.get_session(session_id)
        return (session.get('system_prompt') if session else None) or DEFAULT_SYSTEM_PROMPT

    def set_model(self, session_id: str, provider: Optional[str], model: Optional[str]) -> bool:
        """设置会话使用的 Provider / 模型（P0-3）"""
        session: Optional[dict] = self.get_session(session_id)
        if session:
            session['provider'] = provider
            session['model'] = model
            self._update_session_row(session_id)
            logger.info(f"更新会话模型: {session_id} -> {provider}/{model}")
            return True
        return False

    def create_image_thumbnail(self, image_path: str) -> Optional[str]:
        """创建压缩后的图片缩略图（base64 data URL，仅用于内存内展示，不持久化）"""
        try:
            from PIL import Image
            from io import BytesIO
            with Image.open(image_path) as img:
                img = img.convert("RGB")
                img.thumbnail((200, 200))
                buffer = BytesIO()
                img.save(buffer, format="JPEG", quality=70)
            return f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"
        except Exception as e:
            logger.error(f"创建缩略图失败: {str(e)}")
            return None

    def add_message(self, session_id: str, role: str, content: Optional[str], image_path=None) -> bool:
        """向会话添加消息

        参数:
            image_path: 单个图片路径，或多个图片路径的列表（P1-5 多图）
        """
        session: Optional[dict] = self.get_session(session_id)
        if not session:
            logger.warning(f"会话不存在: {session_id}")
            return False

        ts = time.time()
        message: dict = {'role': role, 'timestamp': ts}
        if role == 'user':
            if image_path:
                # 统一为列表内部表示，单图时退化为单元素
                images = image_path if isinstance(image_path, list) else [image_path]
                images = [p for p in images if p]
                if images:
                    message['image'] = images if len(images) > 1 else images[0]
                    first = images[0]
                    message['image_thumbnail'] = self.create_image_thumbnail(first)
                    session['current_image'] = message['image']
                    session['current_image_thumbnail'] = message['image_thumbnail']
            message['text'] = content
        else:
            message['content'] = content

        session['history'].append(message)
        session['last_active'] = ts

        # 持久化单条消息（增量写入，避免全量重写）。多图以 JSON 字符串存储。
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO messages (session_id, role, text, content, image, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, role, message.get('text'), message.get('content'),
                 self._encode_image(message.get('image')), ts),
            )
            conn.execute(
                "UPDATE sessions SET last_active = ?, current_image = ? WHERE session_id = ?",
                (ts, self._encode_image(session.get('current_image')), session_id),
            )

        # 内存中按最大长度截断（DB 保留完整历史）
        if len(session['history']) > MAX_HISTORY_LENGTH * 2:
            session['history'] = session['history'][-MAX_HISTORY_LENGTH * 2:]

        self.add_audit_log(
            action="add_message",
            session_id=session_id,
            resource_type="message",
            resource_id=role,
            user_id=session.get('user_id'),
            provider=session.get('provider'),
            model=session.get('model'),
            detail=json.dumps({"role": role, "has_image": bool(image_path)}, ensure_ascii=False),
        )
        logger.debug(f"添加消息到会话 {session_id}: {role}")
        return True

    @staticmethod
    def _encode_image(image) -> Optional[str]:
        """将 image 字段（单图字符串或多图列表）编码为 DB 存储字符串"""
        if not image:
            return None
        if isinstance(image, list):
            return json.dumps(image, ensure_ascii=False)
        return image

    @staticmethod
    def _decode_image(value):
        """将 DB 中的 image 字段解码为单图字符串或多图列表"""
        if not value:
            return None
        if isinstance(value, str) and value.startswith('['):
            try:
                decoded = json.loads(value)
                if isinstance(decoded, list):
                    return decoded if len(decoded) > 1 else (decoded[0] if decoded else None)
            except json.JSONDecodeError:
                return value
        return value

    def update_current_image(self, session_id: str, image_path: str) -> bool:
        """更新当前会话的图片（重新上传）"""
        session: Optional[dict] = self.get_session(session_id)
        if session:
            session['current_image'] = image_path
            session['current_image_thumbnail'] = self.create_image_thumbnail(image_path)
            session['last_active'] = time.time()
            self._update_session_row(session_id)
            logger.info(f"更新会话图片: {session_id}")
            return True
        logger.warning(f"会话不存在: {session_id}")
        return False

    def get_history(self, session_id: str, format_for_api: bool = True) -> list[dict]:
        """获取对话历史"""
        session: Optional[dict] = self.get_session(session_id)
        if not session:
            logger.warning(f"会话不存在: {session_id}")
            return []

        if format_for_api:
            history: list[dict] = []
            for msg in session['history']:
                if msg['role'] == 'user':
                    history.append({'role': 'user', 'image': msg.get('image'), 'text': msg.get('text')})
                else:
                    history.append({'role': 'assistant', 'content': msg.get('content')})
            return history
        return session['history']

    def get_current_image(self, session_id: Optional[str] = None) -> Optional[str]:
        """获取当前会话的图片"""
        if session_id is None:
            session_id = self.current_session_id
        session: Optional[dict] = self.get_session(session_id)
        return session.get('current_image') if session else None

    def get_current_image_thumbnail(self, session_id: Optional[str] = None) -> Optional[str]:
        """获取当前会话的图片缩略图"""
        if session_id is None:
            session_id = self.current_session_id
        session: Optional[dict] = self.get_session(session_id)
        return session.get('current_image_thumbnail') if session else None

    def pop_last_exchange(self, session_id: str) -> Optional[dict]:
        """
        移除并返回最近一轮用户提问（含其后助手回答），用于"重新生成"（P1-7）。

        返回:
            最近一条 user 消息的内存表示（含 text/image），无则返回 None
        """
        session: Optional[dict] = self.get_session(session_id)
        if not session or not session['history']:
            return None

        history = session['history']
        # 若末条是 assistant，连同其前的 user 一起回退
        last_user: Optional[dict] = None
        removed = 0
        if history and history[-1]['role'] == 'assistant':
            history.pop()
            removed += 1
        if history and history[-1]['role'] == 'user':
            last_user = history.pop()
            removed += 1

        if removed:
            # 从 DB 删除对应的最近 N 行
            with self._connect() as conn:
                ids = conn.execute(
                    "SELECT id FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                    (session_id, removed),
                ).fetchall()
                for r in ids:
                    conn.execute("DELETE FROM messages WHERE id = ?", (r['id'],))
            session['last_active'] = time.time()
        return last_user

    def clear_history(self, session_id: Optional[str] = None) -> bool:
        """清空对话历史"""
        if session_id is None:
            session_id = self.current_session_id
        session: Optional[dict] = self.get_session(session_id)
        if not session:
            logger.warning(f"会话不存在: {session_id}")
            return False
        session['history'] = []
        session['current_image'] = None
        session['current_image_thumbnail'] = None
        session['last_active'] = time.time()
        with self._connect() as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute(
                "UPDATE sessions SET last_active = ?, current_image = NULL WHERE session_id = ?",
                (session['last_active'], session_id),
            )
        self.add_audit_log(
            action="clear_history",
            session_id=session_id,
            resource_type="session",
            resource_id=session_id,
            user_id=session.get('user_id'),
        )
        logger.info(f"清空会话历史: {session_id}")
        return True

    # ── 用户与审计 ────────────────────────────────────────────────
    def upsert_user(self, username: str, role: str = "user", user_id: Optional[str] = None) -> str:
        """创建或更新基础用户记录，为后续 RBAC / 配额 / 审计做数据模型准备"""
        user_id = user_id or uuid.uuid5(uuid.NAMESPACE_DNS, username).hex
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO users (user_id, username, role, created_at, last_seen)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(username) DO UPDATE SET role = excluded.role, last_seen = excluded.last_seen""",
                (user_id, username, role, now, now),
            )
            row = conn.execute("SELECT user_id FROM users WHERE username = ?", (username,)).fetchone()
        return row["user_id"] if row else user_id

    def add_audit_log(
        self,
        action: str,
        session_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        success: bool = True,
        error_code: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        """记录关键操作审计日志；仅保存元信息，避免落敏感内容"""
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO audit_logs
                       (request_id, user_id, session_id, action, resource_type, resource_id,
                        provider, model, success, error_code, detail, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        request_id, user_id, session_id, action, resource_type, resource_id,
                        provider, model, 1 if success else 0, error_code, detail, time.time(),
                    ),
                )
        except Exception as e:
            logger.warning(f"写入审计日志失败: {e}")

    def get_audit_logs(self, limit: int = 100, session_id: Optional[str] = None) -> list[dict]:
        """读取最近审计日志，供排障和测试使用"""
        with self._connect() as conn:
            if session_id:
                rows = conn.execute(
                    "SELECT * FROM audit_logs WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                    (session_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def _update_session_row(self, session_id: str) -> None:
        """将会话元数据写回数据库"""
        session = self.get_session(session_id)
        if not session:
            return
        with self._connect() as conn:
            conn.execute(
                """UPDATE sessions
                   SET name = ?, current_image = ?, system_prompt = ?, provider = ?, model = ?, user_id = ?, last_active = ?
                   WHERE session_id = ?""",
                (session['name'], self._encode_image(session.get('current_image')), session.get('system_prompt'),
                 session.get('provider'), session.get('model'), session.get('user_id', DEFAULT_USER_ID),
                 session['last_active'], session_id),
            )

    def save_session(self, session_id: str) -> None:
        """保存会话元数据到数据库（消息为增量写入，此处仅同步元信息）"""
        if self.get_session(session_id):
            self._update_session_row(session_id)
            logger.debug(f"保存会话: {session_id}")

    def load_all_sessions(self) -> None:
        """从数据库加载所有会话"""
        try:
            with self._connect() as conn:
                rows = conn.execute("SELECT * FROM sessions").fetchall()
                for row in rows:
                    session_id = row['session_id']
                    msg_rows = conn.execute(
                        "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC",
                        (session_id,),
                    ).fetchall()
                    history: list[dict] = []
                    for m in msg_rows:
                        if m['role'] == 'user':
                            entry: dict = {'role': 'user', 'text': m['text'], 'timestamp': m['timestamp']}
                            decoded_img = self._decode_image(m['image'])
                            if decoded_img:
                                entry['image'] = decoded_img
                                first = decoded_img[0] if isinstance(decoded_img, list) else decoded_img
                                if first and os.path.exists(first):
                                    entry['image_thumbnail'] = self.create_image_thumbnail(first)
                            history.append(entry)
                        else:
                            history.append({'role': 'assistant', 'content': m['content'], 'timestamp': m['timestamp']})
                    # 内存只保留最近 N 轮
                    if len(history) > MAX_HISTORY_LENGTH * 2:
                        history = history[-MAX_HISTORY_LENGTH * 2:]

                    current_image = self._decode_image(row['current_image'])
                    thumb = None
                    _first_cur = current_image[0] if isinstance(current_image, list) else current_image
                    if _first_cur and os.path.exists(_first_cur):
                        thumb = self.create_image_thumbnail(_first_cur)

                    self.sessions[session_id] = {
                        'session_id': session_id,
                        'name': row['name'],
                        'history': history,
                        'current_image': current_image,
                        'current_image_thumbnail': thumb,
                        'system_prompt': row['system_prompt'] or DEFAULT_SYSTEM_PROMPT,
                        'provider': row['provider'],
                        'model': row['model'],
                        'user_id': row['user_id'] or DEFAULT_USER_ID,
                        'created_at': row['created_at'],
                        'last_active': row['last_active'],
                    }

            if len(self.sessions) > 0:
                latest_session: str = max(self.sessions.keys(), key=lambda k: self.sessions[k]['last_active'])
                self.current_session_id = latest_session
            logger.info(f"加载会话完成: {len(self.sessions)} 个")
        except Exception as e:
            logger.error(f"加载会话失败: {str(e)}")

    def cleanup_expired_sessions(self) -> int:
        """清理过期会话"""
        current_time: float = time.time()
        expired_sessions: list[str] = [sid for sid, s in self.sessions.items() if current_time - s['last_active'] > SESSION_TIMEOUT]
        for sid in expired_sessions:
            self.delete_session(sid)
        logger.info(f"清理过期会话: {len(expired_sessions)} 个")
        return len(expired_sessions)

    def get_session_count(self) -> int:
        """获取当前活跃会话数量"""
        return len(self.sessions)

    def format_for_chatbot(self, session_id: Optional[str] = None) -> list[dict]:
        """格式化历史记录为Gradio Chatbot格式（支持图片内联显示）"""
        if session_id is None:
            session_id = self.current_session_id
        session: Optional[dict] = self.get_session(session_id)
        if not session:
            return []

        chatbot_history: list[dict] = []
        history: list[dict] = session['history']
        i: int = 0
        while i < len(history):
            if history[i]['role'] == 'user':
                user_text: str = history[i].get('text', '')
                # Gradio 6.x 需要文件路径，不支持 base64；多图时逐张渲染
                user_image = history[i].get('image')
                image_list: list[str] = []
                if isinstance(user_image, list):
                    image_list = [p for p in user_image if p]
                elif user_image:
                    image_list = [user_image]

                # 构建用户消息：图片+文本（Gradio 6.x 格式）
                if image_list:
                    user_content: list = [{"path": p} for p in image_list]
                    if user_text:
                        user_content.append(user_text)
                else:
                    user_content = user_text

                if i + 1 < len(history) and history[i + 1]['role'] == 'assistant':
                    assistant_msg: str = history[i + 1].get('content', '')
                    chatbot_history.append({"role": "user", "content": user_content})
                    chatbot_history.append({"role": "assistant", "content": assistant_msg})
                    i += 2
                else:
                    chatbot_history.append({"role": "user", "content": user_content})
                    i += 1
            else:
                i += 1
        return chatbot_history
