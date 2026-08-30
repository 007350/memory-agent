"""
WebSearch 工具
使用 Firecrawl API 进行网络搜索
"""
import json
from typing import Any, Dict, List

import httpx

from app.config import settings
from app.tools.base import BaseTool
from app.tools.exceptions import ToolExecutionError


class WebSearchTool(BaseTool):
    """
    网络搜索工具（基于 Firecrawl API）

    功能：
    - 搜索互联网获取最新信息
    - 返回结构化的搜索结果
    - 支持自定义返回数量
    """

    name = "web_search"
    description = """在互联网上搜索最新信息。适用于：
- 查找实时信息（新闻、天气、股价、汇率等）
- 搜索文档和教程
- 查找 API 文档和示例
- 获取最新动态和趋势

返回结构化的搜索结果，包含标题、链接和内容摘要。"""

    timeout: float = 15.0
    max_results: int = 5

    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索查询语句（建议使用英文或中文，清晰表达搜索意图）"
            },
            "max_results": {
                "type": "integer",
                "description": f"返回结果数量（可选，默认 {max_results}，最大 10）",
                "maximum": 10,
            }
        },
        "required": ["query"]
    }

    def __init__(self):
        # settings 已从 .env 加载；os.environ 作为显式环境变量优先
        import os
        self.api_key = os.environ.get("FIRECRAWL_API_KEY", "") or settings.firecrawl_api_key

        # Firecrawl v1 search 接口（v0 已废弃，会返回人机验证页）
        self.base_url = settings.firecrawl_base_url.rstrip("/") + "/search"

    async def execute(self, query: str, max_results: int = None) -> Dict[str, Any]:
        """
        执行网络搜索

        Args:
            query: 搜索查询
            max_results: 返回结果数量（可选）

        Returns:
            包含 search_results 的字典
        """
        if not self.api_key:
            raise ToolExecutionError(
                self.name,
                "WebSearch API key not configured. Please set FIRECRAWL_API_KEY environment variable."
            )

        if max_results is None:
            max_results = self.max_results

        # 限制最大结果数
        max_results = min(max_results, 10)

        # 调用 Firecrawl API
        try:
            results = await self._firecrawl_search(query, max_results)
            return {
                "query": query,
                "results_count": len(results),
                "results": results,
            }
        except httpx.HTTPStatusError as e:
            raise ToolExecutionError(
                self.name,
                f"Search API error: {e.response.status_code}",
                details={"status_code": e.response.status_code}
            )
        except httpx.TimeoutException:
            raise ToolExecutionError(
                self.name,
                "Search request timed out"
            )
        except Exception as e:
            raise ToolExecutionError(
                self.name,
                f"Search failed: {str(e)}",
                details={"error_type": type(e).__name__}
            )

    async def _firecrawl_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """
        调用 Firecrawl API（v1）

        Args:
            query: 搜索查询
            max_results: 最大结果数

        Returns:
            搜索结果列表
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "query": query,
            "limit": max_results,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            # httpx 的 response.json() 是同步方法，不能 await
            data = response.json()

        # 解析 Firecrawl v1 响应：data[] 含 url/title/description（开启 scrape 时还有 markdown）
        results = []
        for item in data.get("data", []):
            content = item.get("markdown") or item.get("description") or item.get("content", "")
            result = {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": self._truncate_content(content),
                "source": "web",
            }
            results.append(result)

        return results

    def _truncate_content(self, content: str, max_length: int = 1000) -> str:
        """
        截断内容（防止返回过长）

        Args:
            content: 原始内容
            max_length: 最大长度

        Returns:
            截断后的内容
        """
        if not content:
            return ""

        content = content.strip()
        if len(content) <= max_length:
            return content

        # 智能截断：在句子结束处截断
        truncated = content[:max_length]
        last_period = max(
            truncated.rfind('.'),
            truncated.rfind('。'),
            truncated.rfind('\n')
        )

        if last_period > max_length * 0.7:  # 如果找到句末标点且在 70% 位置后
            return truncated[:last_period + 1]

        return truncated + "..."
