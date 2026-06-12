"""
会话管理模块
实现多轮对话历史管理、上下文维护、持久化存储和多会话管理
"""
import uuid
import time
import json
import os
import base64
from collections import defaultdict
from datetime import datetime
from typing import Optional
from .config import MAX_HISTORY_LENGTH, SESSION_TIMEOUT
from .logger import get_chat_logger

# 获取日志器
logger = get_chat_logger()

# 持久化存储目录
HISTORY_STORAGE_DIR: str = "data/sessions"


class ChatManager:
    """会话管理器"""

    def __init__(self) -> None:
        """初始化会话管理器"""
        self.sessions: dict = defaultdict(dict)
        self.current_session_id: Optional[str] = None

        # 确保存储目录存在
        os.makedirs(HISTORY_STORAGE_DIR, exist_ok=True)

        # 加载已有的会话
        self.load_all_sessions()
        logger.info(f"会话管理器初始化完成，加载 {len(self.sessions)} 个会话")

    def create_session(self, session_id: Optional[str] = None, name: Optional[str] = None) -> str:
        """创建新会话"""
        if session_id is None:
            session_id = uuid.uuid4().hex

        if name is None:
            name = f"对话 {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        self.sessions[session_id] = {
            'session_id': session_id,
            'name': name,
            'history': [],
            'current_image': None,
            'current_image_thumbnail': None,
            'created_at': time.time(),
            'last_active': time.time()
        }

        self.current_session_id = session_id
        self.save_session(session_id)
        logger.info(f"创建新会话: {session_id} ({name})")
        return session_id

    def get_session(self, session_id: str) -> Optional[dict]:
        """获取会话"""
        return self.sessions.get(session_id)

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

    def get_all_sessions(self) -> list[dict]:
        """获取所有会话列表"""
        session_list: list[dict] = []
        for session_id, session in self.sessions.items():
            session_list.append({
                'session_id': session_id,
                'name': session.get('name', '未命名'),
                'created_at': session.get('created_at'),
                'last_active': session.get('last_active'),
                'message_count': len(session.get('history', [])) // 2
            })
        session_list.sort(key=lambda x: x['last_active'], reverse=True)
        return session_list

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            session_file: str = os.path.join(HISTORY_STORAGE_DIR, f"{session_id}.json")
            if os.path.exists(session_file):
                os.remove(session_file)
            if self.current_session_id == session_id:
                if len(self.sessions) > 0:
                    latest_session: str = max(self.sessions.keys(),
                                         key=lambda k: self.sessions[k]['last_active'])
                    self.current_session_id = latest_session
                else:
                    self.current_session_id = None
            logger.info(f"删除会话: {session_id}")
            return True
        logger.warning(f"会话不存在: {session_id}")
        return False

    def rename_session(self, session_id: str, new_name: str) -> bool:
        """重命名会话"""
        session: Optional[dict] = self.get_session(session_id)
        if session:
            session['name'] = new_name
            self.save_session(session_id)
            logger.info(f"重命名会话: {session_id} -> {new_name}")
            return True
        logger.warning(f"会话不存在: {session_id}")
        return False

    def create_image_thumbnail(self, image_path: str) -> Optional[str]:
        """创建图片缩略图（base64格式）"""
        try:
            with open(image_path, 'rb') as f:
                image_data: bytes = f.read()
            ext: str = os.path.splitext(image_path)[1].lower()
            mime_type: str = 'image/jpeg' if ext in ['.jpg', '.jpeg'] else 'image/png' if ext == '.png' else 'image/webp' if ext == '.webp' else 'image/jpeg'
            return f"data:{mime_type};base64,{base64.b64encode(image_data).decode('utf-8')}"
        except Exception as e:
            logger.error(f"创建缩略图失败: {str(e)}")
            return None

    def add_message(self, session_id: str, role: str, content: Optional[str], image_path: Optional[str] = None) -> bool:
        """向会话添加消息"""
        session: Optional[dict] = self.get_session(session_id)
        if not session:
            logger.warning(f"会话不存在: {session_id}")
            return False

        message: dict = {'role': role, 'timestamp': time.time()}
        if role == 'user':
            if image_path:
                message['image'] = image_path
                message['image_thumbnail'] = self.create_image_thumbnail(image_path)
                session['current_image'] = image_path
                session['current_image_thumbnail'] = message['image_thumbnail']
            message['text'] = content
        else:
            message['content'] = content

        session['history'].append(message)
        if len(session['history']) > MAX_HISTORY_LENGTH * 2:
            session['history'] = session['history'][-MAX_HISTORY_LENGTH * 2:]

        session['last_active'] = time.time()
        self.save_session(session_id)
        logger.debug(f"添加消息到会话 {session_id}: {role}")
        return True

    def update_current_image(self, session_id: str, image_path: str) -> bool:
        """更新当前会话的图片（重新上传）"""
        session: Optional[dict] = self.get_session(session_id)
        if session:
            session['current_image'] = image_path
            session['current_image_thumbnail'] = self.create_image_thumbnail(image_path)
            session['last_active'] = time.time()
            self.save_session(session_id)
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
        self.save_session(session_id)
        logger.info(f"清空会话历史: {session_id}")
        return True

    def save_session(self, session_id: str) -> None:
        """保存会话到文件"""
        session: Optional[dict] = self.get_session(session_id)
        if session:
            session_file: str = os.path.join(HISTORY_STORAGE_DIR, f"{session_id}.json")
            try:
                session_data: dict = {
                    'session_id': session['session_id'],
                    'name': session['name'],
                    'history': session['history'],
                    'current_image': session['current_image'],
                    'created_at': session['created_at'],
                    'last_active': session['last_active']
                }
                with open(session_file, 'w', encoding='utf-8') as f:
                    json.dump(session_data, f, ensure_ascii=False, indent=2)
                logger.debug(f"保存会话: {session_id}")
            except Exception as e:
                logger.error(f"保存会话失败: {str(e)}")

    def load_all_sessions(self) -> None:
        """加载所有已保存的会话"""
        try:
            for filename in os.listdir(HISTORY_STORAGE_DIR):
                if filename.endswith('.json'):
                    session_file: str = os.path.join(HISTORY_STORAGE_DIR, filename)
                    try:
                        with open(session_file, 'r', encoding='utf-8') as f:
                            session_data: dict = json.load(f)
                            session_id: str = session_data['session_id']
                            for msg in session_data.get('history', []):
                                if msg.get('image') and os.path.exists(msg['image']):
                                    msg['image_thumbnail'] = self.create_image_thumbnail(msg['image'])
                            if session_data.get('current_image') and os.path.exists(session_data['current_image']):
                                session_data['current_image_thumbnail'] = self.create_image_thumbnail(session_data['current_image'])
                            else:
                                session_data['current_image_thumbnail'] = None
                            self.sessions[session_id] = session_data
                    except Exception as e:
                        logger.error(f"加载会话 {filename} 失败: {str(e)}")

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
                # Gradio 6.x 需要文件路径，不支持 base64
                user_image: Optional[str] = history[i].get('image')

                # 构建用户消息：图片+文本（Gradio 6.x 格式）
                if user_image and user_text:
                    user_content: list[dict] = [
                        {"path": user_image},
                        user_text
                    ]
                elif user_image:
                    user_content = [
                        {"path": user_image}
                    ]
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
