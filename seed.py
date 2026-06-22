"""
範例資料產生器 — 灌入一批決策／選項／標籤，方便演示與 dashboard 展示。

用法：
    python3 seed.py          # 清空舊資料並寫入範例
    python3 seed.py --keep   # 保留現有資料，只追加範例
"""
import sys
import uuid

from database import get_db, init_db
from logic import compute_net_values


# 每筆決策：(標題, 描述, 狀態, [選項...])
# 選項：(名稱, 描述, benefit, cost, risk, [標籤], is_important)
SAMPLE_DECISIONS = [
    (
        "暑假要做什麼", "想兼顧收入、成長與休息", "completed",
        [
            ("科技公司實習", "後端工程實習，月薪 3.8 萬", 9, 4, 3, ["#實習", "#專業課"], 1),
            ("飲料店打工", "時薪 183，彈性排班", 5, 3, 2, ["#打工"], 0),
            ("在家自學專案", "做一個側專案放作品集", 7, 2, 5, ["#專案開發"], 0),
            ("純休息旅遊", "出國放鬆兩週", 6, 7, 4, ["#社交"], 0),
        ],
    ),
    (
        "下學期選修課", "學分有限，想選最有價值的", "completed",
        [
            ("機器學習導論", "硬但業界搶手", 9, 6, 4, ["#專業課"], 1),
            ("通識電影賞析", "輕鬆好拿高分", 4, 2, 1, ["#學業"], 0),
            ("資料庫系統", "和未來工作相關", 8, 5, 3, ["#專業課"], 0),
        ],
    ),
    (
        "要不要接學生會幹部", "考慮時間成本與人脈", "completed",
        [
            ("接活動組長", "練領導，但很花時間", 7, 8, 5, ["#社交"], 0),
            ("只當一般幹部", "參與感夠又不爆肝", 6, 4, 2, ["#社交"], 1),
            ("不參加", "把時間留給課業", 5, 1, 2, ["#學業"], 0),
        ],
    ),
    (
        "畢業專題題目", "影響未來一年的方向", "active",
        [
            ("AI 決策輔助系統", "結合課堂所學，挑戰高", 9, 6, 6, ["#專案開發", "#專業課"], 1),
            ("校園二手交易 App", "需求明確、好實作", 7, 4, 3, ["#專案開發"], 0),
            ("資安弱點掃描工具", "題目酷但門檻高", 8, 7, 7, ["#專案開發", "#專業課"], 0),
        ],
    ),
    (
        "要不要修第二外語", "興趣 vs 學業負擔", "active",
        [
            ("修日文", "有興趣、想看原文動畫", 7, 4, 3, ["#學業", "#社交"], 0),
            ("不修，專心本科", "把時間集中在專業課", 6, 2, 2, ["#專業課"], 1),
        ],
    ),
    (
        "週末時間怎麼分配", "想在效率與生活間取得平衡", "active",
        [
            ("刷題準備面試", "為實習做準備", 8, 5, 3, ["#實習"], 1),
            ("和朋友出遊", "維持社交與心理健康", 6, 4, 2, ["#社交"], 0),
            ("補眠耍廢", "恢復精神", 5, 2, 1, ["#學業"], 0),
        ],
    ),
    (
        "要不要換實習公司", "現職薪低但穩定", "completed",
        [
            ("跳新創拿股票", "高成長高風險", 8, 5, 7, ["#實習"], 0),
            ("留原公司轉正", "穩定、熟悉環境", 7, 3, 2, ["#實習", "#專業課"], 1),
        ],
    ),
]


def seed(keep=False):
    init_db()
    conn = get_db()

    if not keep:
        for tbl in ("tags", "options", "decisions"):
            conn.execute(f"DELETE FROM {tbl}")
        conn.commit()

    n_dec = n_opt = 0
    for title, desc, status, options in SAMPLE_DECISIONS:
        did = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO decisions (id, title, description, status) VALUES (?, ?, ?, ?)",
            (did, title, desc, status),
        )
        n_dec += 1

        # 先建立選項物件以計算淨值
        built = []
        for name, odesc, benefit, cost, risk, tags, important in options:
            oid = str(uuid.uuid4())
            built.append({
                "id": oid, "name": name, "description": odesc,
                "benefit": benefit, "cost": cost, "risk": risk,
                "tags": tags, "is_important": important,
            })

        compute_net_values(built)  # 填入 weighted_score / net_value / recommended

        for o in built:
            conn.execute(
                """INSERT INTO options
                   (id, decision_id, name, description, benefit, cost, risk,
                    net_value, is_chosen, is_important)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (o["id"], did, o["name"], o["description"],
                 o["benefit"], o["cost"], o["risk"], o["net_value"],
                 1 if o.get("recommended") else 0, o["is_important"]),
            )
            n_opt += 1
            for tag in o["tags"]:
                conn.execute(
                    "INSERT INTO tags (option_id, tag) VALUES (?, ?)", (o["id"], tag)
                )

    conn.commit()
    conn.close()
    print(f"✓ 已寫入 {n_dec} 筆決策、{n_opt} 個選項"
          + ("（追加模式）" if keep else "（已清空舊資料）"))


if __name__ == "__main__":
    seed(keep="--keep" in sys.argv)
