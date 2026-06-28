import time
import yaml
from datetime import datetime, time as dtime

from kis_api import KisApi
from market_bot import run_once
from logger import write_log, write_error
from indicator import calc_ma, calc_rsi


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


# 종목별 일봉/지표 캐시
# key: stock_code
# value: {"date": "YYYY-MM-DD", "ma20": ..., "ma60": ..., "rsi": ...}
indicator_cache = {}


def load_config(path="config_virtual.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_stocks(config):
    """
    새 구조:
      default_buy_amount: 5000000
      stocks:
        - code: "005930"
          name: "삼성전자"
          buy_amount: 5000000
        - code: "000660"
          name: "SK하이닉스"

    기존 구조도 지원:
      stock_code: "005930"
      stock_name: "삼성전자"
      buy_amount: 5000000
    """
    default_buy_amount = int(config.get("default_buy_amount", config.get("buy_amount", 1000000)))

    stocks = config.get("stocks")
    if stocks:
        result = []
        for stock in stocks:
            code = stock.get("code") or stock.get("stock_code")
            if not code:
                continue

            name = stock.get("name") or stock.get("stock_name") or code
            buy_amount = int(stock.get("buy_amount", default_buy_amount))
            enabled = stock.get("enabled", stock.get("enable", True))

            if enabled is False:
                continue

            result.append({
                "code": str(code),
                "name": str(name),
                "buy_amount": buy_amount,
            })
        return result

    return [{
        "code": str(config["stock_code"]),
        "name": str(config.get("stock_name", config["stock_code"])),
        "buy_amount": default_buy_amount,
    }]


def get_market_state():
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    if now.weekday() >= 5:
        return "WEEKEND", 3600

    if today in HOLIDAYS:
        return "HOLIDAY", 3600

    now_time = now.time()

    if MARKET_START <= now_time <= MARKET_END:
        return "MARKET", 60

    if ACTIVE_START <= now_time <= ACTIVE_END:
        return "OFF_MARKET", 60

    return "OFF_MARKET", 1800


def print_config(config, stocks):
    print()
    print("========== 설정 정보 ==========")
    print("모드           :", config.get("mode"))
    print("URL            :", config.get("base_url"))
    print("계좌번호       :", config.get("cano"))
    print("계좌상품코드   :", config.get("acnt_prdt_cd"))
    print("SIMULATION MODE:", config.get("simulation_mode"))
    print("등록 종목 수   :", len(stocks))
    print("---------- 등록 종목 ----------")
    for idx, stock in enumerate(stocks, start=1):
        print(
            f"{idx}. {stock['name']} {stock['code']} "
            f"/ 1회 매수한도 {stock['buy_amount']:,} 원"
        )
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


def safe_get_balance(api):
    try:
        return api.get_balance()
    except Exception as e:
        print("잔고 조회 실패:", e)
        write_error("BALANCE_ERROR", str(e))
        return None


def main():
    config = load_config("config_virtual.yaml")
    stocks = get_stocks(config)

    print_config(config, stocks)

    api = KisApi(config)
    safe_get_token(api)

    print()
    print("========== 기술지표 초기 생성 ==========")

    for stock in stocks:
        try:
            code = stock["code"]

            print(f"{stock['name']} ({code})")

            daily = api.get_daily_prices(code, days=100)

            indicator_cache[code] = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "ma20": calc_ma(daily, 20),
                "ma60": calc_ma(daily, 60),
                "rsi": calc_rsi(daily, 14),
            }

        except Exception as e:
            write_error("INIT_INDICATOR_ERROR", f"{stock['name']}({code}) {e}")
            print(f"{stock['name']} 초기 지표 생성 실패:", e)

    print("기술지표 캐시 생성 완료.")

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
            print("등록종목 :", len(stocks), "개")
            print("==============================")

            if state == "MARKET":
                # 핵심: 잔고 조회는 전체 루프에서 1회만 실행
                raw_balance = safe_get_balance(api)
                if raw_balance is None:
                    print("잔고 조회 실패로 이번 회차 전체를 건너뜁니다.")
                    time.sleep(sleep_sec)
                    continue

                for idx, stock in enumerate(stocks, start=1):
                    try:
                        print()
                        print(f"[DEBUG] run_once 시작 ({idx}/{len(stocks)}) {stock['name']}({stock['code']})")

                        result = run_once(
                            api=api,
                            config=config,
                            stock=stock,
                            raw_balance=raw_balance,
                            indicator_cache=indicator_cache,
                        )

                        print(f"[DEBUG] run_once 종료 ({idx}/{len(stocks)}) {stock['name']}({stock['code']})")

                        # 주문이 실제 발생했다면 잔고가 바뀔 수 있으므로 한 번 갱신
                        if result in ("BUY", "SELL"):
                            print("주문 발생. 다음 종목 처리를 위해 잔고를 다시 조회합니다.")
                            time.sleep(3)
                            new_balance = safe_get_balance(api)
                            if new_balance is not None:
                                raw_balance = new_balance

                        # 여러 종목 조회 시 API 초당 제한 방지
                        time.sleep(2.5)

                    except Exception as e:
                        print("market_bot 오류:", e)
                        write_error("MARKET_BOT_ERROR", f"{stock['name']}({stock['code']}) {e}")
                        print("이번 종목은 건너뛰고 다음 종목으로 진행합니다.")
            else:
                print("장외/주말/공휴일입니다. 실행하지 않습니다.")

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
