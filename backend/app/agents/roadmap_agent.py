import json
import time
from openai import AsyncOpenAI

from app.config import settings
from app.services.lightrag_client import LightRAGClient, LightRAGUnavailableError
from app.schemas.lightrag import QueryRequest
from app.services import memory_service


_EXTRACT_PROMPT = """从用户消息中提取文档名称。
只返回JSON: {{"doc_name": "<文档名>"}}
如果无法确定，返回: {{"doc_name": ""}}
用户消息: {query}"""

_STEPS_PROMPT = """你是一名专业学习规划师。根据以下文档内容，为用户生成一份结构化的学习路线。

文档内容:
{context}

要求:
- 生成 5~10 个学习步骤
- 每个步骤简明扼要
- 按照学习难度和依赖关系排序
- 只返回JSON数组，不要其他内容

返回格式:
[
  {{"id": 1, "title": "步骤标题", "detail": "具体学习内容和方法", "done": false}},
  ...
]"""


class RoadmapAgent:
    def __init__(self) -> None:
        self._lightrag = LightRAGClient()
        self._llm = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )
        self._model = settings.llm_model_main
        self._model_light = settings.llm_model_light

    async def run(self, query: str, user_id: str) -> str:
        doc_name = await self._extract_doc_name(query)
        search_query = doc_name if doc_name else query

        try:
            rag_response = await self._lightrag.query(
                QueryRequest(query=search_query, mode="hybrid")
            )
            context = rag_response.response or ""
        except LightRAGUnavailableError:
            context = ""

        if not context or context == "No relevant context found for the query.":
            context = f"关于 {search_query} 的学习内容"

        steps = await self._generate_steps(context)
        if not steps:
            return "抱歉，无法为该文档生成学习路线，请确认文档已上传到知识库。"

        title = f"{doc_name or search_query} 学习路线"
        doc_ref = doc_name or search_query
        roadmap_id = await memory_service.save_roadmap(
            user_id=user_id,
            doc_ref=doc_ref,
            title=title,
            steps=steps,
        )

        lines = [f"## {title}", "", f"已生成 {len(steps)} 个学习步骤（路线 ID: {roadmap_id}）", ""]
        for step in steps:
            lines.append(f"**{step['id']}. {step['title']}**")
            lines.append(f"   {step['detail']}")
            lines.append("")
        lines.append("---")
        lines.append("你可以在侧边栏「学习路线」页面查看并跟踪学习进度。")
        return "\n".join(lines)

    async def _extract_doc_name(self, query: str) -> str:
        try:
            # 模板渲染也放进 try：避免模板里的花括号等格式问题导致整个链路 500
            prompt = _EXTRACT_PROMPT.format(query=query)
            resp = await self._llm.chat.completions.create(
                model=self._model_light,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            raw = (resp.choices[0].message.content or "{}").strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            data = json.loads(raw)
            return str(data.get("doc_name", "")).strip()
        except Exception:
            return ""

    async def _generate_steps(self, context: str) -> list[dict]:
        prompt = _STEPS_PROMPT.format(context=context[:3000])
        try:
            resp = await self._llm.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            raw = (resp.choices[0].message.content or "[]").strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            steps = json.loads(raw)
            if not isinstance(steps, list):
                return []
            validated = []
            for step in steps:
                if isinstance(step, dict) and step.get("title"):
                    validated.append({
                        # 按保留下来的顺序连续重排，避免过滤掉无效项后 id 跳号（如 1,3）
                        "id": len(validated) + 1,
                        "title": str(step.get("title", "")),
                        "detail": str(step.get("detail", "")),
                        "done": False,
                    })
            return validated
        except Exception:
            return []

    async def close(self) -> None:
        await self._lightrag.release()
