

from loguru import logger

from master import master_start
from app_v2 import app
from env import PORT
import flask


def main():
    master_start()

    # 启动参数
    app.run(host="0.0.0.0", port=PORT)
    logger.info('主进程已启动')


if __name__ == '__main__':
    import multiprocessing
    
    multiprocessing.set_start_method('spawn')
    main()
    
    