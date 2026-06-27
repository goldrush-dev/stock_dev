import time
import yaml
from datetime import datetime, time as dtime

from kis_api import KisApi
from market_bot import run_once
from logger import write_log, write_error

HOLIDAYS = {
    "2026-01-01",
    "2026-02-16",
    "2026-02-17",
    "2026-02-18",
    "2026-03-01",
    "2026-05-05",
    "2026-06-06",
    "2026-08-15",
    "2026-09-24",
    "2026-09-25",
    "2026-09-26",
    "2026-10-03",
    "2026-10-09",
    "2026-12-25",
}

MARKET_START = dtime(9, 0)
MARKET_END = dtime(15, 30)

ACTIVE_START = dtime(8, 30)
ACTIVE_END = dtime(15, 40)


def load_config(path="config_virtual.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_market_state():
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    # 주말
    if now.weekday() >= 5:
        return "WEEKEND", 3600

    # 공휴일
    if today in HOLIDAYS:
        return "HOLIDAY", 3600

    now_time = now.time()

    if MARKET_START <= now_time <= MARKET_END:
        return "MARKET", 60

    if ACTIVE_START <= now_time <= ACTIVE_END:
        return "OFF_MARKET", 60

    return "OFF_MARKET", 1800


def print_config(config):
    print()
    print("========== 설정 정보 ==========")
    print("모드           :", config.get("mode"))
    print("URL            :", config.get("base_url"))
    print("계좌번호       :", config.get("cano"))
    print("계좌상품코드   :", config.get("acnt_prdt_cd"))
    print("종목           :", config.get("stock_name"), config.get("stock_code"))
    print("1회 매수한도   :", config.get("buy_amount"))
    print("SIMU1LATION MODE:", config.get("simulation_mode"))
    print("==============================")


def safe_get_token(api):
    while True:
        try:
            api.get_token()
            return True
        except Exception as e:
            print()
            print("토큰 발급 실패:", e)
            write_error("TOKEN_ERROR", str(e))
            print("60초 후 다시 시도합니다.")
            time.sleep(60)


def main():
    config = load_config("config_virtual.yaml")
    print_config(config)

    api = KisApi(config)
    safe_get_token(api)

    print()
    print("========== 자동매매 항시 실행 시작 ==========")

    prev_state = None

    while True:
        try:
            state, sleep_sec = get_market_state()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if prev_state != state:
                if prev_state != "MARKET" and state == "MARKET":
                    write_log("MARKET_OPEN", "장중 자동매매 시작")

                elif prev_state == "MARKET" and state == "OFF_MARKET":
                    write_log("MARKET_CLOSE", "장 종료. 자동매매 대기 전환")

                prev_state = state

            print()
            print("========== 상태 확인 ==========")
            print("현재시간 :", now)
            print("상태     :", state)
            print("대기시간 :", sleep_sec, "초")
            print("==============================")

            if state == "MARKET":
                try:
                    print("[DEBUG] run_once 시작")

                    run_once(api, config)

                    print("[DEBUG] run_once 종료")

                except Exception as e:
                    print("market_bot 오류:", e)
                    write_error("MARKET_BOT_ERROR", str(e))
                    print("이번 회차는 건너뛰고 계속 진행합니다.")
            else:
                print("장외 시간입니다. 실행하지 않습니다.")

            time.sleep(sleep_sec)

        except KeyboardInterrupt:
            print()
            print("사용자 종료 요청. 프로그램을 종료합니다.")
            break

        except Exception as e:
            print()
            print("main loop 오류:", e)
            write_error("MAIN_LOOP_ERROR", str(e))
            print("프로그램은 종료하지 않고 60초 후 계속 진행합니다.")
            time.sleep(60)


if __name__ == "__main__":
    main()