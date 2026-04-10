import os
# 只读取系统底层环境变量，完全不加载 .env 文件
key = os.environ.get("OPENAI_API_KEY")
print(f"系统底层环境变量中的 Key 是: {key}")