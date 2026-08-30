"""
工具异常定义
"""
from typing import Any


class ToolError(Exception):
    """工具错误基类"""
    pass


class ToolNotFoundError(ToolError):
    """工具未找到"""
    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' not found")


class ToolValidationError(ToolError):
    """工具参数验证失败"""
    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' validation error: {message}")


class ToolExecutionError(ToolError):
    """工具执行错误"""
    def __init__(self, tool_name: str, message: str, details: Any = None):
        self.tool_name = tool_name
        self.details = details
        super().__init__(f"Tool '{tool_name}' execution error: {message}")


class ToolTimeoutError(ToolExecutionError):
    """工具执行超时"""
    def __init__(self, tool_name: str, timeout: float):
        super().__init__(
            tool_name,
            f"Execution timed out after {timeout}s",
            details={"timeout": timeout},
        )