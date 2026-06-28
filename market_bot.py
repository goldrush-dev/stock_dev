import time
import random
from datetime import datetime

from ai_strategy import make_balance_info, ai_strategy
from indicator import calc_ma, calc_rsi
from logger import write_log


last_status_log_hour = {}


def print_balance(balance):
    print()
    print("========== 나의 자산 ==========")
    print("총평가금액     :", f"{balance['total']:,}", "원")
    print("예수금         :", f"{balance['cash']:,}", "원")
    print("D+1 예수금     :", f"{balance['d1_cash']:,}", "원")
    print("D+2 예수금     :", f"{balance['d2_cash']:,}", "원")
    print("주문가능금액   :", f"{balance['orderable_cash']:,}", "원")
    print("보유수량       :", f"{balance['holding_qty']:,}", "주")
    print("==============================")


def safe_order(api, action, code, name, qty, price):
    try:
        if qty <= 0:
            print("주문 수량이 0 이하입니다. 주문하지 않습니다.")
            return False

        if action == "BUY":
            result = api.buy(code, qty, price)
            log_event = "BUY"
            log_msg = f"{name}({code}) {qty}주 {price:,}원 매수 성공"

        elif action == "SELL":
            result = api.sell(code, qty, price)
            log_event = "SELL"
            log_msg = f"{name}({code}) {qty}주 {price:,}원 매도 성공"

        else:
            print("주문 없음")
            return False

        if result.get("rt_cd") == "0":
            print("주문 성공")
            write_log(log_event, log_msg)
            return True

        print("주문 실패:", result)
        return False

    except Exception as e:
        print("주문 중 예외 발생:", e)
        return False


def _resolve_stock(config, stock=None):
    if stock is None:
        default_buy_amount = int(config.get("default_buy_amount", config.get("buy_amount", 1000000)))
        return {
            "code": str(config["stock_code"]),
            "name": str(config.get("stock_name", config["stock_code"])),
            "buy_amount": default_buy_amount,
        }

    default_buy_amount = int(config.get("default_buy_amount", config.get("buy_amount", 1000000)))
    code = stock.get("code") or stock.get("stock_code")
    name = stock.get("name") or stock.get("stock_name") or code
    buy_amount = int(stock.get("buy_amount", default_buy_amount))

    return {
        "code": str(code),
        "name": str(name),
        "buy_amount": buy_amount,
    }


def get_cached_indicators(api, code, indicator_cache):
    today = datetime.now().strftime("%Y-%m-%d")
    cached = indicator_cache.get(code)

    if cached and cached.get("date") == today:
        print("기술지표 캐시 사용")
        return cached["ma20"], cached["ma60"], cached["rsi"]

    print("기술지표 신규 계산")
    daily_prices = api.get_daily_prices(code, days=100)

    ma20 = calc_ma(daily_prices, 20)
    ma60 = calc_ma(daily_prices, 60)
    rsi = calc_rsi(daily_prices, 14)

    indicator_cache[code] = {
        "date": today,
        "ma20": ma20,
        "ma60": ma60,
        "rsi": rsi,
    }

    return ma20, ma60, rsi


def run_once(api, config, stock=None, raw_balance=None, indicator_cache=None):
    stock = _resolve_stock(config, stock)

    code = stock["code"]
    name = stock["name"]
    buy_amount = int(stock["buy_amount"])
    simulation_mode = bool(config.get("simulation_mode", True))

    if indicator_cache is None:
        indicator_cache = {}

    print()
    print("========== 장중 자동매매 실행 ==========")
    print("시간          :", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("종목          :", name, code)
    print("1회 매수한도  :", f"{buy_amount:,}", "원")

    try:
        price_info = api.get_price(code)
        price = price_info["price"]

        print()
        print("========== 현재가 조회 ==========")
        print("종목명     :", name)
        print("현재가     :", f"{price:,}", "원")
        print("전일대비   :", price_info["diff"])
        print("등락률     :", price_info["rate"], "%")
        print("===============================")

    except Exception as e:
        print("현재가 조회 실패:", e)
        return "ERROR"

    time.sleep(random.uniform(1.0, 1.8))

    try:
        # 핵심: main에서 넘겨준 잔고를 재사용. 없을 때만 조회.
        if raw_balance is None:
            raw_balance = api.get_balance()

        balance = make_balance_info(raw_balance, code)
        print_balance(balance)

    except Exception as e:
        print("잔고 처리 실패:", e)
        return "ERROR"

    time.sleep(random.uniform(1.0, 1.8))

    try:
        # 핵심: 일봉/지표는 종목별 하루 1회만 조회/계산
        cache = indicator_cache[code]
        ma20 = cache["ma20"]
        ma60 = cache["ma60"]
        rsi = cache["rsi"]
        #ma20, ma60, rsi = get_cached_indicators(api, code, indicator_cache)

        print()
        print("========== 기술 지표 ==========")
        print("MA20 :", round(ma20, 2) if ma20 is not None else "-")
        print("MA60 :", round(ma60, 2) if ma60 is not None else "-")
        print("RSI  :", round(rsi, 2) if rsi is not None else "-")
        print("==============================")

        signal = ai_strategy(
            price,
            balance,
            buy_amount,
            avg_buy_price=balance.get("avg_buy_price", 0),
            ma20=ma20,
            ma60=ma60,
            rsi=rsi,
        )

        print()
        print("========== AI 전략 판단 ==========")
        print("판단       :", signal["action"])
        print("수량       :", signal["qty"])
        print("가격       :", f"{int(signal['price']):,}")
        print("신뢰도     :", str(signal.get("confidence", 0)) + "%")
        print("이유       :", signal["reason"])
        print("=================================")

        ma20_txt = round(ma20, 2) if ma20 is not None else "-"
        ma60_txt = round(ma60, 2) if ma60 is not None else "-"
        rsi_txt = round(rsi, 2) if rsi is not None else "-"

        summary = (
            f"{name}({code}) "
            f"현재가={price:,}, "
            f"보유={balance['holding_qty']}주, "
            f"총자산={balance['total']:,}, "
            f"예수금={balance['cash']:,}, "
            f"D+1={balance['d1_cash']:,}, "
            f"D+2={balance['d2_cash']:,}, "
            f"주문가능={balance['orderable_cash']:,}, "
            f"1회매수한도={buy_amount:,}, "
            f"MA20={ma20_txt}, "
            f"MA60={ma60_txt}, "
            f"RSI={rsi_txt}, "
            f"판단={signal['action']}, "
            f"이유={signal['reason']}"
        )

        current_hour = datetime.now().hour

        if signal["action"] in ("BUY", "SELL"):
            write_log("SIGNAL", summary)
        elif last_status_log_hour.get(code) != current_hour:
            write_log("STATUS", summary)
            last_status_log_hour[code] = current_hour

    except Exception as e:
        print("전략 판단 실패:", e)
        return "ERROR"

    time.sleep(random.uniform(1.0, 1.8))

    if simulation_mode:
        print("SIMULATION 모드입니다. 실제 주문은 실행하지 않습니다.")
        return signal["action"]

    ordered = safe_order(
        api=api,
        action=signal["action"],
        code=code,
        name=name,
        qty=int(signal["qty"]),
        price=int(signal["price"]),
    )

    if ordered:
        return signal["action"]

    return "HOLD"
