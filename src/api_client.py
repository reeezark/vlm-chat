"""
API客户端封装
实现OpenAI兼容接口调用视觉语言模型，支持：
- 多 Provider 切换（P0-3）
- System Prompt（P0-4）
- 流式输出（P0-1）
- 工具调用 / 联网搜索（P0-4）
"""
import os
import time
import base64
from collections import OrderedDict
from typing import Optional, Iterator

from openai import OpenAI

from .config import (
    DASHSCOPE_API_KEY, BASE_URL, MODEL_NAME, TEMPERATURE, MAX_TOKENS, TOP_P,
    PROVIDERS, DEFAULT_PROVIDER, ENABLE_TOOLS, IMAGE_BASE64_CACHE_SIZE,
)
from .tools import TOOLS_SPEC, execute_tool_call
from .logger import get_api_logger

# 获取日志器
logger = get_api_logger()


def resolve_provider(provider: Optional[str]) -> tuple[str, str, str]:
    """
    解析 Provider 配置，返回 (base_url, api_key, default_model)。

    参数:
        provider: Provider 标识（PROVIDERS 的 key）；为空时使用默认 Provider
    """
    provider = provider or DEFAULT_PROVIDER
    conf = PROVIDERS.get(provider)
    if not conf:
        # 回退到兼容旧逻辑的 DashScope 默认
        return BASE_URL, DASHSCOPE_API_KEY, MODEL_NAME
    api_key = os.getenv(conf["api_key_env"], "")
    default_model = conf["models"][0] if conf.get("models") else MODEL_NAME
    return conf["base_url"], api_key, default_model


