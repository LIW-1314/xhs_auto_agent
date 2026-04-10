import os
import asyncio
from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright

# 初始化 MCP 服务
mcp = FastMCP("xiaohongshu-mcp-adapter", host="127.0.0.1", port=18060)
# 复用爬虫采集时生成的登录态文件
STATE_FILE = "data/raw/xhs_state.json"

@mcp.tool()
async def check_login_status() -> dict:
    """检查小红书登录状态"""
    if os.path.exists(STATE_FILE):
        return {"logged_in": True, "username": "LocalUser"}
    return {"logged_in": False, "username": ""}

@mcp.tool()
async def publish_content(
    title: str,
    content: str,
    images: list[str],
    tags: list[str] = None,
    is_original: bool = True,
    visibility: str = "公开可见",
    schedule_at: str = None,
    products: list[str] = None
) -> dict:
    """自动化发布图文内容到小红书"""
    print(f"\n🚀 收到发布任务:\n标题: {title}\n图片: {images}")
    
    try:
        async with async_playwright() as p:
            # 启动浏览器，headless=False 会弹出可见窗口
            browser = await p.chromium.launch(headless=False)
            
            # 加载创作中心登录态
            state_path = "data/raw/creator_state.json" 

            if os.path.exists(state_path):
                # 把浏览器视口强制撑大到 1920x1080，避免一些元素因为响应式布局而找不到
                context = await browser.new_context(
                    storage_state=state_path,
                    viewport={'width': 1920, 'height': 1080}
                )
                print("✅ 已加载创作者中心专属凭证！")
            else:
                context = await browser.new_context(
                    storage_state=state_path,
                    viewport={'width': 1920, 'height': 1080}
                )
                print("⚠️ 警告：未找到专属凭证！")

            page = await context.new_page()
            await page.goto("https://creator.xiaohongshu.com/publish/publish")
            print("✅ 已成功进入小红书创作者发布中心！")

            try:
                # 直接打印数据
                print(f"📦 接收到标题: {title}")
                print(f"📦 接收到图片路径: {images}")
                print("⏳ 等待网页底层脚本加载...")
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(2)
                print("⏳ 正在切换到【上传图文】模式...")
                try:
                    image_tab = page.locator("xpath=//*[text()='上传图文']").first
                    await image_tab.wait_for(state="attached", timeout=10000)
                    await image_tab.scroll_into_view_if_needed()
                    await image_tab.evaluate("node => node.click()")
                    print("✅ 成功点击【上传图文】！等待网页状态刷新...")
                    await asyncio.sleep(2)
                except Exception as e:
                    print(f"⚠️ 切换图文 Tab 失败，网页结构可能变化: {e}")
                    
                print("⏳ 正在上传图片...")
                try:
                    # 方案 A：尝试截获系统弹窗
                    try:
                        async with page.expect_file_chooser(timeout=8000) as fc_info:
                            # 寻找“上传图片”大按钮并点击
                            upload_btn = page.locator("xpath=//*[text()='上传图片']").first
                            await upload_btn.click()
                            
                        file_chooser = await fc_info.value
                        await file_chooser.set_files(images)
                        print("🚀 已成功通过模拟系统弹窗塞入图片！")
                        
                    except Exception as popup_e:
                        print(f"⚠️ 模拟弹窗拦截失败，降级使用底层强塞法: {popup_e}")
                        
                        # 方案 B：降级方案（必须加上 .first 防止严格模式报错）
                        file_input = page.locator("input[type='file']").first
                        await file_input.set_input_files(images)
                        # 尝试唤醒前端框架
                        await file_input.evaluate("node => node.dispatchEvent(new Event('change', { bubbles: true }))")
                        print("🚀 已通过 Input 强塞法提交图片！")

                    print("⏳ 文件已提交给浏览器，正在监控页面编辑框是否出现...")
                    
                    # 监控标题框出现，作为图片上传完成的标志
                    title_locator = page.locator("input[placeholder*='标题'], .c-input_inner").first
                    await title_locator.wait_for(state="visible", timeout=45000) # 时间稍微给长一点
                    print("✅ 成功进入图文编辑状态！")
                    
                except Exception as e:
                    print(f"❌ 图片上传大阶段失败: {e}")
                    await page.screenshot(path="error_upload.png")
                    await browser.close()
                    return {"success": False, "message": f"图片上传失败: {str(e)}"}

                # 填写标题
                print("⏳ 正在填写标题...")
                try:
                    # 用多个常见特征联合定位，总有一个能中
                    title_locator = page.locator("input[placeholder*='标题'], input[class*='title'], .c-input_inner").first
                    await title_locator.wait_for(state="visible", timeout=10000)
                    
                    await title_locator.click() # 先点一下，激活输入框
                    await title_locator.fill(title)
                    print("✅ 标题填写成功！")
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"❌ 找不到标题框: {e}")
                await asyncio.sleep(1)

                # 填写正文内容
                try:
                    # 找网页上允许编辑的那个富文本框
                    content_locator = page.locator("[contenteditable='true'], textarea, .ql-editor").first
                    await content_locator.wait_for(state="visible", timeout=10000)
                    
                    await content_locator.click() # 必须先点一下，让光标在里面闪烁
                    
                    # 不要用 locator.fill()，改用 page.keyboard.type 模拟真实的物理键盘敲击，有些前端框架对直接赋值不敏感
                    await page.keyboard.type(content, delay=50) 
                    
                    print("✅ 正文填写成功！")
                    await asyncio.sleep(2)
                except Exception as e:
                    print(f"❌ 找不到正文框: {e}")

                # 点击发布
                print("⏳ 准备点击发布...")
                publish_btn = page.locator("button:has-text('发布')").first
                await publish_btn.click() 
                print("✅ 已点击发布按钮！等待发布结果...")

                await asyncio.sleep(10)
                await browser.close()
                return {
                    "success": True,
                    "message": "发布流程已完成，浏览器已关闭！请前往小红书 App 查看发布结果。"
                }

            except Exception as e:
                print(f"❌ 自动化点击出错: {e}")
                await page.screenshot(path="data/error/error_publish.png")
                await browser.close()
                return {
                    "success": False, 
                    "message": f"发布失败,请查看error_publish.png。错误详情： {str(e)}"
                    }
            
            
        return {"success": True, "message": "Python 适配版：自动化发布流程跑通！"}
    except Exception as e:
        return {"success": False, "message": f"发布异常: {str(e)}"}

if __name__ == "__main__":
    print("🚀 启动 Python 版小红书 MCP 服务，监听 18060 端口...")
    # 使用 SSE 协议监听，对接前端
    mcp.run(transport="sse")