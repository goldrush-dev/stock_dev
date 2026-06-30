def make_balance_info(data, stock_code):
    output1 = data.get("output1", [])
    output2 = data.get("output2", [{}])[0]

    cash = int(output2.get("dnca_tot_amt", "0") or "0")
    total = int(output2.get("tot_evlu_amt", "0") or "0")
    orderable_cash = int(output2.get("ord_psbl_cash", "0") or "0")
    d1_cash = int(output2.get("nxdy_excc_amt", "0") or "0")
    d2_cash = int(output2.get("prvs_rcdl_excc_amt", "0") or "0")

    holding_qty = 0
    stock_name = "-"
    avg_buy_price = 0

    for item in output1:
        if item.get("pdno") == stock_code:
            holding_qty = int(item.get("hldg_qty", "0") or "0")
            stock_name = item.get("prdt_name", "-")
            avg_buy_price = int(float(item.get("pchs_avg_pric", "0") or "0"))

    return {
        "cash": cash,
        "total": total,
        "orderable_cash": orderable_cash,
        "holding_qty": holding_qty,
        "stock_name": stock_name,
        "items": output1,
        "avg_buy_price": avg_buy_price,

        "d1_cash": d1_cash,
        "d2_cash": d2_cash,
    }


def ai_strategy(price, balance, buy_amount, avg_buy_price=0, ma20=None, ma60=None, rsi=None, rsi_buy_min=35, rsi_buy_max=60):
    """
    모의투자용 기본 자동매매 전략

    매수:
    - 보유 수량 0
    - MA20 > MA60 상승추세
    - RSI rsi_buy_min~rsi_buy_max 반등 구간
    - buy_amount 만큼 매수

    매도:
    - 보유 수량 있음
    - 수익률 +3% 이상 익절
    - 수익률 -2% 이하 손절
    """

    holding_qty = int(balance.get("holding_qty", 0))
    #cash = int(balance.get("orderable_cash", balance.get("cash", 0)) or 0)
    orderable_cash = int(balance.get("orderable_cash", 0) or 0)
    cash_balance = int(balance.get("cash", 0) or 0)

    cash = orderable_cash if orderable_cash > 0 else cash_balance

    if ma20 is None or ma60 is None or rsi is None:
        return {
            "action": "HOLD",
            "qty": 0,
            "price": price,
            "reason": "지표 부족"
        }

    # 보유 중이면 익절/손절 판단
    if holding_qty > 0 and avg_buy_price > 0:
        profit_rate = (price - avg_buy_price) / avg_buy_price * 100

        if profit_rate >= 3.0:
            return {
                "action": "SELL",
                "qty": holding_qty,
                "price": price,
                "reason": f"익절 조건 충족: 수익률={profit_rate:.2f}%"
            }

        if profit_rate <= -2.0:
            return {
                "action": "SELL",
                "qty": holding_qty,
                "price": price,
                "reason": f"손절 조건 충족: 수익률={profit_rate:.2f}%"
            }

        return {
            "action": "HOLD",
            "qty": 0,
            "price": price,
            "reason": f"보유 유지: 수익률={profit_rate:.2f}%, 익절=+3%, 손절=-2%"
        }

    # 보유 없으면 매수 판단
    if holding_qty == 0:
        up_trend = ma20 > ma60
        rsi_rebound_zone = rsi_buy_min <= rsi <= rsi_buy_max

        fail_reasons = []

        if cash <= 0:
            fail_reasons.append(f"주문가능금액 부족: 주문가능={cash:,}원")

        if not up_trend:
            fail_reasons.append(f"상승추세 아님: MA20={ma20}, MA60={ma60}")

        if not rsi_rebound_zone:
            fail_reasons.append(f"RSI 조건 미충족: 현재 RSI={rsi:.2f}, 필요 RSI={rsi_buy_min}~{rsi_buy_max}")

        if not fail_reasons:
            usable_amount = min(buy_amount, cash)
            qty = int(usable_amount // price)

            if qty >= 1:
                return {
                    "action": "BUY",
                    "qty": qty,
                    "price": price,
                    "reason": f"매수 조건 충족: 상승추세 + RSI 반등구간, 주문가능={cash:,}원"
                }

            fail_reasons.append(
                f"매수수량 부족: 매수가능금액={usable_amount:,}원, 현재가={price:,}원"
            )

        return {
            "action": "HOLD",
            "qty": 0,
            "price": price,
            "reason": "매수 보류: " + " / ".join(fail_reasons)
        }

    return {
        "action": "HOLD",
        "qty": 0,
        "price": price,
        "reason": "조건 미충족"
    }