"""
API客户端测试模块
"""
import os
import pytest
from unittest.mock import patch, MagicMock, mock_open
from src.api_client import VLMAPIClient


@pytest.fixture
def client():
    """创建API客户端实例"""
    with patch("src.api_client.DASHSCOPE_API_KEY", "test-key"):
        return VLMAPIClient(api_key="test-key")


@pytest.fixture
def mock_client():
    """创建带mock的API客户端"""
    client = VLMAPIClient(api_key="test-key")
    client.client = MagicMock()
    return client


class TestInit:
    """测试初始化"""

    def test_init_uses_config_default(self):
        from src.config import DASHSCOPE_API_KEY
        client = VLMAPIClient()
        assert client.api_key == DASHSCOPE_API_KEY

    def test_init_with_param_key(self):
        client = VLMAPIClient(api_key="param-key")
        assert client.api_key == "param-key"

    def test_init_without_key(self):
        with patch("src.api_client.DASHSCOPE_API_KEY", ""):
            with pytest.raises(ValueError, match="API密钥未设置"):
                VLMAPIClient(api_key="")

    def test_custom_model(self):
        client = VLMAPIClient(api_key="test-key", model_name="custom-model")
        assert client.model_name == "custom-model"


class TestBuildMessages:
    """测试消息构建"""

    def test_text_only(self, client):
        messages = client.build_messages(None, "你好")
        assert len(messages) == 1
        assert messages[0]['role'] == "user"
        assert messages[0]['content'] == "你好"

    def test_image_with_text(self, client, tmp_path):
        image_path = tmp_path / "test.jpg"
        image_path.write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 100)
        messages = client.build_messages(str(image_path), "描述图片")
        assert len(messages) == 1
        assert isinstance(messages[0]['content'], list)
        assert messages[0]['content'][0]['type'] == "image_url"
        assert messages[0]['content'][1]['type'] == "text"

    def test_image_without_text(self, client, tmp_path):
        image_path = tmp_path / "test.jpg"
        image_path.write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 100)
        messages = client.build_messages(str(image_path), None)
        assert len(messages) == 1
        assert len(messages[0]['content']) == 1

    def test_with_history(self, client):
        history = [
            {"role": "user", "text": "你好"},
            {"role": "assistant", "content": "你好！"}
        ]
        messages = client.build_messages(None, "今天天气怎么样？", history=history)
        assert len(messages) == 3
        assert messages[0]['role'] == "user"
        assert messages[1]['role'] == "assistant"
        assert messages[2]['role'] == "user"

    def test_history_with_image(self, client, tmp_path):
        image_path = tmp_path / "test.jpg"
        image_path.write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 100)
        history = [
            {"role": "user", "image": str(image_path), "text": "描述这张图"},
            {"role": "assistant", "content": "这是一张测试图片"}
        ]
        messages = client.build_messages(None, "再看一次", history=history)
        assert len(messages) == 3
        assert isinstance(messages[0]['content'], list)

    def test_url_image(self, client):
        url = "https://example.com/image.jpg"
        messages = client.build_messages(url, "描述图片")
        assert messages[0]['content'][0]['image_url']['url'] == url


class TestEncodeImageToBase64:
    """测试Base64编码"""

    def test_encode_jpg(self, client, tmp_path):
        image_path = tmp_path / "test.jpg"
        image_path.write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 100)
        result = client.encode_image_to_base64(str(image_path))
        assert result.startswith("data:image/jpeg;base64,")

    def test_encode_png(self, client, tmp_path):
        image_path = tmp_path / "test.png"
        image_path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
        result = client.encode_image_to_base64(str(image_path))
        assert result.startswith("data:image/png;base64,")


class TestCallAPI:
    """测试API调用"""

    def test_call_success(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "测试回复"
        mock_client.client.chat.completions.create.return_value = mock_response

        result = mock_client.call_api(None, "你好")
        assert result == "测试回复"
        mock_client.client.chat.completions.create.assert_called_once()

    def test_call_retry_then_success(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "成功"
        mock_client.client.chat.completions.create.side_effect = [
            Exception("临时错误"),
            mock_response
        ]

        with patch("time.sleep"):  # 跳过等待
            result = mock_client.call_api(None, "你好", max_retries=3)
        assert result == "成功"

    def test_call_max_retries_exceeded(self, mock_client):
        mock_client.client.chat.completions.create.side_effect = Exception("持续错误")

        with patch("time.sleep"):
            with pytest.raises(Exception, match="已达到最大重试次数"):
                mock_client.call_api(None, "你好", max_retries=2)


class TestTestConnection:
    """测试连接测试"""

    def test_connection_success(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "你好"
        mock_client.client.chat.completions.create.return_value = mock_response

        success, msg = mock_client.test_connection()
        assert success is True
        assert "成功" in msg

    def test_connection_failure(self, mock_client):
        mock_client.client.chat.completions.create.side_effect = Exception("连接失败")

        success, msg = mock_client.test_connection()
        assert success is False
        assert "失败" in msg
