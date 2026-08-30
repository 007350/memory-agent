from app.schemas.chat import KnowledgeAnswer


class VisionAgent:
    async def run(self, query: str, memory_context: list = [], user_profile=None, memory_events=None) -> KnowledgeAnswer:
        return KnowledgeAnswer(
            answer="暂不支持图片分析，请将图片内容用文字描述后再提问。",
            sources=[],
            retrieval_mode="none",
            latency=0.0,
            model="none",
        )
