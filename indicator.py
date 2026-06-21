def calc_ma(prices, period):
    if len(prices) < period:
        return None

    return sum(prices[-period:]) / period


def calc_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None

    gains = []
    losses = []

    recent = prices[-(period + 1):]

    for i in range(1, len(recent)):
        diff = recent[i] - recent[i - 1]

        if diff > 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))