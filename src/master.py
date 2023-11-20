
import time
import queue
import random
import threading
import multiprocessing

from threading import Event, Condition
from uuid import uuid1
from typing import Dict
from dataclasses import dataclass
from loguru import logger

from utils import generation_sub_md5
from worker import create_worker
from pipe import ChildPipe, create_process_pipe
from models import APIRequestModel, APIResponseModel
from env import MAX_TASK_NUMBER, MAX_TASK_LIVE_TIME, MAX_TASK_IDLE_TIME
from exception import InternalException, TimeoutException, HTTPException


q_thread = queue.Queue(maxsize=MAX_TASK_NUMBER)


class TaskState:
    busy = 'busy'
    idle = 'idle'
    with_destroyed = 'with-destroyed'
    destroyed = 'destroyed'
    all_state = ['busy', 'idle', 'with-destroyed', 'destroyed']


@dataclass
class Task:
    pipe: ChildPipe
    cond: Condition
    flag: int


@dataclass
class SubprocessInfo:
    task_id: str
    task: multiprocessing.Process
    pipe: ChildPipe
    task_state: str
    task_md5: str
    create_time: int
    update_time: int


class Master:
    def __init__(self):
        self.max_task_number = MAX_TASK_NUMBER
        self.max_task_live = MAX_TASK_LIVE_TIME
        self.max_task_idle = MAX_TASK_IDLE_TIME

        self.subprocess_num = 0
        self.subprocess_lst: Dict[str, SubprocessInfo] = {}  # 保留子线程的任务
        self.thread_lock = threading.RLock()
        self.thread_lock2 = threading.Lock()

        self.thread_num = 0
        self.thread_info = {}

        self.manager_thread = None
        self.watch_thread = None

    def create_subprocess(self, task_id=None):
        """
        创建子进程，并记录子进程信息
        """
        p_pipe, c_pipe = create_process_pipe()

        task = multiprocessing.Process(target=create_worker, args=(c_pipe,))
        task.start()

        with self.thread_lock:
            task_id = task_id or str(uuid1())
            self.subprocess_lst[task_id] = SubprocessInfo(
                task_id=task_id,
                task=task,
                pipe=p_pipe,
                task_state=TaskState.idle,
                task_md5=None,
                create_time=int(time.time()),
                update_time=int(time.time())
            )
            self.subprocess_num = len(self.subprocess_lst)

        return self.subprocess_lst[task_id]

    def update_subprocess_status(self, task_id, task_state: str):

        with self.thread_lock:
            if task_id not in self.subprocess_lst or task_state not in TaskState.all_state:
                return False

            self.subprocess_lst[task_id].task_state = task_state
            self.subprocess_lst[task_id].update_time = int(time.time())

    def _manager_subprocess(self):
        # 管理子进程
        with self.thread_lock:
            for task_id, task_info in self.subprocess_lst.items():
                # 若进程已不存活，且没有标记删除。更新状态删除。
                if not task_info.task.is_alive() and task_info.task_state != TaskState.destroyed:
                    logger.info(f'子进程 {task_info.task.pid} 不存活，标记删除。')
                    self.update_subprocess_status(task_id, TaskState.destroyed)
                    continue

                # 若进程已创建一个小时或20分钟未使用，则标记删除。
                if ((task_info.create_time < int(time.time()) - self.max_task_live
                     or task_info.update_time < int(time.time()) - self.max_task_idle)
                        and task_info.task_state == TaskState.idle):
                    logger.info(f'子进程 {task_info.task.pid} 已过期，标记删除。')
                    self.update_subprocess_status(task_id, TaskState.with_destroyed)
                    continue

            # kill不存活的子进程
            # todo 为啥用两个标记删除？
            need_kill_id = [(task_id, task)
                            for task_id, task in self.subprocess_lst.items()
                            if task.task_state in [TaskState.destroyed, TaskState.with_destroyed]]

            if need_kill_id:
                for task_id, task_info in need_kill_id:
                    if task_info.task_state == TaskState.with_destroyed:
                        task_info.pipe.send('kill')
                        continue

                    task_info.task.kill()
                    self.subprocess_lst.pop(task_id, '')
                self.subprocess_num = len(self.subprocess_lst)

            is_not_usable = (
                    len([1 for _, t in self.subprocess_lst.items()
                         if t.task_state == TaskState.idle]) == 0
                    and self.subprocess_num < self.max_task_number
            )
            if not self.subprocess_lst or is_not_usable:
                self.create_subprocess()

            logger.info(f'subprocess_num: {self.subprocess_num}')

    def manager_subprocess(self):
        # 管理子进程
        while True:
            self._manager_subprocess()
            time.sleep(1)

    def get_one_alive_subprocess(self, timeout=30, task_md5=None):
        # 获取一个可用的子进程
        now = time.time()
        while time.time() < now + timeout:
            with self.thread_lock:
                for task_id, task_info in self.subprocess_lst.items():
                    if task_info.task_state == TaskState.idle and task_info.task_md5 in [task_md5, None]:
                        self.update_subprocess_status(task_id, TaskState.busy)
                        # 清空管道
                        while task_info.pipe.recv(0.01):
                            continue

                        return task_info

                for task_id, task_info in self.subprocess_lst.items():
                    if task_info.task_state == TaskState.idle:
                        task_info.pipe.send('kill')
                        task_info_ = self.create_subprocess(task_id=task_id)
                        return task_info_

            time.sleep(random.random() + 0.1)
        raise InternalException("获取子进程失败")
    
    def check_use_thread(self):
        with self.thread_lock2:
            if self.thread_num >= self.max_task_number:
                return False
            else:
                self.thread_num += 1
                return True

    def sub_thread(self, task: Task):
        now = time.time()

        check_status = False
        while (time.time() - now) < 10:
            check_status = self.check_use_thread()
            if check_status:
                break
            time.sleep(random.random() + 0.1)
        
        if not check_status:
            task.pipe.send(TimeoutException("线程等待超时"))
            return

        try:
            task.cond.acquire()
            if task.flag == 0:
                task.cond.wait()
            task.cond.release()
            data: APIRequestModel = task.pipe.recv(1)
            if not data:
                raise TimeoutException("线程接收超时")

            task_md5 = generation_sub_md5(data)
            # 执行data任务
            subprocess_info: SubprocessInfo = self.get_one_alive_subprocess(task_md5=task_md5, timeout=10)
            if (time.time() - now) >= data.timeout:
                raise TimeoutException("子线程已执行超时，不发送给子进程执行任务")

            real_timeout = data.timeout - (time.time() - now)
            data.timeout = real_timeout
            subprocess_info.pipe.send(data)
            if not subprocess_info.task_md5:
                subprocess_info.task_md5 = task_md5

            res: APIResponseModel = subprocess_info.pipe.recv(real_timeout+0.5)

            self.update_subprocess_status(subprocess_info.task_id, TaskState.idle)

            task.pipe.send(res)
        except Exception as e:
            try:
                task.pipe.send(e)
            except:
                pass
            
            logger.exception(e)
        finally:
            with self.thread_lock2:
                self.thread_num -= 1

    def execute(self, task: Task, timeout=30):
        """
        创建子线程，并传入Task
        """

        thread_task = threading.Thread(target=self.sub_thread, args=(task,))
        thread_task.start()

    def watch_dog(self):
        while True:
            task: Task = q_thread.get()
            logger.info('获取到api接口任务，准备执行任务。')
            self.execute(task)
    
    def daemon_thread(self):
        while True:
            if not self.manager_thread or not self.manager_thread.is_alive():
                manager_subprocess = threading.Thread(target=self.manager_subprocess)
                manager_subprocess.start()
                self.manager_thread = manager_subprocess
            
            if not self.watch_thread or not self.watch_thread.is_alive():
                watch_dog = threading.Thread(target=self.watch_dog)
                watch_dog.start()
                self.watch_thread = watch_dog
            
            time.sleep(1)

    def start(self):
        # 子进程管理
        manager_subprocess = threading.Thread(target=self.manager_subprocess)
        manager_subprocess.start()
        self.manager_thread = manager_subprocess

        watch_dog = threading.Thread(target=self.watch_dog)
        watch_dog.start()
        self.watch_thread = watch_dog

        daemon_task = threading.Thread(target=self.daemon_thread)
        daemon_task.setDaemon(True)
        daemon_task.start()

        logger.info('master 初始化完成。')


def master_start():
    master = Master()
    master.start()



