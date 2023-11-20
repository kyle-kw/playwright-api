
import uvicorn

from loguru import logger

from master import master_start
from app import app


HOST = '0.0.0.0'
PORT = 8000

def main():
    master_start()

    # 启动参数
    uvicorn.run(app, host=HOST, port=PORT)
    logger.info('主进程已启动')


if __name__ == '__main__':
    main()