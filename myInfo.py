import yaml
from kis_api import KisApi


def load_config(path="config_virtual.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def to_int(value):
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def main():
    config = load_config()

    api = KisApi(config)
    api.get_token()

    raw = api.get_balance()

    code = config["stock_code"]
    name = config.get("stock_name", code)

    output1 = raw.get("output1", [])
    output2 = raw.get("output2", [{}])[0]

    item = None
    for x in output1:
        if x.get("pdno") == code:
            item = x
            break

    cash = to_int(output2.get("dnca_tot_amt"))
    orderable_cash = to_int(output2.get("ord_psbl_cash"))
    total_asset = to_int(output2.get("tot_evlu_amt"))

    # 일부 API에서는 매도대금/정산예정금이 다른 필드에 들어갈 수 있음
    d1_cash = to_int(output2.get("nxdy_excc_amt"))
    d2_cash = to_int(output2.get("prvs_rcdl_excc_amt"))

    print()
    print("========== 내 계좌 요약 ==========")
    print(f"총자산          : {total_asset:,} 원")
    print(f"예수금          : {cash:,} 원")
    print(f"주문가능금액    : {orderable_cash:,} 원")
    print(f"D+1 추정 예수금 : {d1_cash:,} 원")
    print(f"D+2 추정 예수금 : {d2_cash:,} 원")
    print("=================================")

    if item:
        qty = to_int(item.get("hldg_qty"))
        avg_price = to_int(item.get("pchs_avg_pric"))
        buy_amount = to_int(item.get("pchs_amt"))
        current_price = to_int(item.get("prpr"))
        eval_amount = to_int(item.get("evlu_amt"))
        profit = to_int(item.get("evlu_pfls_amt"))

        if buy_amount > 0:
            profit_rate = profit / buy_amount * 100
        else:
            profit_rate = 0

        print()
        print("========== 보유 종목 ==========")
        print(f"종목명        : {name} ({code})")
        print(f"보유수량      : {qty:,} 주")
        print(f"평균매수가    : {avg_price:,} 원")
        print(f"현재가        : {current_price:,} 원")
        print()
        print(f"투입금액      : {buy_amount:,} 원")
        print(f"평가금액      : {eval_amount:,} 원")
        print(f"평가손익      : {profit:,} 원")
        print(f"수익률        : {profit_rate:.2f} %")
        print("==============================")
    else:
        print()
        print("========== 보유 종목 ==========")
        print(f"종목명        : {name} ({code})")
        print("보유수량      : 0 주")
        print("투입금액      : 0 원")
        print("평가금액      : 0 원")
        print("평가손익      : 0 원")
        print("수익률        : 0.00 %")
        print("==============================")


if __name__ == "__main__":
    main()