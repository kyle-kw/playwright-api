FROM mcr.microsoft.com/devcontainers/python:0-3.11

WORKDIR /app
COPY requirements.txt .

RUN pip install -r requirements.txt

RUN apt update && playwright install --with-deps

COPY src .

ENTRYPOINT ["python", "main.py"]

# docker build -f Dockerfile . -t ccr.ccs.tencentyun.com/zhongbiao/playwright-demo-new:1.0.0
