FROM mcr.microsoft.com/devcontainers/python:0-3.11

RUN pip install playwright && \
    playwright install --with-deps

RUN apt-get update && \
    apt-get install -y dumb-init

COPY gost /opt
ENV PATH=/opt:$PATH

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src .

ENTRYPOINT ["dumb-init", "--", "python", "main.py"]

# docker build . -t ccr.ccs.tencentyun.com/zhongbiao/playwright-api:1.2.1
