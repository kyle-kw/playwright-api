# -*- coding:utf-8 -*-

# @Time   : 2023/10/30 15:33
# @Author : huangkewei


from loguru import logger
from threading import Condition
from flask import Flask, request
from master import q_thread, Task
from pipe import create_process_pipe
from models import APIRequestModel


app = Flask()


@app.get("/ping")
def ping():
    return "PONG"


@app.post("/get_content")
@app.post("/get_cookies")
def get_content():
    res_data = request.get_json()
    api_req = APIRequestModel.parse_raw(res_data)
    
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

    data = p_pipe.recv(int(api_req.gotoOptions.timeout / 1000))
    if data is None:
        raise Exception("请求超时！")
    elif isinstance(data, Exception):
        raise data

    logger.info('任务执行成功')

    return data
