def make_balance_info(data, stock_code):
    output1 = data.get("output1", [])
    output2 = data.get("output2", [{}])[0]

    cash = int(output2.get("dnca_tot_amt", "0") or "0")
    total = int(output2.get("tot_evlu_amt", "0") or "0")
    orderable_cash = int(output2.get("ord_psbl_cash", "0") or "0")

    holding_qty = 0
    stock_name = "-"

    for item in output1:
        if item.get("pdno") == stock_code:
            holding_qty = int(item.get("hldg_qty", "0") or "0")
            stock_name = item.get("prdt_name", "-")

    return {
        "cash": cash,
        "total": total,
        "orderable_cash": orderable_cash,
        "holding_qty": holding_qty,
        "stock_name": stock_name,
        "items": output1,
    }


def ai_strategy(price, balance, buy_amount, avg_buy_price=0, ma20=None, ma60=None, rsi=None):
    """
    모의투자용 기본 자동매매 전략

    매수:
    - 보유 수량 0
    - MA20 > MA60 상승추세
    - RSI 30~45 저점 반등 구간
    - buy_amount 만큼 매수

    매도:
    - 보유 수량 있음
    - 수익률 +3% 이상 익절
    - 수익률 -2% 이하 손절
    """

    holding_qty = int(balance.get("holding_qty", 0))
    cash = int(balance.get("cash", 0))

    # 지표가 아직 없으면 HOLD
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
                "reason": f"익절 조건 충족: {profit_rate:.2f}%"
            }

        if profit_rate <= -2.0:
            return {
                "action": "SELL",
                "qty": holding_qty,
                "price": price,
                "reason": f"손절 조건 충족: {profit_rate:.2f}%"
            }

        return {
            "action": "HOLD",
            "qty": 0,
            "price": price,
            "reason": f"보유 유지: 수익률 {profit_rate:.2f}%"
        }

    # 보유 없으면 매수 판단
    if holding_qty == 0:
        up_trend = ma20 > ma60
        rsi_rebound_zone = 30 <= rsi <= 45

        if up_trend and rsi_rebound_zone:
            usable_amount = min(buy_amount, cash)
            qty = int(usable_amount // price)

            if qty >= 1:
                return {
                    "action": "BUY",
                    "qty": qty,
                    "price": price,
                    "reason": f"상승추세 + RSI 반등구간: MA20={ma20}, MA60={ma60}, RSI={rsi}"
                }

    return {
        "action": "HOLD",
        "qty": 0,
        "price": price,
        "reason": f"조건 미충족: MA20={ma20}, MA60={ma60}, RSI={rsi}"
    }