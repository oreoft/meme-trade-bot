FROM python:3.11-slim

WORKDIR /app

# 设置时区和系统依赖
ENV TZ=Asia/Shanghai
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock .
RUN pip install uv && uv pip install --system --no-cache -r requirements.lock

COPY . .

EXPOSE 8000

CMD ["python", "main.py"]
