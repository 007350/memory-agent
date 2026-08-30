import httpx
from app.config import settings


async def web_search(query: str, max_results: int = 5) -> list[dict]:
    """
    调用 Firecrawl /search 端点搜索网络内容。
    返回 [{"title": ..., "url": ..., "snippet": ...}, ...]
    """
    if not settings.firecrawl_api_key:
        return []

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{settings.firecrawl_base_url}/search",
                headers={
                    "Authorization": f"Bearer {settings.firecrawl_api_key}",
                    "Content-Type": "application/json",
                },
                json={"query": query, "limit": max_results},
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("data", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description") or item.get("markdown", "")[:500] or "",
            })
        return results

    except Exception:
        return []
