from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    AgentRunRequest,
    PreparePublishRequest,
    TaskCreateResponse,
    TaskDetail,
    TaskListResponse,
)
from app.services.agent_service import run_agent_pipeline
from app.services.image_service import generate_images
from app.services.publish_service import send_to_xhs
from app.services.review_service import review_content
from app.services.task_service import create_task, get_task, list_tasks, schedule_task

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("", response_model=TaskListResponse, summary="列出最近任务")
async def list_recent_tasks(limit: int = 20) -> TaskListResponse:
    return list_tasks(limit=limit)


@router.get("/{task_id}", response_model=TaskDetail, summary="查询任务详情")
async def get_task_detail(task_id: str) -> TaskDetail:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return task


@router.post("/agent/run", response_model=TaskCreateResponse, summary="异步创建内容生成任务")
async def create_agent_task(request: AgentRunRequest) -> TaskCreateResponse:
    payload = request.model_dump(mode="json")
    created = create_task(
        task_type="agent_run",
        input_payload=payload,
        message="内容生成任务已创建",
        max_retries=1,
    )

    async def runner() -> dict:
        result = await run_agent_pipeline(request)
        return result.model_dump(mode="json")

    schedule_task(
        task_id=created.task_id,
        runner=runner,
        running_message="正在执行内容生成流水线",
        success_message="内容生成完成",
        max_retries=1,
        retry_delay_seconds=1.5,
    )
    return created


@router.post("/publish/run", response_model=TaskCreateResponse, summary="异步创建发布任务")
async def create_publish_task(request: PreparePublishRequest) -> TaskCreateResponse:
    payload = request.model_dump(mode="json")
    created = create_task(
        task_type="publish_run",
        input_payload=payload,
        message="发布任务已创建",
        max_retries=2,
    )

    async def runner() -> dict:
        review = review_content(request.content)
        image_paths = await generate_images(
            topic=request.topic,
            content=request.content,
            image_count=request.image_count,
        )
        result = await send_to_xhs(
            content=request.content,
            image_paths=image_paths,
            is_original=request.is_original,
            visibility=request.visibility,
            mode=request.mode,
        )
        data = result.model_dump(mode="json")
        data["image_paths"] = image_paths
        data["review"] = review.model_dump(mode="json")
        return data

    schedule_task(
        task_id=created.task_id,
        runner=runner,
        running_message="正在生成图片并发布内容",
        success_message="发布流程完成",
        max_retries=2,
        retry_delay_seconds=3.0,
    )
    return created
