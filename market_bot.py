import time
from datetime import datetime

from ai_strategy import make_balance_info, ai_strategy
from indicator import calc_ma, calc_rsi
from logger import write_log, write_error


def print_balance(balance):
    print()
    print("========== 나의 자산 ==========")
    print("총평가금액     :", balance["total"], "원")
    print("예수금         :", balance["cash"], "원")
    print("주문가능금액   :", balance["orderable_cash"], "원")
    print("보유수량       :", balance["holding_qty"], "주")
    print("==============================")


def safe_order(api, action, code, name, qty, price):
    try:
        if qty <= 0:
            print("주문 수량이 0 이하입니다. 주문하지 않습니다.")
            return False

        if action == "BUY":
            result = api.buy(code, qty, price)
            log_event = "BUY"
            log_msg = f"{name}({code}) {qty}주 {price}원 매수 성공"

        elif action == "SELL":
            result = api.sell(code, qty, price)
            log_event = "SELL"
            log_msg = f"{name}({code}) {qty}주 {price}원 매도 성공"

        else:
            print("주문 없음")
            return True

        if result.get("rt_cd") == "0":
            print("주문 성공")
            write_log(log_event, log_msg)
            return True

        print("주문 실패:", result)
        return False

    except Exception as e:
        print("주문 중 예외 발생:", e)
        return False


def run_once(api, config):
    code = config["stock_code"]
    name = config.get("stock_name", code)
    buy_amount = int(config.get("buy_amount", 1000000))
    simulation_mode = bool(config.get("simulation_mode", True))

    print()
    print("========== 장중 자동매매 실행 ==========")
    print("시간:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    try:
        price_info = api.get_price(code)
        price = price_info["price"]

        print()
        print("========== 현재가 조회 ==========")
        print("종목명     :", name)
        print("현재가     :", price, "원")
        print("전일대비   :", price_info["diff"])
        print("등락률     :", price_info["rate"], "%")
        print("===============================")

    except Exception as e:
        print("현재가 조회 실패:", e)
        return

    time.sleep(1)

    try:
        raw_balance = api.get_balance()
        balance = make_balance_info(raw_balance, code)
        print_balance(balance)

    except Exception as e:
        print("잔고 조회 실패:", e)
        return

    time.sleep(1)

    try:
        daily_prices = api.get_daily_prices(code, days=100)

        ma20 = calc_ma(daily_prices, 20)
        ma60 = calc_ma(daily_prices, 60)
        rsi = calc_rsi(daily_prices, 14)

        print()
        print("========== 기술 지표 ==========")
        print("MA20 :", round(ma20, 2) if ma20 else "-")
        print("MA60 :", round(ma60, 2) if ma60 else "-")
        print("RSI  :", round(rsi, 2) if rsi else "-")
        print("==============================")

        signal = ai_strategy(
            price,
            balance,
            buy_amount,
            ma20=ma20,
            ma60=ma60,
            rsi=rsi,
        )
        
        print()
        print("========== AI 전략 판단 ==========")
        print("판단       :", signal["action"])
        print("수량       :", signal["qty"])
        print("가격       :", signal["price"])
        print("신뢰도     :", str(signal.get("confidence", 0)) + "%")
        print("이유       :", signal["reason"])
        print("=================================")

    except Exception as e:
        print("전략 판단 실패:", e)
        return

    time.sleep(1)

    if simulation_mode:
        print("SIMULATION 모드입니다. 실제 주문은 실행하지 않습니다.")
        return

    safe_order(
        api=api,
        action=signal["action"],
        code=code,
        name=name,
        qty=int(signal["qty"]),
        price=int(signal["price"]),
    )