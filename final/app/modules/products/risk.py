def analyze_product_risk(*, net_profit: float, margin_rate: float, selling_price: float,
                         recommended_price: float, quantity: int, minimum_quantity: int) -> dict:
    risks = []

    def add(code, level, message):
        risks.append({"code": code, "level": level, "message": message})

    if selling_price <= 0:
        add("NO_PRICE", "HIGH", "판매가가 0원입니다.")
    if net_profit <= 0:
        add("LOSS", "HIGH", "순이익이 0원 이하입니다.")
    elif net_profit < 2000:
        add("LOW_PROFIT", "MEDIUM", "순이익이 SELL 기준 2,000원보다 낮습니다.")

    if selling_price > 0 and margin_rate < 5:
        add("LOW_MARGIN", "MEDIUM" if margin_rate > 0 else "HIGH", "마진율이 SELL 기준 5%보다 낮습니다.")

    if recommended_price > 0 and selling_price < recommended_price:
        gap = round(recommended_price - selling_price, 2)
        add("BELOW_RECOMMENDED", "MEDIUM", f"권장판매가보다 {gap:,.2f}원 낮습니다.")

    if quantity <= 0:
        add("OUT_OF_STOCK", "HIGH", "현재 재고가 0개입니다.")
    elif quantity <= minimum_quantity:
        add("LOW_STOCK", "MEDIUM", "현재 재고가 최소재고 이하입니다.")

    high = sum(1 for x in risks if x["level"] == "HIGH")
    medium = sum(1 for x in risks if x["level"] == "MEDIUM")
    if high:
        overall = "HIGH"
    elif medium:
        overall = "MEDIUM"
    else:
        overall = "LOW"

    return {
        "risk_level": overall,
        "risk_count": len(risks),
        "high_risk_count": high,
        "medium_risk_count": medium,
        "risks": risks,
    }
