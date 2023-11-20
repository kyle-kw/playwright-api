import os
from loguru import logger


def get_env(env_name, default=None, required=False, arg_formatter=None):
    rv = os.getenv(env_name)
    if required and rv is None and default is None:
        raise ValueError("'{}' environment variable is required.".format(env_name))
    elif rv is None:
        rv = default
    if arg_formatter is not None:
        rv = arg_formatter(rv)

    logger.info("'{}' uses value: {}".format(env_name, rv))

    return rv


MAX_TASK_NUMBER = get_env('MAX_TASK_NUMBER', 1, arg_formatter=int)
PORT = get_env('PORT', 8000, arg_formatter=int)
MAX_TASK_LIVE_TIME = get_env('MAX_TASK_LIVE_TIME', 60 * 60, arg_formatter=int)
MAX_TASK_IDLE_TIME = get_env('MAX_TASK_IDLE_TIME', 60 * 20, arg_formatter=int)

OPEN_SENTRY = get_env("OPEN_SENTRY", "false")
SENTRY_NSD = get_env("SENTRY_NSD", "")
if OPEN_SENTRY.lower() == 'true':
    OPEN_SENTRY = True
else:
    OPEN_SENTRY = False
