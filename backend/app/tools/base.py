"""
工具基类和注册表
"""
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.tools.exceptions import ToolError, ToolNotFoundError


class BaseTool(ABC):
    """
    工具基类
    所有工具必须继承此类并实现 execute 方法
    """
    
    # 工具名称（唯一标识）
    name: str = ""
    
    # 工具描述（用于 LLM 理解何时使用）
    description: str = ""
    
    # 工具参数定义（OpenAI Function Calling 格式）
    parameters: Dict[str, Any] = {}
    
    # 工具超时时间（秒）
    timeout: float = 5.0
    
    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """
        执行工具逻辑
        
        Args:
            **kwargs: 工具参数
            
        Returns:
            工具执行结果
            
        Raises:
            ToolExecutionError: 执行失败
            ToolTimeoutError: 执行超时
        """
        pass
    
    def get_definition(self) -> Dict[str, Any]:
        """
        获取工具定义（OpenAI Function Calling 格式）
        
        Returns:
            工具定义字典
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }
    
    def validate_parameters(self, **kwargs) -> bool:
        """
        验证参数（简单实现，可被子类重写）
        
        Args:
            **kwargs: 待验证的参数
            
        Returns:
            是否验证通过
            
        Raises:
            ToolValidationError: 验证失败
        """
        required = self.parameters.get("required", [])
        for param in required:
            if param not in kwargs:
                raise ToolValidationError(
                    self.name,
                    f"Missing required parameter: {param}"
                )
        return True


class ToolRegistry:
    """
    工具注册表
    统一管理所有可用工具
    """
    
    _tools: Dict[str, BaseTool] = {}
    
    @classmethod
    def register(cls, tool: BaseTool) -> None:
        """
        注册工具
        
        Args:
            tool: BaseTool 实例
        """
        if not tool.name:
            raise ValueError("Tool must have a name")
        cls._tools[tool.name] = tool
    
    @classmethod
    def get(cls, name: str) -> BaseTool:
        """
        获取工具
        
        Args:
            name: 工具名称
            
        Returns:
            BaseTool 实例
            
        Raises:
            ToolNotFoundError: 工具未找到
        """
        if name not in cls._tools:
            raise ToolNotFoundError(name)
        return cls._tools[name]
    
    @classmethod
    def list_tools(cls) -> List[str]:
        """
        列出所有已注册工具
        
        Returns:
            工具名称列表
        """
        return list(cls._tools.keys())
    
    @classmethod
    def get_definitions(cls) -> List[Dict[str, Any]]:
        """
        获取所有工具的定义（OpenAI Function Calling 格式）
        
        Returns:
            工具定义列表
        """
        return [tool.get_definition() for tool in cls._tools.values()]
    
    @classmethod
    async def execute(cls, name: str, **kwargs) -> Any:
        """
        执行工具
        
        Args:
            name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            工具执行结果
            
        Raises:
            ToolNotFoundError: 工具未找到
            ToolExecutionError: 执行失败
            ToolTimeoutError: 执行超时
        """
        tool = cls.get(name)
        
        # 验证参数
        tool.validate_parameters(**kwargs)
        
        # 执行工具（带超时控制）
        try:
            import asyncio
            result = await asyncio.wait_for(
                tool.execute(**kwargs),
                timeout=tool.timeout,
            )
            return result
        except asyncio.TimeoutError:
            from app.tools.exceptions import ToolTimeoutError
            raise ToolTimeoutError(name, tool.timeout)
        except ToolError:
            raise
        except Exception as e:
            from app.tools.exceptions import ToolExecutionError
            raise ToolExecutionError(name, str(e), details={"exception": type(e).__name__})
    
    @classmethod
    def clear(cls) -> None:
        """清空注册表（主要用于测试）"""
        cls._tools.clear()