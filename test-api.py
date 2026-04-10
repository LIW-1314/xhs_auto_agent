import asyncio
from openai import AsyncOpenAI
from app.core.config import settings

async def test():
    print(f"使用的 URL: {settings.openai_base_url}")
    print(f"使用的 Key: {settings.openai_api_key[:10]}...")  # 只显示前10个字符，保护密钥安全
    
    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url
    )
    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": "测试"}],
            max_tokens=10
        )
        print("✅ 测试成功！API 返回：", response.choices[0].message.content)
    except Exception as e:
        print("❌ 测试失败：", str(e))

asyncio.run(test())