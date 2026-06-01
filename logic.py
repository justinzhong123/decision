"""
Decision Logic Module — OCDS
Net_Value(A) = (B_A - C_A - R_A) - max(B_others - C_others - R_others)
Career weight ω_cr = 1.25 applied when option tags include #專業課, #實習, #專案開發
"""

CAREER_TAGS = {"#專業課", "#實習", "#專案開發"}
CAREER_WEIGHT = 1.25


def raw_score(benefit: float, cost: float, risk: float) -> float:
    return benefit - cost - risk


def career_weighted_score(benefit: float, cost: float, risk: float, tags: list[str]) -> float:
    score = raw_score(benefit, cost, risk)
    if any(t in CAREER_TAGS for t in tags):
        score *= CAREER_WEIGHT
    return round(score, 4)


def compute_net_values(options: list[dict]) -> list[dict]:
    """
    options: list of dicts with keys benefit, cost, risk, tags (list of str)
    Returns the same list enriched with:
      - weighted_score
      - net_value  (weighted_score minus best competitor)
      - recommended (bool)
    """
    for opt in options:
        opt["weighted_score"] = career_weighted_score(
            opt["benefit"], opt["cost"], opt["risk"], opt.get("tags", [])
        )

    if not options:
        return options

    scored = sorted(options, key=lambda o: o["weighted_score"], reverse=True)
    best = scored[0]["weighted_score"]
    second = scored[1]["weighted_score"] if len(scored) > 1 else best

    for opt in options:
        if opt["weighted_score"] == best:
            # best option's net value vs. closest competitor
            opt["net_value"] = round(best - second, 4)
            opt["recommended"] = True
        else:
            opt["net_value"] = round(opt["weighted_score"] - best, 4)
            opt["recommended"] = False

    return options


def historical_baseline(conn, tag: str) -> dict | None:
    """Moving average of B, C, R for the same tag across completed decisions."""
    rows = conn.execute("""
        SELECT o.benefit, o.cost, o.risk
        FROM options o
        JOIN tags t ON t.option_id = o.id
        JOIN decisions d ON d.id = o.decision_id
        WHERE t.tag = ? AND d.status = 'completed'
        ORDER BY o.created_at DESC
        LIMIT 20
    """, (tag,)).fetchall()

    if not rows:
        return None

    n = len(rows)
    return {
        "tag": tag,
        "count": n,
        "avg_benefit": round(sum(r["benefit"] for r in rows) / n, 2),
        "avg_cost": round(sum(r["cost"] for r in rows) / n, 2),
        "avg_risk": round(sum(r["risk"] for r in rows) / n, 2),
    }
