import os
from datetime import datetime


LOG_DIR = "./log"


def write_log(event, msg):
    os.makedirs(LOG_DIR, exist_ok=True)

    now = datetime.now()

    filename = now.strftime("%Y%m%d_%H") + ".log"
    filepath = os.path.join(LOG_DIR, filename)

    log_time = now.strftime("%Y-%m-%d %H:%M:%S")

    line = f"[{log_time}] [{event}] {msg}\n"

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(line)

def write_error(msg):
    os.makedirs(LOG_DIR, exist_ok=True)

    now = datetime.now()

    filename = "error_" + now.strftime("%Y%m%d") + ".log"
    filepath = os.path.join(LOG_DIR, filename)

    line = f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(line)
        