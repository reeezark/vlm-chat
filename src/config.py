"""
配置文件
存储API密钥、模型名称和其他配置参数
"""
import os

# 尝试从.env文件加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()  # 加载.env文件中的环境变量
except ImportError:
    # 如果没有安装python-dotenv，继续使用系统环境变量
    pass

# API配置 - 从环境变量或.env文件获取
DASHSCOPE_API_KEY: str = os.getenv('DASHSCOPE_API_KEY', '')  # API密钥
BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"  # OpenAI兼容接口地址
MODEL_NAME: str = os.getenv('MODEL_NAME', 'qwen-vl-plus')  # 模型名称（可配置）

# 图片配置
MAX_IMAGE_SIZE: int = 5 * 1024 * 1024  # 最大图片大小5MB
ALLOWED_FORMATS: list[str] = ['jpg', 'jpeg', 'png', 'webp']  # 支持的图片格式
TEMP_IMAGE_DIR: str = "data/temp_images"  # 临时图片存储目录

# 会话配置
MAX_HISTORY_LENGTH: int = 10  # 最大对话轮数
SESSION_TIMEOUT: int = 3600  # 会话超时时间（秒）

# 生成参数
TEMPERATURE: float = 0.7  # 温度参数
MAX_TOKENS: int = 512  # 最大生成token数
TOP_P: float = 0.9  # Top-p采样参数

# 界面配置
GRADIO_SERVER_NAME: str = "0.0.0.0"  # Gradio服务器地址
GRADIO_SERVER_PORT: int = 7860  # Gradio服务器端口
GRADIO_SHARE: bool = False  # 是否创建公开分享链接
