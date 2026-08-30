import os

# 在任何 app 模块导入前注入 dummy 环境变量，避免 AsyncOpenAI 因 api_key="" 报错
os.environ.setdefault("LLM_API_KEY", "test-dummy-key")
os.environ.setdefault("LLM_BASE_URL", "https://api.stepfun.com/step_plan/v1")
os.environ.setdefault("LIGHTRAG_BASE_URL", "http://localhost:9621")
