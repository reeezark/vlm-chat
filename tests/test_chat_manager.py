"""
会话管理器测试模块
"""
import os
import json
import time
import pytest
from src.chat_manager import ChatManager, HISTORY_STORAGE_DIR


@pytest.fixture
def manager(tmp_path, monkeypatch):
    """创建会话管理器实例（使用临时目录）"""
    test_dir = str(tmp_path / "sessions")
    monkeypatch.setattr("src.chat_manager.HISTORY_STORAGE_DIR", test_dir)
    os.makedirs(test_dir, exist_ok=True)
    return ChatManager()


@pytest.fixture
def session_id(manager):
    """创建一个测试会话并返回ID"""
    return manager.create_session(name="测试会话")


class TestCreateSession:
    """测试创建会话"""

    def test_create_with_name(self, manager):
        sid = manager.create_session(name="自定义名称")
        session = manager.get_session(sid)
        assert session is not None
        assert session['name'] == "自定义名称"
        assert session['history'] == []

    def test_create_with_id(self, manager):
        sid = manager.create_session(session_id="custom-id", name="测试")
        assert sid == "custom-id"
        assert manager.get_session("custom-id") is not None

    def test_create_auto_id(self, manager):
        sid = manager.create_session()
        assert len(sid) == 32  # uuid hex长度


class TestGetSession:
    """测试获取会话"""

    def test_get_existing(self, manager, session_id):
        session = manager.get_session(session_id)
        assert session is not None
        assert session['session_id'] == session_id

    def test_get_nonexistent(self, manager):
        session = manager.get_session("nonexistent")
        assert session is None

    def test_get_current(self, manager, session_id):
        current = manager.get_current_session()
        assert current is not None
        assert current['session_id'] == session_id

    def test_get_current_none(self, manager):
        manager.current_session_id = None
        assert manager.get_current_session() is None


class TestSetCurrentSession:
    """测试设置当前会话"""

    def test_set_existing(self, manager, session_id):
        new_sid = manager.create_session(name="另一个会话")
        result = manager.set_current_session(new_sid)
        assert result is True
        assert manager.current_session_id == new_sid

    def test_set_nonexistent(self, manager):
        result = manager.set_current_session("nonexistent")
        assert result is False


class TestGetAllSessions:
    """测试获取所有会话"""

    def test_list_sessions(self, manager):
        manager.create_session(name="会话1")
        manager.create_session(name="会话2")
        sessions = manager.get_all_sessions()
        assert len(sessions) == 2
        assert all('session_id' in s for s in sessions)
        assert all('name' in s for s in sessions)

    def test_sorted_by_last_active(self, manager):
        sid1 = manager.create_session(name="旧会话")
        time.sleep(0.01)
        sid2 = manager.create_session(name="新会话")
        sessions = manager.get_all_sessions()
        assert sessions[0]['name'] == "新会话"


class TestDeleteSession:
    """测试删除会话"""

    def test_delete_existing(self, manager, session_id):
        result = manager.delete_session(session_id)
        assert result is True
        assert manager.get_session(session_id) is None

    def test_delete_nonexistent(self, manager):
        result = manager.delete_session("nonexistent")
        assert result is False

    def test_delete_current_switches(self, manager):
        sid1 = manager.create_session(name="会话1")
        time.sleep(0.01)
        sid2 = manager.create_session(name="会话2")
        manager.delete_session(sid2)
        assert manager.current_session_id == sid1

    def test_delete_all_clears_current(self, manager, session_id):
        manager.delete_session(session_id)
        assert manager.current_session_id is None


class TestRenameSession:
    """测试重命名会话"""

    def test_rename_existing(self, manager, session_id):
        result = manager.rename_session(session_id, "新名称")
        assert result is True
        assert manager.get_session(session_id)['name'] == "新名称"

    def test_rename_nonexistent(self, manager):
        result = manager.rename_session("nonexistent", "新名称")
        assert result is False


class TestAddMessage:
    """测试添加消息"""

    def test_add_user_text(self, manager, session_id):
        result = manager.add_message(session_id, "user", "你好")
        assert result is True
        history = manager.get_history(session_id)
        assert len(history) == 1
        assert history[0]['role'] == "user"
        assert history[0]['text'] == "你好"

    def test_add_assistant_message(self, manager, session_id):
        manager.add_message(session_id, "user", "你好")
        result = manager.add_message(session_id, "assistant", "你好！有什么可以帮助你的？")
        assert result is True
        history = manager.get_history(session_id)
        assert len(history) == 2
        assert history[1]['role'] == "assistant"

    def test_add_to_nonexistent(self, manager):
        result = manager.add_message("nonexistent", "user", "你好")
        assert result is False

    def test_history_truncation(self, manager, session_id):
        # 添加超过最大长度的消息
        for i in range(25):
            manager.add_message(session_id, "user", f"消息{i}")
            manager.add_message(session_id, "assistant", f"回复{i}")
        history = manager.get_history(session_id, format_for_api=False)
        assert len(history) <= 20  # MAX_HISTORY_LENGTH * 2


class TestClearHistory:
    """测试清空历史"""

    def test_clear(self, manager, session_id):
        manager.add_message(session_id, "user", "你好")
        manager.add_message(session_id, "assistant", "你好！")
        result = manager.clear_history(session_id)
        assert result is True
        assert len(manager.get_history(session_id)) == 0

    def test_clear_nonexistent(self, manager):
        result = manager.clear_history("nonexistent")
        assert result is False


class TestGetSessionCount:
    """测试获取会话数量"""

    def test_count(self, manager):
        manager.create_session(name="会话1")
        manager.create_session(name="会话2")
        assert manager.get_session_count() == 2


class TestFormatForChatbot:
    """测试聊天机器人格式化"""

    def test_format_pairs(self, manager, session_id):
        manager.add_message(session_id, "user", "你好")
        manager.add_message(session_id, "assistant", "你好！")
        formatted = manager.format_for_chatbot(session_id)
        assert len(formatted) == 2
        assert formatted[0]['role'] == "user"
        assert formatted[1]['role'] == "assistant"

    def test_format_unpaired(self, manager, session_id):
        manager.add_message(session_id, "user", "你好")
        formatted = manager.format_for_chatbot(session_id)
        assert len(formatted) == 1
        assert formatted[0]['role'] == "user"

    def test_format_nonexistent(self, manager):
        formatted = manager.format_for_chatbot("nonexistent")
        assert formatted == []


class TestPersistence:
    """测试持久化"""

    def test_save_and_load(self, manager, session_id, tmp_path, monkeypatch):
        manager.add_message(session_id, "user", "测试消息")
        manager.add_message(session_id, "assistant", "测试回复")

        # 创建新的管理器实例（会从文件加载）
        new_manager = ChatManager()
        session = new_manager.get_session(session_id)
        assert session is not None
        assert len(session['history']) == 2
