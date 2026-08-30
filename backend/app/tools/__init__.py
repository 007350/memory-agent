"""
Tool Use 模块
提供可扩展的工具调用框架
"""
from app.tools.base import BaseTool, ToolRegistry
from app.tools.exceptions import (
    ToolExecutionError,
    ToolTimeoutError,
    ToolNotFoundError,
    ToolValidationError,
)
from app.tools.python_repl import PythonREPLTool
from app.tools.web_search import WebSearchTool


def init_tools() -> None:
    """
    初始化所有工具
    在应用启动时调用
    """
    # 注册 Python REPL 工具
    ToolRegistry.register(PythonREPLTool())
    
    # 注册 WebSearch 工具
    ToolRegistry.register(WebSearchTool())


__all__ = [
    "BaseTool",
    "ToolRegistry",
    "ToolExecutionError",
    "ToolTimeoutError",
    "ToolNotFoundError",
    "ToolValidationError",
    "PythonREPLTool",
    "WebSearchTool",
    "init_tools",
]