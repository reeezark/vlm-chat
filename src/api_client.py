"""
API客户端封装
实现OpenAI兼容接口调用Qwen-VL-Plus模型
"""
import os
import time
import base64
from typing import Optional
from openai import OpenAI
from .config import DASHSCOPE_API_KEY, BASE_URL, MODEL_NAME, TEMPERATURE, MAX_TOKENS, TOP_P
from .logger import get_api_logger

# 获取日志器
logger = get_api_logger()


class VLMAPIClient:
    """视觉语言模型API客户端"""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None) -> None:
        """
        初始化API客户端

        参数:
            api_key: DashScope API密钥，如果为None则从环境变量获取
            model_name: 模型名称，如果为None则使用配置中的默认模型
        """
        self.api_key: str = api_key or DASHSCOPE_API_KEY
        self.model_name: str = model_name or MODEL_NAME

        if not self.api_key:
            logger.error("API密钥未设置")
            raise ValueError("API密钥未设置！请设置DASHSCOPE_API_KEY环境变量或在初始化时提供api_key参数")

        self.client: OpenAI = OpenAI(
            api_key=self.api_key,
            base_url=BASE_URL
        )
        logger.info(f"API客户端初始化完成，模型: {self.model_name}")

    def encode_image_to_base64(self, image_path: str) -> str:
        """
        将本地图片转换为base64编码格式

        参数:
            image_path: 本地图片路径

        返回:
            base64_url: base64编码的图片URL（格式：data:image/jpeg;base64,...）
        """
        # 获取图片格式
        ext: str = os.path.splitext(image_path)[1].lower()
        if ext in ['.jpg', '.jpeg']:
            mime_type: str = 'image/jpeg'
        elif ext == '.png':
            mime_type = 'image/png'
        elif ext == '.webp':
            mime_type = 'image/webp'
        else:
            mime_type = 'image/jpeg'  # 默认

        # 读取图片并编码为base64
        with open(image_path, 'rb') as f:
            image_data: bytes = f.read()

        base64_data: str = base64.b64encode(image_data).decode('utf-8')

        logger.debug(f"图片编码完成: {image_path} -> {mime_type}")
        # 返回data URL格式
        return f"data:{mime_type};base64,{base64_data}"

    def build_messages(
        self,
        image_path: Optional[str],
        question: Optional[str],
        history: Optional[list[dict]] = None
    ) -> list[dict]:
        """
        构建API调用的消息格式

        参数:
            image_path: 图片路径（本地文件路径或URL）
            question: 用户问题
            history: 对话历史（可选）

        返回:
            messages: 符合OpenAI格式的消息列表
        """
        messages: list[dict] = []

        # 添加对话历史（如果有）
        if history:
            for msg in history:
                if msg['role'] == 'user':
                    # 用户历史消息
                    has_image: bool = msg.get('image') is not None
                    has_text: bool = msg.get('text') is not None

                    if has_image:
                        # 有图片：content必须是列表格式
                        user_content: list[dict] = []
                        # 添加图片（转换为base64）
                        img_path: str = msg['image']
                        if os.path.exists(img_path):
                            image_url: str = self.encode_image_to_base64(img_path)
                        else:
                            image_url = img_path  # 已经是URL
                        user_content.append({
                            "type": "image_url",
                            "image_url": {"url": image_url}
                        })
                        # 添加文本（如果有）
                        if has_text and msg['text']:
                            user_content.append({
                                "type": "text",
                                "text": msg['text']
                            })
                        messages.append({"role": "user", "content": user_content})
                    elif has_text and msg['text']:
                        # 无图片但有文本：content是字符串格式
                        messages.append({"role": "user", "content": msg['text']})
                elif msg['role'] == 'assistant':
                    # 助手历史消息：content必须是字符串
                    if msg.get('content'):
                        messages.append({"role": "assistant", "content": msg['content']})

        # 构建当前用户消息
        if image_path:
            # 有图片：content必须是列表格式
            current_content: list[dict] = []

            # 处理图片路径：本地文件转base64
            if os.path.exists(image_path):
                image_url = self.encode_image_to_base64(image_path)
            else:
                image_url = image_path  # 已经是URL

            current_content.append({
                "type": "image_url",
                "image_url": {"url": image_url}
            })

            # 添加文本问题
            if question:
                current_content.append({
                    "type": "text",
                    "text": question
                })

            messages.append({"role": "user", "content": current_content})
        elif question:
            # 无图片只有文本：content是字符串格式
            messages.append({"role": "user", "content": question})

        logger.debug(f"构建消息完成，消息数: {len(messages)}")
        return messages

    def call_api(
        self,
        image_path: Optional[str],
        question: Optional[str],
        history: Optional[list[dict]] = None,
        max_retries: int = 3
    ) -> str:
        """
        调用视觉语言模型API

        参数:
            image_path: 图片路径
            question: 用户问题
            history: 对话历史（可选）
            max_retries: 最大重试次数

        返回:
            response_text: 模型的回答文本
        """
        messages: list[dict] = self.build_messages(image_path, question, history)

        for attempt in range(max_retries):
            try:
                logger.info(f"调用API (尝试 {attempt + 1}/{max_retries})")
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=TEMPERATURE,
                    max_tokens=MAX_TOKENS,
                    top_p=TOP_P
                )

                result: str = response.choices[0].message.content
                logger.info(f"API调用成功，响应长度: {len(result)}")
                return result

            except Exception as e:
                logger.warning(f"API调用失败（尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # 等待2秒后重试
                else:
                    logger.error(f"API调用失败，已达到最大重试次数: {str(e)}")
                    raise Exception(f"API调用失败，已达到最大重试次数: {str(e)}")

    def test_connection(self) -> tuple[bool, str]:
        """
        测试API连接

        返回:
            success: 是否成功连接
            message: 测试结果消息
        """
        try:
            logger.info("测试API连接...")
            # 发送一个简单的测试请求（纯文本，content是字符串）
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": "你好"}],
                max_tokens=10
            )
            logger.info("API连接测试成功")
            return True, "API连接测试成功！"
        except Exception as e:
            logger.error(f"API连接测试失败: {str(e)}")
            return False, f"API连接测试失败: {str(e)}"