class VLMAPIClient:
    """视觉语言模型API客户端"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        provider: Optional[str] = None,
        allow_missing_key: bool = False,
    ) -> None:
        """
        初始化API客户端

        参数:
            api_key: API密钥，如果为None则按 Provider 从环境变量获取
            model_name: 模型名称，如果为None则使用 Provider 默认模型
            provider: Provider 标识（dashscope/openai/openrouter/ollama）
        """
        self.provider: str = provider or DEFAULT_PROVIDER
        base_url, resolved_key, default_model = resolve_provider(self.provider)

        # 兼容旧用法：未指定 provider 且未指定 key 时，回退到 DASHSCOPE_API_KEY
        self.api_key: str = api_key or resolved_key or DASHSCOPE_API_KEY
        self.model_name: str = model_name or default_model
        self.base_url: str = base_url
        self._image_cache: OrderedDict[tuple[str, float, int], str] = OrderedDict()

        if not self.api_key and self.provider != "ollama" and not allow_missing_key:
            logger.error("API密钥未设置")
            raise ValueError("API密钥未设置！请设置对应 Provider 的环境变量或在初始化时提供api_key参数")

        self.client: OpenAI = OpenAI(
            api_key=self.api_key or "ollama",  # Ollama 允许占位密钥
            base_url=self.base_url,
        )
        logger.info(f"API客户端初始化完成，provider: {self.provider}, 模型: {self.model_name}")

    def switch_model(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        """运行时切换 Provider / 模型（P0-3），支持前端自定义 OpenAI 兼容配置。"""
        if provider == "custom":
            if not base_url:
                raise ValueError("自定义 API 地址不能为空")
            if not model_name:
                raise ValueError("自定义模型名称不能为空")
            if not api_key:
                raise ValueError("自定义 API Key 不能为空")
            self.provider = "custom"
            self.base_url = base_url.rstrip("/")
            self.api_key = api_key
            self.model_name = model_name
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        elif provider and provider != self.provider:
            self.provider = provider
            base_url, resolved_key, default_model = resolve_provider(provider)
            self.base_url = base_url
            self.api_key = resolved_key
            self.model_name = model_name or default_model
            self.client = OpenAI(api_key=self.api_key or "ollama", base_url=self.base_url)
        elif model_name:
            self.model_name = model_name
        logger.info(f"切换模型: provider={self.provider}, model={self.model_name}")

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

        stat = os.stat(image_path)
        cache_key = (image_path, stat.st_mtime, stat.st_size)
        cached = self._image_cache.get(cache_key)
        if cached:
            self._image_cache.move_to_end(cache_key)
            return cached

        # 读取图片并编码为base64
        with open(image_path, 'rb') as f:
            image_data: bytes = f.read()

        base64_data: str = base64.b64encode(image_data).decode('utf-8')

        logger.debug(f"图片编码完成: {image_path} -> {mime_type}")
        # 返回data URL格式
        data_url = f"data:{mime_type};base64,{base64_data}"
        self._image_cache[cache_key] = data_url
        while len(self._image_cache) > IMAGE_BASE64_CACHE_SIZE:
            self._image_cache.popitem(last=False)
        return data_url

    def _image_blocks(self, images) -> list[dict]:
        """
        将单个或多个图片路径/URL 转为 OpenAI image_url 内容块列表（P1-5 多图）。

        参数:
            images: 单个路径/URL 字符串，或其列表
        """
        if not images:
            return []
        if isinstance(images, str):
            images = [images]
        blocks: list[dict] = []
        for img in images:
            if not img:
                continue
            if os.path.exists(img):
                url = self.encode_image_to_base64(img)
            else:
                url = img  # 已经是 URL
            blocks.append({"type": "image_url", "image_url": {"url": url}})
        return blocks

    def build_messages(
        self,
        image_path,
        question: Optional[str],
        history: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None,
    ) -> list[dict]:
        """
        构建API调用的消息格式

        参数:
            image_path: 图片路径（本地文件路径或URL），可为单个字符串或字符串列表（多图）
            question: 用户问题
            history: 对话历史（可选）
            system_prompt: 系统提示词（可选，P0-4）

        返回:
            messages: 符合OpenAI格式的消息列表
        """
        messages: list[dict] = []

        # 添加 system prompt（P0-4）
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 添加对话历史（如果有）
        if history:
            for msg in history:
                if msg['role'] == 'user':
                    # 用户历史消息（image 可为单个或列表）
                    img_blocks: list[dict] = self._image_blocks(msg.get('image'))
                    has_text: bool = bool(msg.get('text'))

                    if img_blocks:
                        # 有图片：content必须是列表格式
                        user_content: list[dict] = list(img_blocks)
                        if has_text:
                            user_content.append({"type": "text", "text": msg['text']})
                        messages.append({"role": "user", "content": user_content})
                    elif has_text:
                        # 无图片但有文本：content是字符串格式
                        messages.append({"role": "user", "content": msg['text']})
                elif msg['role'] == 'assistant':
                    # 助手历史消息：content必须是字符串
                    if msg.get('content'):
                        messages.append({"role": "assistant", "content": msg['content']})

        # 构建当前用户消息
        current_blocks: list[dict] = self._image_blocks(image_path)
        if current_blocks:
            # 有图片：content必须是列表格式
            current_content: list[dict] = list(current_blocks)
            # 添加文本问题
            if question:
                current_content.append({"type": "text", "text": question})
            messages.append({"role": "user", "content": current_content})
        elif question:
            # 无图片只有文本：content是字符串格式
            messages.append({"role": "user", "content": question})

        logger.debug(f"构建消息完成，消息数: {len(messages)}")
        return messages

    def _completion_kwargs(self, messages: list[dict], use_tools: bool) -> dict:
        """构造 chat.completions.create 的公共参数"""
        kwargs: dict = {
            "model": self.model_name,
            "messages": messages,
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            "top_p": TOP_P,
        }
        if use_tools and ENABLE_TOOLS:
            kwargs["tools"] = TOOLS_SPEC
            kwargs["tool_choice"] = "auto"
        return kwargs

    def call_api(
        self,
        image_path: Optional[str],
        question: Optional[str],
        history: Optional[list[dict]] = None,
        max_retries: int = 3,
        system_prompt: Optional[str] = None,
        use_tools: bool = False,
    ) -> str:
        """
        调用视觉语言模型API（非流式，含指数退避与工具调用）

        参数:
            image_path: 图片路径
            question: 用户问题
            history: 对话历史（可选）
            max_retries: 最大重试次数
            system_prompt: 系统提示词（可选）
            use_tools: 是否启用工具调用

        返回:
            response_text: 模型的回答文本
        """
        messages: list[dict] = self.build_messages(image_path, question, history, system_prompt)

        last_error: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                logger.info(f"调用API (尝试 {attempt + 1}/{max_retries})")
                response = self.client.chat.completions.create(
                    **self._completion_kwargs(messages, use_tools)
                )
                message = response.choices[0].message

                # 处理工具调用（P0-4）
                tool_calls = getattr(message, "tool_calls", None)
                if isinstance(tool_calls, (list, tuple)) and tool_calls:
                    messages.append(message.model_dump() if hasattr(message, "model_dump") else {
                        "role": "assistant", "content": message.content, "tool_calls": tool_calls,
                    })
                    for tc in tool_calls:
                        result = execute_tool_call(tc.function.name, tc.function.arguments)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result,
                        })
                    # 工具结果回灌后再请求一次最终回答
                    response = self.client.chat.completions.create(
                        **self._completion_kwargs(messages, use_tools=False)
                    )
                    message = response.choices[0].message

                result: str = message.content
                logger.info(f"API调用成功，响应长度: {len(result)}")
                return result

            except Exception as e:
                last_error = e
                if not self._is_retryable(e):
                    logger.error(f"API调用失败（不可重试错误）: {str(e)}")
                    raise Exception(f"API调用失败: {str(e)}")
                if attempt == max_retries - 1:
                    logger.error(f"API调用失败，已达到最大重试次数: {str(e)}")
                    raise Exception(f"API调用失败，已达到最大重试次数: {str(e)}")
                backoff = 2 ** attempt  # 指数退避: 1s, 2s, 4s...
                logger.warning(f"API调用失败（尝试 {attempt + 1}/{max_retries}），{backoff}s 后重试: {str(e)}")
                time.sleep(backoff)
        # 理论不可达
        raise Exception(f"API调用失败，已达到最大重试次数: {last_error}")

    def stream_api(
        self,
        image_path: Optional[str],
        question: Optional[str],
        history: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None,
        use_tools: bool = False,
    ) -> Iterator[str]:
        """
        流式调用视觉语言模型API（P0-1），逐步产出累积文本。

        说明：当模型决定调用工具时，先执行工具，再对最终回答进行流式输出。

        产出:
            累积的回答文本（每次 yield 当前已生成的完整文本）
        """
        messages: list[dict] = self.build_messages(image_path, question, history, system_prompt)

        # 工具调用需要先用非流式判断（工具调用与流式同时处理较复杂），
        # 若启用工具，先做一次非流式探测。
        if use_tools and ENABLE_TOOLS:
            probe = self.client.chat.completions.create(
                **self._completion_kwargs(messages, use_tools=True)
            )
            pmsg = probe.choices[0].message
            tool_calls = getattr(pmsg, "tool_calls", None)
            if isinstance(tool_calls, (list, tuple)) and tool_calls:
                messages.append(pmsg.model_dump() if hasattr(pmsg, "model_dump") else {
                    "role": "assistant", "content": pmsg.content, "tool_calls": tool_calls,
                })
                for tc in tool_calls:
                    result = execute_tool_call(tc.function.name, tc.function.arguments)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

        # 流式产出最终回答
        accumulated: str = ""
        stream = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            top_p=TOP_P,
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            piece = getattr(delta, "content", None)
            if piece:
                accumulated += piece
                yield accumulated
        logger.info(f"流式API调用完成，响应长度: {len(accumulated)}")

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

    @staticmethod
    def _is_retryable(error: Exception) -> bool:
        """判断异常是否值得重试：仅对网络/限流/服务端错误重试，鉴权/参数错误不重试"""
        status = getattr(error, "status_code", None)
        if status is None:
            status = getattr(error, "code", None)
        # 明确不可重试的客户端错误
        if isinstance(status, int) and status in (400, 401, 403, 404, 422):
            return False
        name = type(error).__name__.lower()
        if "authentication" in name or "permission" in name or "notfound" in name or "badrequest" in name:
            return False
        return True
