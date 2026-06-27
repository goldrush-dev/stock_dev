import os
from datetime import datetime


LOG_DIR = "./log"


def write_log(event, msg):
    os.makedirs(LOG_DIR, exist_ok=True)

    now = datetime.now()

    # 하루에 하나의 로그 파일
    filename = now.strftime("%Y%m%d") + ".log"
    filepath = os.path.join(LOG_DIR, filename)

    line = f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] [{event}] {msg}\n"

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(line)


def write_error(event, msg=None):
    os.makedirs(LOG_DIR, exist_ok=True)

    now = datetime.now()

    filename = "error_" + now.strftime("%Y%m%d") + ".log"
    filepath = os.path.join(LOG_DIR, filename)

    if msg is None:
        line = f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] {event}\n"
    else:
        line = f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] [{event}] {msg}\n"

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(line)


def write_status(msg):
    write_log("STATUS", msg)


def write_signal(msg):
    write_log("SIGNAL", msg)

