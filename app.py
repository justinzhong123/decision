import csv
import io
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, render_template, Response
from database import get_db, init_db
from logic import compute_net_values, historical_baseline

app = Flask(__name__)


_db_ready = False

@app.before_request
def ensure_db():
    global _db_ready
    if not _db_ready:
        init_db()
        _db_ready = True


# ── Decisions ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/uml")
def uml():
    return render_template("uml.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/decisions", methods=["GET"])
def list_decisions():
    conn = get_db()
    decisions = conn.execute(
        "SELECT * FROM decisions ORDER BY created_at DESC"
    ).fetchall()
    result = []
    for d in decisions:
        d = dict(d)
        d["options"] = _get_options_for_decision(conn, d["id"])
        result.append(d)
    conn.close()
    return jsonify(result)


@app.route("/api/decisions", methods=["POST"])
def create_decision():
    data = request.json
    if not data or not data.get("title", "").strip():
        return jsonify({"error": "title required"}), 400
    did = str(uuid.uuid4())
    conn = get_db()
    conn.execute(
        "INSERT INTO decisions (id, title, description) VALUES (?, ?, ?)",
        (did, data["title"].strip(), data.get("description", ""))
    )
    conn.commit()
    decision = dict(conn.execute("SELECT * FROM decisions WHERE id=?", (did,)).fetchone())
    decision["options"] = []
    conn.close()
    return jsonify(decision), 201


