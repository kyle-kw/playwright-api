# -*- coding:utf-8 -*-

# @Time   : 2023/10/30 15:33
# @Author : huangkewei


from loguru import logger
from threading import Condition
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from master import q_thread, Task
from pipe import create_process_pipe
from models import APIRequestModel
from exception import TimeoutException

from env import OPEN_SENTRY, SENTRY_NSD

if OPEN_SENTRY:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_NSD,
        traces_sample_rate=1.0,
    )

app = FastAPI()


@app.exception_handler(HTTPException)
def http_exception_handler(request, exc):
    logger.error(exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})


@app.get("/ping")
def ping():
    return "PONG"


@app.post("/get-content")
def get_content(api_req: APIRequestModel):
    # 创建任务
    p_pipe, c_pipe = create_process_pipe()
    cond = Condition()
    task = Task(pipe=c_pipe, cond=cond, flag=0)
    q_thread.put(task)

    # 发送具体任务
    task.cond.acquire()
    p_pipe.send(api_req)
    task.cond.notify()
    task.flag = 1
    task.cond.release()
    logger.info('发送具体任务')

    data = p_pipe.recv(api_req.timeout)
    if data is None:
        raise TimeoutException("请求超时！")
    elif isinstance(data, HTTPException):
        raise data

    logger.info('任务执行成功')

    return data
