
import os
import threading
import multiprocessing
from uuid import uuid1
from loguru import logger
from playwright.sync_api import Page

from utils import api_request_to_pw_api, req_res_to_api_res
from headless_playwright import PlaywrightHandler
from pipe import ChildPipe, create_process_pipe
from models import APIRequestModel, APIResponseModel, PlaywrightAPI

class Worker:
    def __init__(self, c_pipe: ChildPipe):
        self.c_pipe = c_pipe
        self.session_id = None
        self.pw: PlaywrightHandler= None
        self.page: Page= None

    def destroy(self):
        """
        清理浏览器资源
        """
        if self.pw:
            self.pw.close_page(self.page)
            self.pw.close_context()
            self.pw.close_browser()

    def send_message(self, res_msg: APIResponseModel):
        """
        往管道中发送信息
        """
        self.c_pipe.send(res_msg)

    def execute(self, req: APIRequestModel) -> APIResponseModel:
        """
        执行接收过来的信息
        """

        logger.info('子进程开始执行请求任务。')
        pw_api = api_request_to_pw_api(req)
        if not self.pw:
            self.pw = PlaywrightHandler()
        req_data = self.pw.goto_the_url(page=self.page, **dict(pw_api))
        self.page = self.pw.page
        api_res = req_res_to_api_res(req_data)
        
        return api_res

    def worker_watch_dog(self):
        """
        检测conn管道信息
        """
        while True:
            data: APIRequestModel = self.c_pipe.recv()
            if data is None:
                continue

            if data == 'kill':
                self.destroy()
                break

            logger.info('子进程获取到请求任务。')
            res_data = self.execute(data)
            self.send_message(res_data)

    def watch_dog(self):
        t = threading.Thread(target=self.worker_watch_dog)
        t.start()
        logger.info('子进程开始监测管道信息。')

    def __del__(self):
        if self.pw:
            self.pw.close_page(self.page)
            self.pw.close_context()
            self.pw.close_browser()


def create_worker(c_pipe: ChildPipe):
    # create one worker

    worker = Worker(c_pipe=c_pipe)
    # worker.watch_dog()
    worker.worker_watch_dog()

    return worker


def worker_test():
    json_data = {
        'url': 'https://sdbhgj.youzhicai.com/index/Notice.html?id=2ed513c0-bc27-45ed-8d82-a200d52f54f7&n=1'
    }
    api_res = APIRequestModel(**json_data)

    p_pipe, c_pipe = create_process_pipe()

    task = multiprocessing.Process(target=create_worker, args=(c_pipe,))
    task.start()

    p_pipe.send(api_res)
    while True:
        data = p_pipe.recv()
        if data is not None:
            break
    print(data)

    p_pipe.send('kill')


if __name__ == '__main__':
    worker_test()
