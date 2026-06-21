import time
import yaml

from kis_api import KisApi
from ai_strategy import make_balance_info, ai_like_strategy


def load_config(path="config_virtual.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def print_config(config):
    print()
    print("========== 설정 정보 ==========")
    print("모드           :", config.get("mode"))
    print("URL            :", config.get("base_url"))
    print("계좌번호       :", config.get("cano"))
    print("계좌상품코드   :", config.get("acnt_prdt_cd"))
    print("종목           :", config.get("stock_name"), config.get("stock_code"))
    print("매수금액       :", config.get("buy_amount"))
    print("SIMULATION MODE :", config.get("simulation_mode"))
    print("==============================")


def print_balance(balance):
    print()
    print("========== 나의 자산 ==========")
    print("총평가금액     :", balance["total"], "원")
    print("예수금         :", balance["cash"], "원")
    print("주문가능금액   :", balance["orderable_cash"], "원")
    print("보유수량       :", balance["holding_qty"], "주")
    print("==============================")


def main():
    config = load_config("config_virtual.yaml")

    print_config(config)

    api = KisApi(config)
    api.get_token()

    code = config["stock_code"]
    name = config.get("stock_name", code)
    buy_amount = int(config.get("buy_amount", 1000000))
    simulation_mode = bool(config.get("simulation_mode", True))

    print()
    print("========== 자동매매 시작 ==========")
    print("종목:", name, code)
    print("===================================")

    price_info = api.get_price(code)
    price = price_info["price"]

    print()
    print("========== 현재가 조회 ==========")
    print("종목명     :", name)
    print("현재가     :", price, "원")
    print("전일대비   :", price_info["diff"])
    print("등락률     :", price_info["rate"], "%")
    print("===============================")

    time.sleep(1)

    raw_balance = api.get_balance()
    balance = make_balance_info(raw_balance, code)
    print_balance(balance)

    time.sleep(1)

    signal = ai_like_strategy(price, balance, buy_amount)

    print()
    print("========== AI 전략 판단 ==========")
    print("판단       :", signal["action"])
    print("수량       :", signal["qty"])
    print("가격       :", signal["price"])
    print("신뢰도     :", str(signal["confidence"]) + "%")
    print("이유       :", signal["reason"])
    print("=================================")

    time.sleep(1)

    if simulation_mode:
        print()
        print("SILMULATION 모드입니다. 실제 주문은 실행하지 않습니다.")
        return

    if signal["action"] == "BUY":
        api.buy(code, signal["qty"], signal["price"])
    elif signal["action"] == "SELL":
        api.sell(code, signal["qty"], signal["price"])
    else:
        print("주문 없음")

    time.sleep(1)

    print()
    print("========== 주문 후 잔고 ==========")
    raw_balance = api.get_balance()
    balance = make_balance_info(raw_balance, code)
    print_balance(balance)


if __name__ == "__main__":
    main()