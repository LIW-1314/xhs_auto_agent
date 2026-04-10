import asyncio
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv

load_dotenv(override=True) 
print("当前使用的 API KEY 后四位:", os.getenv("OPENAI_API_KEY")[-4:] if os.getenv("OPENAI_API_KEY") else "未找到")

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from app.models.schemas import AgentRunRequest, ContentItem, TopicItem
from app.services.agent_service import run_agent_pipeline
from app.services.image_service import generate_images

mcp = FastMCP("xiaohongshu-mcp-adapter", host="127.0.0.1", port=18060)
STATE_FILE = "data/raw/xhs_state.json"
CREATOR_STATE_FILE = "data/raw/creator_state.json"


def _clean_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []

    clean: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        normalized = tag.lstrip("#").strip()
        if normalized and normalized not in seen:
            clean.append(normalized)
            seen.add(normalized)
    return clean[:10]


@mcp.tool()
async def run_content_pipeline(
    audience: str = "大学生女性",
    tone: str = "真实分享",
    topic_count: int = 3,
    content_count_per_topic: int = 2,
) -> dict:
    request = AgentRunRequest(
        audience=audience,
        tone=tone,
        topic_count=topic_count,
        content_count_per_topic=content_count_per_topic,
    )
    result = await run_agent_pipeline(request)

    output = {
        "analysis_summary": result.analysis_summary,
        "top_keywords": result.top_keywords,
        "top_tags": result.top_tags,
        "results": [],
    }
    for item in result.results:
        output["results"].append(
            {
                "topic": {
                    "title": item.topic.title,
                    "reason": item.topic.reason,
                },
                "contents": [
                    {
                        "title": content.title,
                        "body": content.body,
                        "hashtags": content.hashtags,
                        "cta": content.cta,
                        "image_suggestion": content.image_suggestion,
                        "content_type": content.content_type,
                    }
                    for content in item.contents
                ],
            }
        )
    return output


@mcp.tool()
async def generate_xhs_images(
    topic_title: str,
    topic_reason: str,
    content_title: str,
    content_image_suggestion: str,
    content_body: str = "",
    content_hashtags: list[str] = [],
    content_cta: str = "",
    content_type: str = "分享",
    image_count: int = 1,
) -> dict:
    topic = TopicItem(title=topic_title, reason=topic_reason)
    content = ContentItem(
        title=content_title,
        body=content_body,
        hashtags=content_hashtags,
        cta=content_cta,
        image_suggestion=content_image_suggestion,
        content_type=content_type,
    )
    image_paths = await generate_images(topic=topic, content=content, image_count=image_count)
    return {"image_paths": image_paths, "count": len(image_paths)}


@mcp.tool()
async def check_login_status() -> dict:
    if os.path.exists(STATE_FILE) or os.path.exists(CREATOR_STATE_FILE):
        return {"logged_in": True, "username": "LocalUser"}
    return {"logged_in": False, "username": ""}


@mcp.tool()
async def publish_content(
    title: str,
    content: str,
    images: list[str],
    tags: list[str] | None = None,
    is_original: bool = True,
    visibility: str = "公开可见",
    schedule_at: str | None = None,
    products: list[str] | None = None,
) -> dict:
    print(f"\nReceived publish task: title={title}, images={images}")

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=False)

            context = await browser.new_context(
                storage_state=CREATOR_STATE_FILE,
                viewport={"width": 1920, "height": 1080},
            )

            page = await context.new_page()
            await page.goto("https://creator.xiaohongshu.com/publish/publish")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

            try:
                image_tab = page.locator("xpath=//*[text()='上传图文']").first
                await image_tab.wait_for(state="attached", timeout=10000)
                await image_tab.scroll_into_view_if_needed()
                await image_tab.evaluate("node => node.click()")
                await asyncio.sleep(2)
            except Exception as exc:
                print(f"Failed to switch image tab: {exc}")

            try:
                try:
                    async with page.expect_file_chooser(timeout=8000) as chooser_info:
                        upload_btn = page.locator("xpath=//*[text()='上传图片']").first
                        await upload_btn.click()

                    chooser = await chooser_info.value
                    await chooser.set_files(images)
                except Exception:
                    file_input = page.locator("input[type='file']").first
                    await file_input.set_input_files(images)
                    await file_input.evaluate(
                        "node => node.dispatchEvent(new Event('change', { bubbles: true }))"
                    )

                title_locator = page.locator("input[placeholder*='标题'], .c-input_inner").first
                await title_locator.wait_for(state="visible", timeout=45000)
            except Exception as exc:
                await page.screenshot(path="error_upload.png")
                await browser.close()
                return {"success": False, "message": f"图片上传失败: {exc}"}

            try:
                title_locator = page.locator(
                    "input[placeholder*='标题'], input[class*='title'], .c-input_inner"
                ).first
                await title_locator.wait_for(state="visible", timeout=10000)
                await title_locator.click()
                await title_locator.fill(title[:20])
            except Exception as exc:
                print(f"Failed to fill title: {exc}")

            try:
                content_locator = page.locator("[contenteditable='true'], textarea, .ql-editor").first
                await content_locator.wait_for(state="visible", timeout=10000)
                await content_locator.click()
                await page.keyboard.type(content, delay=50)
            except Exception as exc:
                print(f"Failed to fill content: {exc}")

            publish_btn = page.locator("button:has-text('发布')").first
            await publish_btn.click()

            await asyncio.sleep(10)
            await browser.close()
            return {
                "success": True,
                "message": "发布流程已完成，请前往小红书 App 查看结果。",
                "data": {
                    "title": title[:20],
                    "images": images,
                    "tags": _clean_tags(tags),
                    "is_original": is_original,
                    "visibility": visibility,
                    "schedule_at": schedule_at,
                    "products": products or [],
                },
            }
    except Exception as exc:
        return {"success": False, "message": f"发布异常: {exc}"}


@mcp.tool()
async def publish_to_xhs(
    topic_title: str,
    topic_reason: str,
    content_title: str,
    content_body: str,
    content_hashtags: list[str],
    content_cta: str,
    content_image_suggestion: str,
    content_type: str = "分享",
    image_count: int = 1,
    is_original: bool = True,
    visibility: str = "公开可见",
) -> dict:
    topic = TopicItem(title=topic_title, reason=topic_reason)
    content = ContentItem(
        title=content_title,
        body=content_body,
        hashtags=content_hashtags,
        cta=content_cta,
        image_suggestion=content_image_suggestion,
        content_type=content_type,
    )

    image_paths = await generate_images(topic=topic, content=content, image_count=image_count)
    result = await publish_content(
        title=content.title,
        content=f"{content.body}\n\n{content.cta}",
        images=image_paths,
        tags=content.hashtags,
        is_original=is_original,
        visibility=visibility,
    )
    result["image_paths"] = image_paths
    return result


if __name__ == "__main__":
    print("Starting unified XHS MCP server on port 18060...")
    mcp.run(transport="sse")
