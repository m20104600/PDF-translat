FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# 安装系统依赖 (PDF 处理所需)
RUN apt-get update && \
    apt-get install --no-install-recommends -y libgl1 libglib2.0-0 libxext6 libsm6 libxrender1 build-essential && \
    rm -rf /var/lib/apt/lists/*

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PDF2ZH_UI_LANG=zh

# 复制 backend 代码
COPY backend /app/backend
WORKDIR /app/backend

# 安装 backend 开发模式并下载必要资源
RUN uv pip install --system --no-cache .
RUN pdf2zh --version

# 复制整个项目
WORKDIR /app
COPY . .

# 暴露端口 (WebUI: 7860, Custom API: 8000)
EXPOSE 7860 8000

# 默认启动命令 (可以通过更改 CMD 或 entrypoint 运行不同模式)
# 默认运行 WebUI
CMD ["python", "-m", "pdf2zh_next.main", "--gui"]