@app.route("/api/decisions/<did>", methods=["DELETE"])
def delete_decision(did):
    conn = get_db()
    conn.execute("DELETE FROM decisions WHERE id=?", (did,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/decisions/<did>/complete", methods=["POST"])
def complete_decision(did):
    conn = get_db()
    conn.execute("UPDATE decisions SET status='completed' WHERE id=?", (did,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ── Options ────────────────────────────────────────────────────────────────

@app.route("/api/decisions/<did>/options", methods=["POST"])
def create_option(did):
    data = request.json or {}
    oid = str(uuid.uuid4())
    conn = get_db()
    conn.execute(
        """INSERT INTO options (id, decision_id, name, description, benefit, cost, risk)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (oid, did,
         data.get("name", "新選項"),
         data.get("description", ""),
         float(data.get("benefit", 5)),
         float(data.get("cost", 5)),
         float(data.get("risk", 5)))
    )
    tags = data.get("tags", [])
    for tag in tags:
        conn.execute("INSERT INTO tags (option_id, tag) VALUES (?, ?)", (oid, tag))
    conn.commit()
    option = _get_option(conn, oid)
    conn.close()
    return jsonify(option), 201


@app.route("/api/options/<oid>", methods=["PUT"])
def update_option(oid):
    data = request.json or {}
    conn = get_db()
    conn.execute(
        """UPDATE options SET name=?, description=?, benefit=?, cost=?, risk=?,
           is_important=? WHERE id=?""",
        (data.get("name", ""),
         data.get("description", ""),
         float(data.get("benefit", 5)),
         float(data.get("cost", 5)),
         float(data.get("risk", 5)),
         int(data.get("is_important", 0)),
         oid)
    )
    # replace tags
    conn.execute("DELETE FROM tags WHERE option_id=?", (oid,))
    for tag in data.get("tags", []):
        conn.execute("INSERT INTO tags (option_id, tag) VALUES (?, ?)", (oid, tag))
    conn.commit()
    option = _get_option(conn, oid)
    conn.close()
    return jsonify(option)


@app.route("/api/options/<oid>", methods=["DELETE"])
def delete_option(oid):
    conn = get_db()
    conn.execute("DELETE FROM options WHERE id=?", (oid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ── Analysis ───────────────────────────────────────────────────────────────

@app.route("/api/decisions/<did>/analyze", methods=["GET"])
def analyze_decision(did):
    conn = get_db()
    opts = _get_options_for_decision(conn, did)
    if not opts:
        conn.close()
        return jsonify({"options": [], "recommendation": None})

    opts = compute_net_values(opts)

    # Historical baselines per unique tag
    all_tags = {t for o in opts for t in o["tags"]}
    baselines = {}
    for tag in all_tags:
        b = historical_baseline(conn, tag)
        if b:
            baselines[tag] = b

    # Persist computed net_value
    for o in opts:
        conn.execute("UPDATE options SET net_value=? WHERE id=?", (o["net_value"], o["id"]))
    conn.commit()
    conn.close()

    recommended = next((o for o in opts if o.get("recommended")), None)
    return jsonify({
        "options": sorted(opts, key=lambda o: o["weighted_score"], reverse=True),
        "recommendation": recommended["name"] if recommended else None,
        "baselines": baselines,
    })


# ── Dashboard ──────────────────────────────────────────────────────────────

@app.route("/api/dashboard", methods=["GET"])
def dashboard_data():
    conn = get_db()

    decisions = [dict(d) for d in conn.execute(
        "SELECT * FROM decisions ORDER BY created_at DESC"
    ).fetchall()]

    total = len(decisions)
    completed = sum(1 for d in decisions if d["status"] == "completed")
    active = total - completed

    # 每筆決策附上選項數、最佳選項與其淨值
    summaries = []
    total_options = 0
    for d in decisions:
        opts = _get_options_for_decision(conn, d["id"])
        total_options += len(opts)
        best = max(opts, key=lambda o: (o["net_value"] or -999), default=None)
        tags = sorted({t for o in opts for t in o["tags"]})
        summaries.append({
            "id": d["id"],
            "title": d["title"],
            "status": d["status"],
            "created_at": d["created_at"],
            "option_count": len(opts),
            "best_option": best["name"] if best else None,
            "best_net_value": best["net_value"] if best else None,
            "tags": tags,
        })

    # 標籤統計：使用次數 + 平均效益/成本/風險
    tag_rows = conn.execute("""
        SELECT t.tag AS tag,
               COUNT(*) AS count,
               AVG(o.benefit) AS avg_benefit,
               AVG(o.cost)    AS avg_cost,
               AVG(o.risk)    AS avg_risk,
               AVG(o.net_value) AS avg_net
        FROM tags t JOIN options o ON o.id = t.option_id
        GROUP BY t.tag
        ORDER BY count DESC
    """).fetchall()
    tag_stats = [{
        "tag": r["tag"],
        "count": r["count"],
        "avg_benefit": round(r["avg_benefit"], 2) if r["avg_benefit"] is not None else None,
        "avg_cost": round(r["avg_cost"], 2) if r["avg_cost"] is not None else None,
        "avg_risk": round(r["avg_risk"], 2) if r["avg_risk"] is not None else None,
        "avg_net": round(r["avg_net"], 2) if r["avg_net"] is not None else None,
    } for r in tag_rows]

    conn.close()
    return jsonify({
        "totals": {
            "decisions": total,
            "active": active,
            "completed": completed,
            "options": total_options,
            "tags": len(tag_stats),
        },
        "decisions": summaries,
        "tag_stats": tag_stats,
    })


# ── Export ─────────────────────────────────────────────────────────────────

@app.route("/api/export.csv", methods=["GET"])
def export_csv():
    """匯出所有決策與選項為 CSV，每列一個選項。"""
    conn = get_db()
    decisions = conn.execute(
        "SELECT * FROM decisions ORDER BY created_at DESC"
    ).fetchall()

    buf = io.StringIO()
    buf.write("﻿")  # UTF-8 BOM，讓 Excel 正確顯示中文
    writer = csv.writer(buf)
    writer.writerow([
        "決策主題", "決策描述", "狀態", "建立時間",
        "選項名稱", "選項描述", "效益", "成本", "風險",
        "淨值", "是否推薦", "重要", "標籤",
    ])

    for d in decisions:
        d = dict(d)
        opts = _get_options_for_decision(conn, d["id"])
        if not opts:
            writer.writerow([d["title"], d["description"],
                             d["status"], d["created_at"],
                             "", "", "", "", "", "", "", "", ""])
            continue
        for o in opts:
            writer.writerow([
                d["title"], d["description"], d["status"], d["created_at"],
                o["name"], o["description"], o["benefit"], o["cost"], o["risk"],
                o["net_value"] if o["net_value"] is not None else "",
                "是" if o["is_chosen"] else "",
                "是" if o["is_important"] else "",
                " ".join(o["tags"]),
            ])

    conn.close()
    filename = f"decisions_{datetime.now():%Y%m%d}.csv"
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Preferences ────────────────────────────────────────────────────────────

@app.route("/api/preferences", methods=["GET"])
def get_preferences():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM user_preferences").fetchall()
    conn.close()
    return jsonify({r["key"]: r["value"] for r in rows})


@app.route("/api/preferences", methods=["POST"])
def set_preferences():
    data = request.json or {}
    conn = get_db()
    for key, value in data.items():
        conn.execute(
            "INSERT INTO user_preferences (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value))
        )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ── Helpers ────────────────────────────────────────────────────────────────

def _get_option(conn, oid):
    row = conn.execute("SELECT * FROM options WHERE id=?", (oid,)).fetchone()
    if not row:
        return None
    o = dict(row)
    o["tags"] = [r["tag"] for r in conn.execute(
        "SELECT tag FROM tags WHERE option_id=?", (oid,)
    ).fetchall()]
    return o


def _get_options_for_decision(conn, did):
    rows = conn.execute(
        "SELECT * FROM options WHERE decision_id=? ORDER BY created_at", (did,)
    ).fetchall()
    options = []
    for row in rows:
        o = dict(row)
        o["tags"] = [r["tag"] for r in conn.execute(
            "SELECT tag FROM tags WHERE option_id=?", (o["id"],)
        ).fetchall()]
        options.append(o)
    return options


if __name__ == "__main__":
    init_db()
    # use_reloader=False 避免修改檔案時伺服器重啟中斷進行中的請求
    app.run(debug=True, port=5001, use_reloader=False)
