"""
图片处理器测试模块
"""
import os
import pytest
from PIL import Image
from src.image_processor import ImageProcessor


@pytest.fixture
def processor():
    """创建图片处理器实例"""
    return ImageProcessor()


@pytest.fixture
def temp_image(tmp_path):
    """创建临时图片文件"""
    image_path = tmp_path / "test.jpg"
    Image.new("RGB", (10, 10), color="white").save(image_path, format="JPEG")
    return str(image_path)


@pytest.fixture
def large_image(tmp_path):
    """创建超大图片文件"""
    image_path = tmp_path / "large.jpg"
    image_path.write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * (6 * 1024 * 1024))  # 6MB
    return str(image_path)


@pytest.fixture
def png_image(tmp_path):
    """创建PNG图片文件"""
    image_path = tmp_path / "test.png"
    Image.new("RGB", (10, 10), color="white").save(image_path, format="PNG")
    return str(image_path)


class TestValidateFormat:
    """测试格式验证"""

    def test_valid_jpg(self, processor, temp_image):
        result, msg = processor.validate_format(temp_image)
        assert result is True
        assert "验证通过" in msg

    def test_valid_png(self, processor, png_image):
        result, msg = processor.validate_format(png_image)
        assert result is True
        assert "验证通过" in msg

    def test_invalid_format(self, processor, tmp_path):
        txt_path = tmp_path / "test.txt"
        txt_path.write_text("hello")
        result, msg = processor.validate_format(str(txt_path))
        assert result is False
        assert "不支持" in msg

    def test_not_exists(self, processor):
        result, msg = processor.validate_format("/nonexistent/image.jpg")
        assert result is False
        assert "不存在" in msg


class TestValidateSize:
    """测试大小验证"""

    def test_valid_size(self, processor, temp_image):
        result, msg = processor.validate_size(temp_image)
        assert result is True
        assert "验证通过" in msg

    def test_invalid_size(self, processor, large_image):
        result, msg = processor.validate_size(large_image)
        assert result is False
        assert "超过限制" in msg

    def test_not_exists(self, processor):
        result, msg = processor.validate_size("/nonexistent/image.jpg")
        assert result is False
        assert "不存在" in msg


class TestValidateImage:
    """测试完整验证"""

    def test_valid_image(self, processor, temp_image):
        result, messages = processor.validate_image(temp_image)
        assert result is True
        assert len(messages) == 3
        assert "内容校验通过" in messages[-1]

    def test_invalid_format_stops_early(self, processor, tmp_path):
        txt_path = tmp_path / "test.txt"
        txt_path.write_text("hello")
        result, messages = processor.validate_image(str(txt_path))
        assert result is False
        assert len(messages) == 1  # 格式失败后不检查大小


class TestSaveTempImage:
    """测试临时图片保存"""

    def test_save_image(self, processor):
        image_data = b'\xff\xd8\xff\xe0' + b'\x00' * 100
        path = processor.save_temp_image(image_data, "test.jpg")
        assert os.path.exists(path)
        assert path.endswith(".jpg")
        # 清理
        processor.cleanup_temp_image(path)

    def test_save_without_name(self, processor):
        image_data = b'\xff\xd8\xff\xe0' + b'\x00' * 100
        path = processor.save_temp_image(image_data)
        assert os.path.exists(path)
        processor.cleanup_temp_image(path)


class TestCleanupTempImage:
    """测试临时图片清理"""

    def test_cleanup_existing(self, processor):
        image_data = b'\xff\xd8\xff\xe0' + b'\x00' * 100
        path = processor.save_temp_image(image_data, "test.jpg")
        result = processor.cleanup_temp_image(path)
        assert result is True
        assert not os.path.exists(path)

    def test_cleanup_nonexistent(self, processor):
        result = processor.cleanup_temp_image("/nonexistent/image.jpg")
        assert result is False

    def test_cleanup_outside_temp_dir(self, processor, temp_image):
        result = processor.cleanup_temp_image(temp_image)
        assert result is False  # 不删除非临时目录的文件


class TestGetImageInfo:
    """测试获取图片信息"""

    def test_get_info(self, processor, temp_image):
        info = processor.get_image_info(temp_image)
        assert info is not None
        assert info['format'] == 'jpg'
        assert info['size'] > 0
        assert info['size_mb'] > 0

    def test_get_info_not_exists(self, processor):
        info = processor.get_image_info("/nonexistent/image.jpg")
        assert info is None


class TestCleanupOldUploads:
    """测试过期上传/临时文件清理"""

    def test_cleanup_old_uploads(self, processor):
        path = processor.save_temp_image(b"old", "old.jpg")
        result = processor.cleanup_old_uploads(retention_seconds=0)
        assert result >= 1
        assert not os.path.exists(path)
