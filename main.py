import time
import yaml
from datetime import datetime, time as dtime

from kis_api import KisApi
from market_bot import run_once
from logger import write_log, write_error


MARKET_START = dtime(9, 0)
MARKET_FAST_START = dtime(15, 20)
MARKET_END = dtime(15, 30)


def load_config(path="config_virtual.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_market_state():
    now = datetime.now()

    if now.weekday() >= 5:
        return "WEEKEND", 1800

    now_time = now.time()

    if MARKET_START <= now_time < MARKET_FAST_START:
        return "MARKET", 5

    if MARKET_FAST_START <= now_time <= MARKET_END:
        return "CLOSE_WATCH", 1

    return "OFF_MARKET", 300


def print_config(config):
    print()
    print("========== 설정 정보 ==========")
    print("모드           :", config.get("mode"))
    print("URL            :", config.get("base_url"))
    print("계좌번호       :", config.get("cano"))
    print("계좌상품코드   :", config.get("acnt_prdt_cd"))
    print("종목           :", config.get("stock_name"), config.get("stock_code"))
    print("매수금액       :", config.get("buy_amount"))
    print("SIMULATION MODE:", config.get("simulation_mode"))
    print("==============================")


def safe_get_token(api):
    while True:
        try:
            api.get_token()
            return True
        except Exception as e:
            print()
            print("토큰 발급 실패:", e)
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

            # 상태가 바뀔 때만 로그 기록
            if prev_state != state:
                if state in ("MARKET", "CLOSE_WATCH"):
                    write_log("MARKET_OPEN", "장중 자동매매 시작")
                elif prev_state in ("MARKET", "CLOSE_WATCH") and state == "OFF_MARKET":
                    write_log("MARKET_CLOSE", "장 종료. 자동매매 대기 전환")

                prev_state = state

            print()
            print("========== 상태 확인 ==========")
            print("현재시간 :", now)
            print("상태     :", state)
            print("대기시간 :", sleep_sec, "초")
            print("==============================")

            if state in ("MARKET", "CLOSE_WATCH"):
                try:
                    run_once(api, config)
                except Exception as e:
                    print("market_bot 오류:", e)
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
            print("프로그램은 종료하지 않고 60초 후 계속 진행합니다.")
            time.sleep(60)


if __name__ == "__main__":
    main()