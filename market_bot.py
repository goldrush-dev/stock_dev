import os
import json
import time
import random
from datetime import datetime
from datetime import timedelta

from ai_strategy import make_balance_info, ai_strategy
from indicator import calc_ma, calc_rsi
from logger import write_log


last_status_log_hour = {}

# 손절 후 재매수 차단 상태
# 규칙:
#   손절 1회 -> 30분 매수 금지
#   손절 2회 -> 2시간 매수 금지
#   손절 3회 이상 -> 당일 매수 금지
#   다음날 자동 해제
STOP_GUARD_FILE = "stop_guard_state.json"
stop_guard_state = {}


def _today_str():
    return datetime.now().strftime("%Y-%m-%d")


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load_stop_guard_state():
    global stop_guard_state

    if stop_guard_state:
        return

    if not os.path.exists(STOP_GUARD_FILE):
        stop_guard_state = {}
        return

    try:
        with open(STOP_GUARD_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            stop_guard_state = data
        else:
            stop_guard_state = {}

    except Exception as e:
        print("손절 차단 상태 파일 로드 실패:", e)
        stop_guard_state = {}


def _save_stop_guard_state():
    try:
        with open(STOP_GUARD_FILE, "w", encoding="utf-8") as f:
            json.dump(stop_guard_state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("손절 차단 상태 파일 저장 실패:", e)


def _reset_stop_guard_if_new_day(code, name):
    """종목별 손절 상태를 다음날 자동 초기화."""
    _load_stop_guard_state()

    state = stop_guard_state.get(code)
    if not state:
        return

    saved_date = state.get("date")
    today = _today_str()

    if saved_date != today:
        old_count = int(state.get("stop_count", 0))
        stop_guard_state.pop(code, None)
        _save_stop_guard_state()

        msg = f"{name}({code}) 날짜 변경으로 손절 차단 해제 / 이전 손절횟수={old_count}"
        print("[STOP_RESET]", msg)
        write_log("STOP_RESET", msg)


def _parse_block_until(text):
    if not text:
        return None

    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def get_stop_guard_block_reason(code, name):
    """
    현재 종목이 손절 차단 상태인지 확인.
    차단 중이면 reason 문자열 반환, 아니면 None 반환.
    """
    _reset_stop_guard_if_new_day(code, name)

    state = stop_guard_state.get(code)
    if not state:
        return None

    stop_count = int(state.get("stop_count", 0))
    blocked_today = bool(state.get("blocked_today", False))
    block_until = _parse_block_until(state.get("block_until"))

    now = datetime.now()

    if blocked_today:
        return f"손절 {stop_count}회로 오늘 매수 금지"

    if block_until and now < block_until:
        remain_min = int((block_until - now).total_seconds() // 60) + 1
        return f"손절 {stop_count}회 후 재매수 대기 중: 약 {remain_min}분 남음, 해제시각={state.get('block_until')}"

    # 시간이 지났으면 차단만 해제. 손절 횟수는 당일 유지한다.
    if block_until and now >= block_until:
        state["block_until"] = None
        stop_guard_state[code] = state
        _save_stop_guard_state()

        msg = f"{name}({code}) 재매수 시간 차단 해제 / 손절횟수={stop_count}"
        print("[STOP_UNBLOCK]", msg)
        write_log("STOP_UNBLOCK", msg)

    return None


def register_stop_loss(code, name, price, reason):
    """손절 매도가 실제 성공했을 때 호출."""
    _reset_stop_guard_if_new_day(code, name)

    today = _today_str()
    now = datetime.now()

    state = stop_guard_state.get(code, {})
    stop_count = int(state.get("stop_count", 0)) + 1

    blocked_today = False
    block_until = None

    if stop_count == 1:
        block_until = now + timedelta(minutes=30)
    elif stop_count == 2:
        block_until = now + timedelta(hours=2)
    else:
        blocked_today = True

    new_state = {
        "date": today,
        "stop_count": stop_count,
        "last_stop_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "last_stop_price": int(price),
        "last_stop_reason": str(reason),
        "block_until": block_until.strftime("%Y-%m-%d %H:%M:%S") if block_until else None,
        "blocked_today": blocked_today,
    }

    stop_guard_state[code] = new_state
    _save_stop_guard_state()

    if blocked_today:
        msg = f"{name}({code}) 손절 {stop_count}회 발생. 오늘 해당 종목 매수 금지. 손절가={price:,}"
    else:
        msg = f"{name}({code}) 손절 {stop_count}회 발생. {new_state['block_until']}까지 매수 금지. 손절가={price:,}"

    print("[STOP_GUARD]", msg)
    write_log("STOP_GUARD", msg)


def is_stop_loss_signal(signal):
    if not signal:
        return False

    if signal.get("action") != "SELL":
        return False

    reason = str(signal.get("reason", ""))
    return "손절" in reason


def print_balance(balance):
    usable_cash = balance["orderable_cash"]
    if usable_cash <= 0:
        usable_cash = balance["cash"]

    print()
    print("========== 나의 자산 ==========")
    print("총평가금액     :", f"{balance['total']:,}", "원")
    print("예수금         :", f"{balance['cash']:,}", "원")
    print("D+1 예수금     :", f"{balance['d1_cash']:,}", "원")
    print("D+2 예수금     :", f"{balance['d2_cash']:,}", "원")
    print("주문가능금액   :", f"{usable_cash:,}", "원")
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
            "stop_loss": float(config.get("stop_loss", 2.0)),
            "take_profit": float(config.get("take_profit", 3.0)),
        }

    default_buy_amount = int(config.get("default_buy_amount", config.get("buy_amount", 1000000)))
    code = stock.get("code") or stock.get("stock_code")
    name = stock.get("name") or stock.get("stock_name") or code
    buy_amount = int(stock.get("buy_amount", default_buy_amount))
    stop_loss = float(stock.get("stop_loss", config.get("stop_loss", 2.0)))
    take_profit = float(stock.get("take_profit", config.get("take_profit", 3.0)))

    return {
        "code": str(code),
        "name": str(name),
        "buy_amount": buy_amount,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
    }


def get_cached_indicators(api, code, indicator_cache):
    cached = indicator_cache.get(code)

    if cached and "time" in cached:
        last_time = datetime.strptime(cached["time"], "%Y-%m-%d %H:%M:%S")

        if datetime.now() - last_time < timedelta(minutes=30):
            print("기술지표 캐시 사용")
            return cached["ma20"], cached["ma60"], cached["rsi"]

    print("기술지표 신규 계산")
    daily_prices = api.get_daily_prices(code, days=100)

    ma20 = calc_ma(daily_prices, 20)
    ma60 = calc_ma(daily_prices, 60)
    rsi = calc_rsi(daily_prices, 14)

    indicator_cache[code] = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
    stop_loss = float(stock.get("stop_loss", config.get("stop_loss", 2.0)))
    take_profit = float(stock.get("take_profit", config.get("take_profit", 3.0)))
    simulation_mode = bool(config.get("simulation_mode", True))

    # 다음날 자동 해제 체크
    _reset_stop_guard_if_new_day(code, name)

    if indicator_cache is None:
        indicator_cache = {}

    print()
    print("========== 장중 자동매매 실행 ==========")
    print("시간          :", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("종목          :", name, code)
    print("1회 매수한도  :", f"{buy_amount:,}", "원")
    print("손절/익절     :", f"-{stop_loss}%", "/", f"+{take_profit}%")

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
        # 핵심: 일봉/지표는 종목별 30분마다 조회
        ma20, ma60, rsi = get_cached_indicators(api, code, indicator_cache)

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
            rsi_buy_min=config["rsi_buy_min"],
            rsi_buy_max=config["rsi_buy_max"],
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        # 손절 후 재매수 차단: BUY 신호가 나와도 차단 중이면 HOLD로 변경
        block_reason = get_stop_guard_block_reason(code, name)
        if signal.get("action") == "BUY" and block_reason:
            old_reason = signal.get("reason", "")
            signal = dict(signal)
            signal["action"] = "HOLD"
            signal["qty"] = 0
            signal["reason"] = f"매수 차단: {block_reason} / 기존 BUY 이유: {old_reason}"

            msg = f"{name}({code}) {signal['reason']}"
            print("[STOP_BLOCK]", msg)
            write_log("STOP_BLOCK", msg)

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

        usable_cash = balance["orderable_cash"]
        if usable_cash <= 0:
            usable_cash = balance["cash"]

        summary = (
            f"{name}({code}) "
            f"현재가={price:,}, "
            f"보유={balance['holding_qty']}주, "
            f"총자산={balance['total']:,}, "
            f"예수금={balance['cash']:,}, "
            f"D+1={balance['d1_cash']:,}, "
            f"D+2={balance['d2_cash']:,}, "
            f"주문가능={usable_cash:,}, "
            f"1회매수한도={buy_amount:,}, "
            f"손절=-{stop_loss}%, "
            f"익절=+{take_profit}%, "
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

        # 모의 실행에서도 손절 차단 로직 테스트 가능하게 등록
        if is_stop_loss_signal(signal):
            register_stop_loss(code, name, int(signal["price"]), signal.get("reason", ""))

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
        # 실제 손절 매도 성공 후에만 차단 카운트 증가
        if is_stop_loss_signal(signal):
            register_stop_loss(code, name, int(signal["price"]), signal.get("reason", ""))

        return signal["action"]

    return "HOLD"
