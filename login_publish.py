import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        # 打开带界面的浏览器
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print("⏳ 正在打开小红书创作者中心...")
        await page.goto("https://creator.xiaohongshu.com/")
        print("👉 请在弹出的浏览器中，使用小红书 App 扫码登录。")

        # 程序暂停，等你扫码
        input("⚠️ 扫码登录成功，并且看到创作者后台完全加载出来后，请在这里按【回车键】继续...")

        # 将专门针对创作者中心的登录状态保存下来
        state_path = "data/raw/creator_state.json"
        await context.storage_state(path=state_path)
        print(f"✅ 完美！创作者中心登录凭证已保存至: {state_path}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())