FROM mcr.microsoft.com/devcontainers/python:0-3.11

RUN pip install playwright && \
    playwright install --with-deps

WORKDIR /app
COPY requirements.txt .

RUN pip install -r requirements.txt

RUN pip install pjstealth

COPY src .

ENTRYPOINT ["python", "main.py"]

# docker build . -t ccr.ccs.tencentyun.com/zhongbiao/playwright-api:1.0.0
# 1