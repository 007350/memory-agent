import ast
import time
import json
from openai import AsyncOpenAI

from app.config import settings
from app.agents.knowledge_agent import _build_messages_with_memory
from app.schemas.chat import KnowledgeAnswer, ToolCall
from app.tools import ToolRegistry


_SYSTEM_PROMPT = (
    "你是一个通用助手，擅长回答各类问题。"
    "当需要搜索互联网获取最新信息时，使用 web_search 工具。"
    "用简体中文回答，保持简洁友好。"
)


def web_sources_from_tool_calls(tool_calls_log: list, max_sources: int = 5) -> tuple[list, bool]:
    """从工具调用记录中提取 web_search 的来源列表（按 URL 去重、限量）。返回 (sources, used_web_search)。"""
    sources = []
    seen_urls = set()
    used = False
    for tc in tool_calls_log:
        if getattr(tc, "name", "") == "web_search" and not tc.error:
            used = True
            try:
                # result 存的是 str(dict)（Python repr，单引号），不是 JSON
                data = ast.literal_eval(tc.result) if isinstance(tc.result, str) else tc.result
                for r in (data or {}).get("results", []):
                    url = r.get("url", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    sources.append({
                        "file_path": url,
                        "reference_id": r.get("title", "")[:60] or url,
                    })
            except (ValueError, SyntaxError, AttributeError):
                pass
    return sources[:max_sources], used


class GeneralAgent:
    def __init__(self) -> None:
        self._llm = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )
        self._model = settings.llm_model_light

    async def run(
        self,
        query: str,
        memory_context: list = [],
        user_profile=None,
        memory_events=None,
        tools: list = None,
        max_tool_iterations: int = 3,
    ) -> KnowledgeAnswer:
        start = time.monotonic()
        messages, used_memories = _build_messages_with_memory(query, memory_context, user_profile=user_profile, memory_events=memory_events)
        # 在 system message 之前插入通用助手角色提示
        messages.insert(0, {"role": "system", "content": _SYSTEM_PROMPT})
        
        # 如果有工具，使用工具调用
        tool_calls_log = []
        if tools:
            answer, tool_calls_log = await self._run_with_tools(
                messages, tools, max_tool_iterations
            )
        else:
            completion = await self._llm.chat.completions.create(
                model=self._model,
                messages=messages,
            )
            answer = completion.choices[0].message.content or ""
        
        latency = time.monotonic() - start
        # web_search 有结果时把来源透出给前端展示（retrieval_mode=web 分支）
        sources, used_web_search = web_sources_from_tool_calls(tool_calls_log)
        return KnowledgeAnswer(
            answer=answer,
            sources=sources,
            retrieval_mode="web" if used_web_search else "none",
            latency=round(latency, 3),
            model=self._model,
            tool_calls=tool_calls_log,
            used_memories=used_memories,
        )
    
    async def _run_with_tools(
        self,
        messages: list,
        tools: list,
        max_iterations: int,
    ) -> tuple[str, list[ToolCall]]:
        """
        使用工具调用运行对话
        
        Args:
            messages: 消息列表
            tools: 可用工具列表
            max_iterations: 最大工具调用次数
            
        Returns:
            (answer, tool_calls_log)
        """
        tool_calls_log = []
        iteration = 0
        
        # 获取工具定义（OpenAI function calling 格式）
        tool_defs = [tool.get_definition() for tool in tools]
        
        while iteration < max_iterations:
            iteration += 1
            
            # 调用 LLM
            completion = await self._llm.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=tool_defs if tool_defs else None,
            )
            
            message = completion.choices[0].message
            
            # 如果没有工具调用，返回答案
            if not message.tool_calls:
                return message.content or "", tool_calls_log
            
            # 处理工具调用
            messages.append(message)  # 添加助手的工具调用消息
            
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}
                
                # 执行工具
                tool_start = time.monotonic()
                try:
                    result = await ToolRegistry.execute(tool_name, **tool_args)
                    result_str = str(result)
                    error_str = ""
                except Exception as e:
                    result_str = ""
                    error_str = str(e)
                
                tool_latency = time.monotonic() - tool_start
                
                # 记录工具调用
                tool_call_log = ToolCall(
                    name=tool_name,
                    arguments=tool_args,
                    result=result_str,
                    error=error_str,
                    latency=round(tool_latency, 3),
                )
                tool_calls_log.append(tool_call_log)
                
                # 添加工具结果到消息
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_str if not error_str else f"Error: {error_str}",
                })
        
        # 达到最大迭代次数，获取最终答案
        completion = await self._llm.chat.completions.create(
            model=self._model,
            messages=messages,
        )
        return completion.choices[0].message.content or "", tool_calls_log