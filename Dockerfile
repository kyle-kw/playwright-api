FROM mcr.microsoft.com/devcontainers/python:0-3.11

RUN apt-get update && \
    apt-get install -y dumb-init wget && \
    wget https://github.com/ginuerzh/gost/releases/download/v2.11.5/gost-linux-amd64-2.11.5.gz && \
    gzip -d gost-linux-amd64-2.11.5.gz && \
    mv gost-linux-amd64-2.11.5 /bin/gost && \
    pip install playwright && \
    playwright install --with-deps

RUN chmod +x /bin/gost

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src .

ENTRYPOINT ["dumb-init", "--", "python", "main.py"]

# docker build . -t ccr.ccs.tencentyun.com/zhongbiao/playwright-api:1.2.1
