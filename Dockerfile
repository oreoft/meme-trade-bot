FROM python:3.11-slim

WORKDIR /app

# 设置时区和系统依赖
ENV TZ=Asia/Shanghai
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 复制 uv 二进制文件到系统
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 设置 uv 环境变量
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# 先复制依赖文件并执行安装（利用 Docker 缓存层）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 复制整个项目
COPY . .

EXPOSE 8000

# 直接使用 uv 启动项目
CMD ["uv", "run", "python", "main.py"]
