import json
from openai import AsyncOpenAI

from app.config import settings
from app.services import memory_service


_DIAGNOSIS_PROMPT = """你是一位 AI Agent 学习顾问。请根据以下用户学习数据，生成一份结构化的学习诊断报告。

## 用户画像
{profile}

## 学习路线数据
{roadmaps}

## 历史提问记录（最近 50 条记忆事件）
{events}

要求：
1. 报告用 Markdown 格式，包含以下章节：
   - **总体进度**：统计路线数、步骤总数、已完成数、完成率
   - **各路线进度**：逐条列出每条路线的完成情况
   - **已掌握的强项**：根据已完成步骤和提问记录推断
   - **待补强的薄弱点**：根据未完成步骤和历史反复提问的概念推断
   - **下一步学习建议**：给出 3~5 条具体可执行的建议
2. 语言专业、简洁，重在给出有价值的判断，不要流水账式罗列数据
3. 如果数据不足（没有路线、没有历史记录），诚实说明并给出通用建议"""


class DiagnosisAgent:
    def __init__(self) -> None:
        self._llm = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )
        self._model = settings.llm_model_main

    async def run(self, user_id: str) -> str:
        # 并发获取所有数据
        import asyncio
        roadmaps, events, profile = await asyncio.gather(
            memory_service.get_roadmaps(user_id),
            memory_service.get_memory_events(user_id, limit=50),
            memory_service.get_user_profile(user_id),
        )

        # 格式化路线数据
        if roadmaps:
            roadmap_lines = []
            for r in roadmaps:
                steps = r.get("steps", [])
                done = sum(1 for s in steps if s.get("done"))
                total = len(steps)
                roadmap_lines.append(
                    f"- **{r['title']}**（{r['doc_ref']}）：{done}/{total} 步骤已完成\n"
                    + "\n".join(
                        f"  - [{'x' if s.get('done') else ' '}] {s.get('title', '')}"
                        for s in steps
                    )
                )
            roadmaps_text = "\n".join(roadmap_lines)
        else:
            roadmaps_text = "暂无学习路线"

        # 格式化记忆事件
        if events:
            event_lines = [
                f"- [{e.get('event_type', 'fact')}] {e.get('content', '')}"
                for e in events[:50]
                if e.get("content")
            ]
            events_text = "\n".join(event_lines) if event_lines else "暂无记录"
        else:
            events_text = "暂无记录"

        # 格式化用户画像
        if profile:
            profile_text = "\n".join(f"- {k}: {v}" for k, v in profile.items() if k and v)
        else:
            profile_text = "暂无画像信息"

        prompt = _DIAGNOSIS_PROMPT.format(
            profile=profile_text,
            roadmaps=roadmaps_text,
            events=events_text,
        )

        resp = await self._llm.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return resp.choices[0].message.content or "诊断报告生成失败，请稍后重试。"
