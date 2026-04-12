import json
from pathlib import Path
from typing import List

from app.models.schemas import (
    AgentGeneratedTopicWithContents,
    AgentRunRequest,
    AgentRunResponse,
    ContentGenerateRequest,
    NoteItem,
    TopicGenerateRequest,
)
from app.services.analysis_service import analyze_notes
from app.services.content_service import generate_contents
from app.services.topic_service import generate_topics

SAMPLE_NOTES_FILE = Path("data/raw/sample_notes.json")
LATEST_CRAWL_FILE = Path("data/raw/latest_crawled_notes.json")


def _load_notes_from_file(file_path: Path) -> List[NoteItem]:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", data) if isinstance(data, dict) else data
    return [NoteItem(**item) for item in items]


def load_available_notes(request_items: List[NoteItem] | None) -> List[NoteItem]:
    if request_items:
        return request_items

    if LATEST_CRAWL_FILE.exists():
        return _load_notes_from_file(LATEST_CRAWL_FILE)

    if SAMPLE_NOTES_FILE.exists():
        return _load_notes_from_file(SAMPLE_NOTES_FILE)

    raise FileNotFoundError(
        "未检测到可用的笔记数据。请先完成一次采集，或在请求中传入 items，"
        "或提供 data/raw/sample_notes.json 样例文件。"
    )


async def run_agent_pipeline(request: AgentRunRequest) -> AgentRunResponse:
    """
    Note source priority:
    1. request.items
    2. data/raw/latest_crawled_notes.json
    3. data/raw/sample_notes.json
    """
    notes = load_available_notes(request.items)

    analysis_result = analyze_notes(notes)

    topic_result = generate_topics(
        TopicGenerateRequest(
            summary=analysis_result.summary,
            top_keywords=analysis_result.top_keywords,
            top_tags=analysis_result.top_tags,
            title_patterns=analysis_result.title_patterns,
            insight_points=analysis_result.insight_points,
            audience=request.audience,
            count=request.topic_count,
        )
    )

    results = []
    for topic in topic_result.topics:
        content_result = generate_contents(
            ContentGenerateRequest(
                topic=topic.title,
                reason=topic.reason,
                audience=request.audience,
                tone=request.tone,
                count=request.content_count_per_topic,
            )
        )
        results.append(
            AgentGeneratedTopicWithContents(
                topic=topic,
                contents=content_result.contents,
            )
        )

    return AgentRunResponse(
        analysis_summary=analysis_result.summary,
        top_keywords=analysis_result.top_keywords,
        top_tags=analysis_result.top_tags,
        title_patterns=analysis_result.title_patterns,
        insight_points=analysis_result.insight_points,
        results=results,
    )
