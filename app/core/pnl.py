from decimal import Decimal


def calculate_unrealized(balance, avg_price, current_price):

    return (current_price - avg_price) * balance


def calculate_realized(sell_price, buy_price, amount):

    return (sell_price - buy_price) * amount


def calculate_percent(pnl, cost):

    if cost == 0:
        return 0

    return (pnl / cost) * 100