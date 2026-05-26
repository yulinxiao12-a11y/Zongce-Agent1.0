"""
LLM 配置 — 支持任意 OpenAI 兼容 API
自动从 .env 文件加载环境变量
"""
import os
from pathlib import Path

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    # 优先 webapp/.env，其次 项目根/.env
    for env_dir in [Path(__file__).parent, Path(__file__).parent.parent]:
        env_path = env_dir / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    pass

LLM_API_KEY = os.environ.get('LLM_API_KEY', '')
LLM_BASE_URL = os.environ.get('LLM_BASE_URL', '')
LLM_MODEL = os.environ.get('LLM_MODEL', 'default')
LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', '2000'))
