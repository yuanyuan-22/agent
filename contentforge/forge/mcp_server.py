"""ContentForge MCP server.

运行：
    python -m forge.mcp_server

在 Claude Code / Codex / opencode 中注册 stdio MCP server 后，
模型即可创建内容任务、查询 trace、检索经验库、触发离线评测。
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, List

from mcp.server.mcpserver import MCPServer

server = MCPServer(
    "contentforge",
    title="ContentForge Agent Factory",
    description="多智能体内容生产平台的 MCP 工具：任务、trace、经验库、评测。",
    version="0.1.0",
)


def _run_job_in_thread(job_id: str, source: str, style: str,
                       channel: str = "auto",
                       manual: Dict[str, Any] | None = None,
                       visual_style: str = "tech_infographic",
                       generation_mode: str = "balanced",
                       character_id: str = "host_default") -> None:
    from forge.graph import run_job_graph

    try:
        run_job_graph(
            job_id, source, style, channel=channel, manual=manual,
            visual_style=visual_style, generation_mode=generation_mode,
            character_id=character_id,
        )
    except Exception:
        pass


@server.tool(
    name="list_jobs",
    title="List production jobs",
    description="列出 ContentForge 生产任务，可用于确认后台运行状态。",
)
def list_jobs(limit: int = 20) -> List[Dict[str, Any]]:
    from forge.store import list_jobs

    return list_jobs(limit=max(1, min(int(limit or 20), 100)))


@server.tool(
    name="get_job",
    title="Get job detail",
    description="获取单个任务的状态、发布状态、人工复核标记与结果摘要。",
)
def get_job(job_id: str) -> Dict[str, Any]:
    from forge.store import get_job

    job = get_job(job_id)
    return job or {"error": "job not found", "job_id": job_id}


@server.tool(
    name="create_job",
    title="Create content job",
    description="创建内容生产任务：支持 B站/抖音/快手/小红书链接，后台运行抓取->拆DNA->改写->审稿->出片。",
)
def create_job(source: str, style: str = "", channel: str = "auto",
               manual: Dict[str, Any] | None = None,
               visual_style: str = "tech_infographic",
               generation_mode: str = "balanced",
               character_id: str = "host_default") -> Dict[str, Any]:
    from forge.graph import new_job

    source = (source or "").strip()
    if not source:
        return {"error": "source required"}
    job_id = new_job(
        source, style, channel=channel,
        visual_style=visual_style,
        generation_mode=generation_mode,
        character_id=character_id,
    )
    thread = threading.Thread(
        target=_run_job_in_thread,
        args=(job_id, source, style, channel, manual or {},
              visual_style, generation_mode, character_id),
        daemon=True,
    )
    thread.start()
    return {"job_id": job_id, "status": "queued", "source": source}


@server.tool(
    name="get_job_trace",
    title="Get job trace events",
    description="返回任务完整事件流，用于可观测/排查/面试演示。",
)
def get_job_trace(job_id: str, after: int = 0) -> List[Dict[str, Any]]:
    from forge.store import events_after

    return events_after(job_id, after_id=max(0, int(after or 0)), limit=1000)


@server.tool(
    name="search_experience",
    title="Search experience library",
    description="按语义检索经验库，返回复盘沉淀的可复用经验。",
)
def search_experience(query: str = "", top_k: int = 3) -> Dict[str, Any]:
    from forge import experience
    from forge.store import list_experiences

    query = (query or "").strip()
    if not query:
        return {"items": list_experiences(limit=20)}
    return {"items": experience.search(query, top_k=max(1, min(int(top_k or 3), 10)))}


@server.tool(
    name="eval_runs",
    title="Audit run quality",
    description="扫描 runs/ 产物，返回规则通过率、Review 通过率、人工复核率与常见失败原因。",
)
def eval_runs() -> Dict[str, Any]:
    from forge.evalkit import scan_runs, summarize

    return summarize(scan_runs())


@server.tool(
    name="import_sources",
    title="Import multi-platform source links",
    description="导入 B站/抖音/快手/小红书分享链接，成功时解析公开元信息，失败时进入人工补录队列。",
)
def import_sources(urls: List[str]) -> List[Dict[str, Any]]:
    from forge.channels.registry import get_adapter
    from forge.store import upsert_source_item

    results = []
    for url in urls:
        try:
            source = get_adapter(url).fetch(url)
            results.append(upsert_source_item(
                source.platform, url, status="parsed", title=source.title,
                payload=source.to_dict(),
            ))
        except Exception as exc:  # noqa: BLE001
            results.append(upsert_source_item(
                "manual", url, status="manual_required",
                payload={"url": url, "error": str(exc)},
            ))
    return results


@server.tool(
    name="trending_sources",
    title="List trending or imported sources",
    description="B站返回真实热门榜；其他平台返回已导入的来源队列。",
)
def trending_sources(platform: str = "bilibili", limit: int = 10) -> Dict[str, Any]:
    from forge.channels.registry import get_adapter
    from forge.store import list_source_items

    if platform == "bilibili":
        try:
            return {"items": get_adapter(platform).trending(limit=limit)}
        except Exception:
            return {"items": []}
    return {"items": list_source_items(platform=platform, limit=limit)}


@server.tool(
    name="prepare_publish",
    title="Prepare publish package",
    description="按任务目标平台生成发布包、复制文案和创作中心链接。",
)
def prepare_publish(job_id: str) -> Dict[str, Any]:
    from forge.publish import prepare_publish_package

    return prepare_publish_package(job_id)


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
