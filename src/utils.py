# -*- coding:utf-8 -*-

# @Time   : 2023/10/31 09:44
# @Author : huangkewei

import random
import socket
import json
import hashlib
import psutil

from loguru import logger

from models import APIRequestModel, APIResponseModel, PlaywrightAPI



def api_request_to_pw_api(req: APIRequestModel) -> PlaywrightAPI:
    # 根据信息转换为PlaywrightAPI

    json_data = {
        'url': str(req.url),
        'user_agent': req.user_agent,
        'cookies': req.cookies,
        'headers': req.headers,
        'proxy': req.request_proxy,
        'use_cache': req.cache_enabled,
        'save_stack': req.print_stack,
        'ignore_resource': req.ignore_resource,
        'wait_for_selector': req.select_expression,
        'exec_js': req.code,
        'exec_js_args': req.context or None,
        'sleep': req.sleep,
        'timeout': req.timeout,
    }

    pw_api = PlaywrightAPI(**json_data)

    return pw_api

def req_res_to_api_res(res: dict) -> APIResponseModel:

    json_data = {
        'msg': 'success' if res['content'] else 'err',
        'content': res['content'],
        'cookies': {d['name']:d['value'] for d in res['cookies']},
    }

    api_res = APIResponseModel(**json_data)

    return api_res

def generation_sub_md5(data: APIRequestModel) -> str:
    main_param = {
        'user_agent': data.user_agent,
        'cookies': data.cookies,
        'headers': data.headers,
        # 'proxy': data.request_proxy,
        'proxy': True if data.request_proxy else False,
        'use_cache': data.cache_enabled,
        'save_stack': data.print_stack,
        'ignore_resource': data.ignore_resource,
    }
    main_json = json.dumps(main_param)
    md5_string = hashlib.md5(main_json.encode('utf-8')).hexdigest()

    return md5_string


def get_unused_port():
    while True:
        port = random.randint(10000, 20000)  # 选择一个随机端口号
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('localhost', port))  # 尝试绑定到该端口
            sock.close()
            return port  # 绑定成功，返回该端口号
        except OSError:
            continue  # 端口已被占用，继续尝试下一个端口号


def check_pid_exist(pid):

    return psutil.pid_exists(pid=pid)


def kill_pid(pid):
    if not check_pid_exist(pid):
        return
    p = psutil.Process(pid)
    p.terminal()
    p.wait()


def worker_test_3():
    json_data = {
        'url': 'https://sdbhgj.youzhicai.com/index/Notice.html?id=2ed513c0-bc27-45ed-8d82-a200d52f54f7&n=1'
    }
    api_res = APIRequestModel(**json_data)
    # task = multiprocessing.Process(target=browser_request, args=(api_res, '132'))
    # task.start()
    # task.join()


if __name__ == '__main__':
    # render_html_test()
    worker_test_3()
