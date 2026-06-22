"""
Decision Logic Module — OCDS

評分哲學：對成本與風險「容忍」，並額外獎勵高價值的大膽選擇，
讓「高風險、高成本、但高價值」的機會有機會勝出，而不會總是輸給保守選項。

score = (B·w_B − C·w_C − R·w_R) + 高價值獎勵
        其中高價值獎勵 = AMBITION_BONUS × max(0, B − BOLD_THRESHOLD)
weighted_score = score × ω_cr        # 職涯標籤加權
Net_Value(A)   = weighted_score(A) − max(weighted_score(others))

Career weight ω_cr = 1.25 applied when option tags include #專業課, #實習, #專案開發
"""

CAREER_TAGS = {"#專業課", "#實習", "#專案開發"}
CAREER_WEIGHT = 1.25

# ── 可調參數 ──────────────────────────────────────────────────────────────
BENEFIT_WEIGHT = 1.2   # 效益為主要驅動力
COST_WEIGHT    = 0.6   # 成本敏感度（<1：容忍較高成本）
RISK_WEIGHT    = 0.5   # 風險敏感度（<1：容忍較高風險）
AMBITION_BONUS = 0.4   # 效益每超過門檻 1 分的額外獎勵
BOLD_THRESHOLD = 7.0   # 效益 ≥ 此值視為「高價值的大膽選擇」


def raw_score(benefit: float, cost: float, risk: float) -> float:
    """加權基礎分 + 高價值獎勵（不含職涯加權）。"""
    base = BENEFIT_WEIGHT * benefit - COST_WEIGHT * cost - RISK_WEIGHT * risk
    ambition = AMBITION_BONUS * max(0.0, benefit - BOLD_THRESHOLD)
    return base + ambition


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
