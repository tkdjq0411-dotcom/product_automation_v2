from dataclasses import dataclass


@dataclass(frozen=True)
class SellStopPolicy:
    # 단순 판매 판단: 순이익이 남으면 SELL, 아니면 STOP
    min_net_profit: float = 0.0
    min_margin_rate: float = 0.0


DEFAULT_SELL_STOP_POLICY = SellStopPolicy()


def judge_sell_stop(*, net_profit: float, margin_rate: float, selling_price: float,
                    policy: SellStopPolicy = DEFAULT_SELL_STOP_POLICY) -> dict:
    """B2B 판매 판단 단일 기준: 이익이 남으면 SELL, 아니면 STOP."""
    if selling_price <= 0:
        return {"status": "STOP", "status_reason": "판매가 없음"}
    if net_profit <= 0:
        return {"status": "STOP", "status_reason": "이익 없음"}
    return {"status": "SELL", "status_reason": "판매 가능"}


def policy_dict(policy: SellStopPolicy = DEFAULT_SELL_STOP_POLICY) -> dict:
    return {
        "min_net_profit": 0.0,
        "min_margin_rate": 0.0,
        "sell": "순이익이 0원보다 크면 판매",
        "stop": "판매가가 없거나 순이익이 0원 이하이면 중지",
    }
