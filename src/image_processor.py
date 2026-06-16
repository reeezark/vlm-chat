"""
图片处理模块
实现图片格式验证、大小检查、临时存储等功能
"""
import os
import shutil
import uuid
import base64
import time
from io import BytesIO
from pathlib import Path
from typing import Optional
from PIL import Image
from .config import (
    MAX_IMAGE_SIZE, ALLOWED_FORMATS, TEMP_IMAGE_DIR, UPLOAD_IMAGE_DIR,
    ALLOWED_DOC_FORMATS, MAX_DOC_SIZE, MAX_DOC_TEXT_CHARS, MAX_PDF_PAGES,
    UPLOAD_RETENTION_SECONDS,
)
from .logger import get_image_logger

# 获取日志器
logger = get_image_logger()


class ImageProcessor:
    """图片处理器"""

    def __init__(self) -> None:
        """初始化图片处理器"""
        self.temp_dir: str = TEMP_IMAGE_DIR
        self.upload_dir: str = UPLOAD_IMAGE_DIR
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.upload_dir, exist_ok=True)
        logger.info(f"图片处理器初始化完成，临时目录: {self.temp_dir}，上传目录: {self.upload_dir}")

    @staticmethod
    def sanitize_extracted_text(text: str) -> str:
        """清理 PDF 文本抽取中可能出现的非法 Unicode 代理字符。"""
        return (text or "").encode("utf-8", errors="replace").decode("utf-8", errors="replace").strip()

    def validate_format(self, image_path: str) -> tuple[bool, str]:
        """
        验证图片格式

        参数:
            image_path: 图片路径

        返回:
            is_valid: 是否是支持的格式
            message: 验证结果消息
        """
        if not os.path.exists(image_path):
            logger.warning(f"图片文件不存在: {image_path}")
            return False, f"图片文件不存在: {image_path}"

        # 获取文件扩展名
        ext: str = Path(image_path).suffix.lower().lstrip('.')

        if ext not in ALLOWED_FORMATS:
            logger.warning(f"不支持图片格式: {ext}")
            return False, f"不支持图片格式 '{ext}'，支持的格式: {', '.join(ALLOWED_FORMATS)}"

        logger.debug(f"图片格式验证通过: {ext}")
        return True, f"图片格式验证通过: {ext}"

    def validate_size(self, image_path: str) -> tuple[bool, str]:
        """
        验证图片大小

        参数:
            image_path: 图片路径

        返回:
            is_valid: 是否在允许的大小范围内
            message: 验证结果消息
        """
        if not os.path.exists(image_path):
            logger.warning(f"图片文件不存在: {image_path}")
            return False, f"图片文件不存在: {image_path}"

        file_size: int = os.path.getsize(image_path)

        if file_size > MAX_IMAGE_SIZE:
            logger.warning(f"图片大小 {file_size / 1024 / 1024:.2f}MB 超过限制")
            return False, f"图片大小 {file_size / 1024 / 1024:.2f}MB 超过限制 {MAX_IMAGE_SIZE / 1024 / 1024:.2f}MB"

        logger.debug(f"图片大小验证通过: {file_size / 1024 / 1024:.2f}MB")
        return True, f"图片大小验证通过: {file_size / 1024 / 1024:.2f}MB"

    def validate_content(self, image_path: str) -> tuple[bool, str]:
        """
        使用 Pillow 校验图片真实内容（防止伪装扩展名的恶意/损坏文件）

        参数:
            image_path: 图片路径

        返回:
            is_valid: 文件是否为可解析的真实图片
            message: 验证结果消息
        """
        if not os.path.exists(image_path):
            logger.warning(f"图片文件不存在: {image_path}")
            return False, f"图片文件不存在: {image_path}"

        try:
            with Image.open(image_path) as img:
                img.verify()  # 校验文件完整性，损坏/伪装文件会抛异常
        except Exception as e:
            logger.warning(f"图片内容校验失败: {image_path} ({e})")
            return False, "图片内容校验失败：文件不是有效的图片或已损坏"

        logger.debug(f"图片内容校验通过: {image_path}")
        return True, "图片内容校验通过"

    def validate_image(self, image_path: str) -> tuple[bool, list[str]]:
        """
        全面验证图片（格式、大小和真实内容）

        参数:
            image_path: 图片路径

        返回:
            is_valid: 是否验证通过
            messages: 验证结果消息列表
        """
        messages: list[str] = []

        # 验证格式
        format_valid: bool
        format_msg: str
        format_valid, format_msg = self.validate_format(image_path)
        messages.append(format_msg)

        if not format_valid:
            return False, messages

        # 验证大小
        size_valid: bool
        size_msg: str
        size_valid, size_msg = self.validate_size(image_path)
        messages.append(size_msg)

        if not size_valid:
            return False, messages

        # 验证真实内容
        content_valid: bool
        content_msg: str
        content_valid, content_msg = self.validate_content(image_path)
        messages.append(content_msg)

        return content_valid, messages

    def save_temp_image(self, image_data: bytes, original_name: Optional[str] = None) -> str:
        """
        保存临时图片

        参数:
            image_data: 图片数据（字节）
            original_name: 原始文件名（可选）

        返回:
            temp_path: 临时图片路径
        """
        # 生成唯一文件名
        unique_id: str = uuid.uuid4().hex
        ext: str = Path(original_name).suffix if original_name else '.jpg'
        temp_filename: str = f"{unique_id}{ext}"

        temp_path: str = os.path.join(self.temp_dir, temp_filename)

        # 保存图片
        with open(temp_path, 'wb') as f:
            f.write(image_data)

        logger.info(f"临时图片已保存: {temp_path}")
        return temp_path

    def persist_upload(self, image_path: str) -> str:
        """
        将上传的图片复制到项目内持久化目录，避免依赖 Gradio 临时路径
        （Gradio 临时文件在重启/换机后会失效，导致历史图片丢失）

        参数:
            image_path: 原始上传图片路径

        返回:
            persisted_path: 持久化后的图片路径；失败时返回原路径
        """
        try:
            ext: str = Path(image_path).suffix.lower() or '.jpg'
            persisted_path: str = os.path.join(self.upload_dir, f"{uuid.uuid4().hex}{ext}")
            shutil.copy2(image_path, persisted_path)
            logger.info(f"上传图片已持久化: {image_path} -> {persisted_path}")
            return persisted_path
        except Exception as e:
            logger.error(f"持久化上传图片失败: {str(e)}")
            return image_path

    def make_thumbnail(self, image_path: str, max_size: tuple[int, int] = (200, 200)) -> Optional[str]:
        """
        生成压缩后的缩略图（base64 data URL），用于界面内联展示

        参数:
            image_path: 图片路径
            max_size: 缩略图最大边长

        返回:
            data URL 字符串；失败时返回 None
        """
        try:
            with Image.open(image_path) as img:
                img = img.convert("RGB")
                img.thumbnail(max_size)
                buffer = BytesIO()
                img.save(buffer, format="JPEG", quality=70)
            b64: str = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return f"data:image/jpeg;base64,{b64}"
        except Exception as e:
            logger.error(f"生成缩略图失败: {str(e)}")
            return None

    def cleanup_temp_image(self, image_path: str) -> bool:
        """
        清理临时图片文件

        参数:
            image_path: 图片路径

        返回:
            success: 是否成功删除
        """
        if os.path.exists(image_path) and image_path.startswith(self.temp_dir):
            try:
                os.remove(image_path)
                logger.info(f"临时图片已删除: {image_path}")
                return True
            except Exception as e:
                logger.error(f"删除临时图片失败: {str(e)}")
                return False

        return False

    def get_image_info(self, image_path: str) -> Optional[dict]:
        """
        获取图片信息

        参数:
            image_path: 图片路径

        返回:
            info: 图片信息字典（格式、大小等）
        """
        if not os.path.exists(image_path):
            logger.warning(f"图片文件不存在: {image_path}")
            return None

        ext: str = Path(image_path).suffix.lower().lstrip('.')
        file_size: int = os.path.getsize(image_path)

        info: dict = {
            'format': ext,
            'size': file_size,
            'size_mb': file_size / 1024 / 1024,
            'path': image_path
        }

        logger.debug(f"获取图片信息: {info}")
        return info

    # ── 文档（PDF）支持（P1-5）────────────────────────────────────
    @staticmethod
    def is_document(file_path: str) -> bool:
        """判断文件是否为受支持的文档（按扩展名）"""
        ext: str = Path(file_path).suffix.lower().lstrip('.')
        return ext in ALLOWED_DOC_FORMATS

    @staticmethod
    def is_image(file_path: str) -> bool:
        """判断文件是否为受支持的图片（按扩展名）"""
        ext: str = Path(file_path).suffix.lower().lstrip('.')
        return ext in ALLOWED_FORMATS

    def validate_document(self, doc_path: str) -> tuple[bool, str]:
        """
        验证文档格式与大小

        参数:
            doc_path: 文档路径

        返回:
            is_valid: 是否通过验证
            message: 验证结果消息
        """
        if not os.path.exists(doc_path):
            return False, f"文档文件不存在: {doc_path}"

        ext: str = Path(doc_path).suffix.lower().lstrip('.')
        if ext not in ALLOWED_DOC_FORMATS:
            return False, f"不支持文档格式 '{ext}'，支持的格式: {', '.join(ALLOWED_DOC_FORMATS)}"

        file_size: int = os.path.getsize(doc_path)
        if file_size > MAX_DOC_SIZE:
            return False, f"文档大小 {file_size / 1024 / 1024:.2f}MB 超过限制 {MAX_DOC_SIZE / 1024 / 1024:.2f}MB"

        return True, "文档验证通过"

    def extract_pdf_text(self, pdf_path: str) -> tuple[bool, str]:
        """
        提取 PDF 文本内容（视觉模型不直接读 PDF，转为文本随问题一起送入）

        参数:
            pdf_path: PDF 文件路径

        返回:
            success: 是否成功提取到文本
            text: 提取的文本（截断到 MAX_DOC_TEXT_CHARS）；失败时为错误说明
        """
        try:
            from pypdf import PdfReader
        except ImportError:
            logger.error("未安装 pypdf，无法解析 PDF")
            return False, "服务器未安装 PDF 解析依赖（pypdf）"

        try:
            reader = PdfReader(pdf_path)
            if len(reader.pages) > MAX_PDF_PAGES:
                return False, f"PDF 页数 {len(reader.pages)} 超过限制 {MAX_PDF_PAGES} 页"
            parts: list[str] = []
            for page in reader.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    parts.append(page_text.strip())
            text = self.sanitize_extracted_text("\n\n".join(parts))
        except Exception as e:
            logger.error(f"PDF 解析失败: {pdf_path} ({e})")
            return False, f"PDF 解析失败: {e}"

        if not text:
            return False, "未能从 PDF 中提取到文本（可能为扫描件图片）"

        if len(text) > MAX_DOC_TEXT_CHARS:
            text = text[:MAX_DOC_TEXT_CHARS] + "\n\n…（文档内容过长，已截断）"
        logger.info(f"PDF 文本提取成功: {pdf_path}，{len(text)} 字符")
        return True, text

    def cleanup_old_uploads(self, retention_seconds: int = UPLOAD_RETENTION_SECONDS) -> int:
        """清理超过保留期的上传文件，避免长期运行时本地文件无限增长"""
        now = time.time()
        removed = 0
        for folder in (self.upload_dir, self.temp_dir):
            if not os.path.isdir(folder):
                continue
            for name in os.listdir(folder):
                path = os.path.join(folder, name)
                if not os.path.isfile(path):
                    continue
                try:
                    if now - os.path.getmtime(path) > retention_seconds:
                        os.remove(path)
                        removed += 1
                except Exception as e:
                    logger.warning(f"清理过期上传文件失败: {path} ({e})")
        if removed:
            logger.info(f"清理过期上传/临时文件: {removed} 个")
        return removed
