"""
图片处理模块
实现图片格式验证、大小检查、临时存储等功能
"""
import os
import uuid
from pathlib import Path
from typing import Optional
from .config import MAX_IMAGE_SIZE, ALLOWED_FORMATS, TEMP_IMAGE_DIR
from .logger import get_image_logger

# 获取日志器
logger = get_image_logger()


class ImageProcessor:
    """图片处理器"""

    def __init__(self) -> None:
        """初始化图片处理器"""
        self.temp_dir: str = TEMP_IMAGE_DIR
        os.makedirs(self.temp_dir, exist_ok=True)
        logger.info(f"图片处理器初始化完成，临时目录: {self.temp_dir}")

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

    def validate_image(self, image_path: str) -> tuple[bool, list[str]]:
        """
        全面验证图片（格式和大小）

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

        return size_valid, messages

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
