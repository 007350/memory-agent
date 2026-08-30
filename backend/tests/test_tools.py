"""
工具模块测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.tools import ToolRegistry, ToolExecutionError, ToolTimeoutError, ToolNotFoundError
from app.tools.python_repl import PythonREPLTool
from app.tools.web_search import WebSearchTool


@pytest.fixture(autouse=True)
def clear_registry():
    """每个测试前清空工具注册表"""
    ToolRegistry.clear()
    yield
    ToolRegistry.clear()


class TestPythonREPLTool:
    """Python REPL 工具测试"""
    
    def test_registration(self):
        """测试工具注册"""
        tool = PythonREPLTool()
        ToolRegistry.register(tool)
        assert "python_repl" in ToolRegistry.list_tools()
    
    @pytest.mark.asyncio
    async def test_simple_calculation(self):
        """测试简单计算"""
        tool = PythonREPLTool()
        result = await tool.execute(code="print(2 + 2)")
        assert "4" in str(result.get("output", ""))
    
    @pytest.mark.asyncio
    async def test_import_math(self):
        """测试导入 math 模块"""
        tool = PythonREPLTool()
        result = await tool.execute(code="import math; print(math.sqrt(16))")
        assert "4.0" in str(result.get("output", ""))
    
    @pytest.mark.asyncio
    async def test_banned_import(self):
        """测试禁止导入危险模块"""
        tool = PythonREPLTool()
        with pytest.raises(ToolExecutionError):
            await tool.execute(code="import os")
    
    @pytest.mark.asyncio
    async def test_dangerous_function(self):
        """测试危险函数检测"""
        tool = PythonREPLTool()
        with pytest.raises(ToolExecutionError):
            await tool.execute(code="eval('2+2')")
    
    @pytest.mark.asyncio
    async def test_timeout(self):
        """测试超时控制"""
        tool = PythonREPLTool()
        tool.timeout = 0.1  # 设置很短超时
        with pytest.raises(ToolTimeoutError):
            await tool.execute(code="import time; time.sleep(10)")


class TestWebSearchTool:
    """WebSearch 工具测试"""
    
    def test_registration(self):
        """测试工具注册"""
        tool = WebSearchTool()
        ToolRegistry.register(tool)
        assert "web_search" in ToolRegistry.list_tools()

    def test_web_sources_from_tool_calls(self):
        """web_search 结果应被提取为 sources（result 是 Python repr 字符串，非 JSON）"""
        from app.agents.general_agent import web_sources_from_tool_calls
        from app.schemas.chat import ToolCall

        tool_calls = [
            ToolCall(
                name="web_search",
                arguments={"query": "北京天气"},
                result=str({"query": "北京天气", "results_count": 1, "results": [
                    {"title": "北京天气", "url": "http://weather.cma.cn", "content": "晴", "source": "web"},
                ]}),
                error="",
                latency=1.0,
            ),
        ]
        sources, used = web_sources_from_tool_calls(tool_calls)
        assert used is True
        assert sources == [{"file_path": "http://weather.cma.cn", "reference_id": "北京天气"}]

    def test_web_sources_dedup_and_limit(self):
        """多次 web_search 返回相同 URL 时应去重，且总量受限"""
        from app.agents.general_agent import web_sources_from_tool_calls
        from app.schemas.chat import ToolCall

        def make_result(urls):
            return str({"query": "q", "results_count": len(urls), "results": [
                {"title": f"t-{u}", "url": u, "content": "c", "source": "web"} for u in urls
            ]})

        tool_calls = [
            ToolCall(name="web_search", arguments={}, result=make_result(["a.com", "b.com"]), error="", latency=1.0),
            ToolCall(name="web_search", arguments={}, result=make_result(["b.com", "c.com", "d.com", "e.com", "f.com"]), error="", latency=1.0),
        ]
        sources, used = web_sources_from_tool_calls(tool_calls)
        assert used is True
        urls = [s["file_path"] for s in sources]
        assert len(urls) == len(set(urls)), "sources 不应有重复 URL"
        assert len(sources) == 5, "默认最多 5 条来源"

    def test_web_sources_skips_failed_calls(self):
        """失败的 web_search 调用不应产出 sources，也不算 used"""
        from app.agents.general_agent import web_sources_from_tool_calls
        from app.schemas.chat import ToolCall

        tool_calls = [
            ToolCall(name="web_search", arguments={}, result="", error="boom", latency=0.1),
            ToolCall(name="python_repl", arguments={"code": "1"}, result="1", error="", latency=0.1),
        ]
        sources, used = web_sources_from_tool_calls(tool_calls)
        assert used is False
        assert sources == []
    
    @pytest.mark.asyncio
    async def test_missing_api_key(self):
        """测试缺少 API Key"""
        tool = WebSearchTool()
        tool.api_key = ""

        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ToolExecutionError, match="API key not configured"):
                await tool.execute(query="test")

    def test_api_key_falls_back_to_settings(self):
        """环境变量没有 FIRECRAWL_API_KEY 时，应从 settings（.env）读取 key"""
        from app.config import settings

        tool = WebSearchTool()
        if not settings.firecrawl_api_key:
            pytest.skip("firecrawl key not configured")
        assert tool.api_key == settings.firecrawl_api_key

    def test_uses_v1_search_endpoint(self):
        """应使用 Firecrawl v1 search 接口（v0 已废弃）"""
        tool = WebSearchTool()
        assert "/v1/search" in tool.base_url

    @pytest.mark.asyncio
    async def test_search_with_mock(self):
        """测试搜索功能（使用 mock）"""
        tool = WebSearchTool()
        tool.api_key = "test-api-key"

        mock_response = {
            "data": [
                {
                    "title": "Test Title",
                    "url": "https://example.com",
                    "description": "Test content here",
                }
            ]
        }

        with patch('httpx.AsyncClient') as mock_client:
            # httpx 的 response.json() 是同步方法，必须用 MagicMock（AsyncMock 会掩盖真实行为）
            mock_client.return_value.__aenter__.return_value.post.return_value.json = MagicMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post.return_value.raise_for_status = MagicMock()

            result = await tool.execute(query="test query")

            assert result["query"] == "test query"
            assert len(result["results"]) == 1
            assert result["results"][0]["title"] == "Test Title"
            assert result["results"][0]["content"] == "Test content here"


class TestToolRegistry:
    """工具注册表测试"""
    
    def test_register_and_get(self):
        """测试注册和获取"""
        tool = PythonREPLTool()
        ToolRegistry.register(tool)
        
        retrieved = ToolRegistry.get("python_repl")
        assert retrieved.name == "python_repl"
    
    def test_get_not_found(self):
        """测试获取不存在的工具"""
        with pytest.raises(ToolNotFoundError):
            ToolRegistry.get("nonexistent_tool")
    
    def test_list_tools(self):
        """测试列出所有工具"""
        ToolRegistry.register(PythonREPLTool())
        ToolRegistry.register(WebSearchTool())
        
        tools = ToolRegistry.list_tools()
        assert len(tools) == 2
        assert "python_repl" in tools
        assert "web_search" in tools
    
    def test_get_definitions(self):
        """测试获取工具定义"""
        ToolRegistry.register(PythonREPLTool())
        
        definitions = ToolRegistry.get_definitions()
        assert len(definitions) == 1
        assert definitions[0]["function"]["name"] == "python_repl"
    
    @pytest.mark.asyncio
    async def test_execute_tool(self):
        """测试执行工具"""
        ToolRegistry.register(PythonREPLTool())
        
        result = await ToolRegistry.execute("python_repl", code="print(1 + 1)")
        assert "2" in str(result.get("output", ""))
    
    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self):
        """测试执行不存在的工具"""
        with pytest.raises(ToolNotFoundError):
            await ToolRegistry.execute("nonexistent_tool")