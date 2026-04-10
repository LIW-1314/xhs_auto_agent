import sys
import asyncio

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import os
from dotenv import load_dotenv

# override=True 是核心！它的意思是：如果系统里有旧的变量，强行用 .env 里的替换掉它！
load_dotenv(override=True) 

# 打印出来验明正身，确认读到的是不是你期望的那个（确认无误后可以删掉这行）
print("当前使用的 API KEY 后四位:", os.getenv("OPENAI_API_KEY")[-4:] if os.getenv("OPENAI_API_KEY") else "未找到")

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)