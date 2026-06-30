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

    output1 = raw.get("output1", [])
    output2 = raw.get("output2", [{}])[0]

    cash = to_int(output2.get("dnca_tot_amt"))
    orderable_cash = to_int(output2.get("ord_psbl_cash"))
    usable_cash = orderable_cash
    if usable_cash <= 0:
        usable_cash = cash
    total_asset = to_int(output2.get("tot_evlu_amt"))

    d1_cash = to_int(output2.get("nxdy_excc_amt"))
    d2_cash = to_int(output2.get("prvs_rcdl_excc_amt"))

    print()
    print("============================================================")
    print("                    계좌 요약")
    print("============================================================")
    print(f"총자산          : {total_asset:>15,} 원")
    print(f"예수금          : {cash:>15,} 원")
    print(f"주문가능금액    : {usable_cash:>15,} 원")
    print(f"D+1 예수금      : {d1_cash:>15,} 원")
    print(f"D+2 예수금      : {d2_cash:>15,} 원")
    print("============================================================")

    if not output1:
        print()
        print("보유 종목이 없습니다.")
        return

    print()
    print("============================================================")
    print("                     보유 종목")
    print("============================================================")

    total_buy = 0
    total_eval = 0
    total_profit = 0

    for item in output1:

        code = item.get("pdno", "")
        name = item.get("prdt_name", "")

        qty = to_int(item.get("hldg_qty"))
        avg_price = to_int(item.get("pchs_avg_pric"))
        current_price = to_int(item.get("prpr"))

        buy_amount = to_int(item.get("pchs_amt"))
        eval_amount = to_int(item.get("evlu_amt"))
        profit = to_int(item.get("evlu_pfls_amt"))

        profit_rate = (
            profit / buy_amount * 100
            if buy_amount > 0 else 0
        )

        total_buy += buy_amount
        total_eval += eval_amount
        total_profit += profit

        print(f"종목명      : {name} ({code})")
        print(f"보유수량    : {qty:,} 주")
        print(f"평균단가    : {avg_price:,} 원")
        print(f"현재가      : {current_price:,} 원")
        print(f"매수금액    : {buy_amount:,} 원")
        print(f"평가금액    : {eval_amount:,} 원")
        print(f"평가손익    : {profit:,} 원")
        print(f"수익률      : {profit_rate:.2f} %")
        print("------------------------------------------------------------")

    total_rate = (
        total_profit / total_buy * 100
        if total_buy > 0 else 0
    )

    print()
    print("============================================================")
    print("                   보유 종목 합계")
    print("============================================================")
    print(f"총 매수금액  : {total_buy:>15,} 원")
    print(f"총 평가금액  : {total_eval:>15,} 원")
    print(f"총 평가손익  : {total_profit:>15,} 원")
    print(f"총 수익률    : {total_rate:>14.2f} %")
    print("============================================================")


if __name__ == "__main__":
    main()