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


def ai_like_strategy(price, balance, buy_amount):
    """
    AI 붙이기 전 임시 전략.

    지금은 규칙 기반:
    - 삼성전자 보유수량이 0이면 매수 후보
    - 이미 보유 중이면 HOLD
    - 주문가능금액 부족하면 HOLD

    나중에 이 함수 내부만 진짜 AI 판단으로 교체하면 됨.
    """

    holding_qty = balance["holding_qty"]
    orderable_cash = balance["orderable_cash"] or balance["cash"]

    if holding_qty == 0:
        usable_amount = min(buy_amount, orderable_cash)
        qty = usable_amount // price

        if qty >= 1:
            return {
                "action": "BUY",
                "qty": int(qty),
                "price": price,
                "confidence": 60,
                "reason": "AI 이전 테스트 로직: 보유수량이 없어 매수 후보",
            }

        return {
            "action": "HOLD",
            "qty": 0,
            "price": price,
            "confidence": 90,
            "reason": "주문가능금액 부족",
        }

    return {
        "action": "HOLD",
        "qty": 0,
        "price": price,
        "confidence": 70,
        "reason": "이미 삼성전자를 보유 중이므로 추가 매수 안 함",
    }