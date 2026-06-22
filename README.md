# Decision — 智慧決策輔助系統

一個基於 Flask 的個人決策分析工具，幫助你透過量化評分來比較選項、做出更理性的決定。

## 功能

- 建立多個決策題目，每題可新增多個選項
- 為每個選項設定**效益 (Benefit)**、**成本 (Cost)**、**風險 (Risk)** 分數（1–10）
- 系統自動計算加權分數與淨值，並推薦最佳選項
- 支援標籤系統（如 `#學業`、`#打工`、`#社交`），職涯相關標籤（`#專業課`、`#實習`、`#專案開發`）自動套用 1.25 倍加權
- 歷史基準比較：根據過去同標籤的決策結果提供參考
- 決策完成後可標記為已完成

## 評分公式

```
weighted_score = (Benefit - Cost - Risk) × ω
net_value      = weighted_score(最佳) - weighted_score(次佳)
```

其中職涯相關標籤的權重 `ω = 1.25`，其餘為 `1.0`。

## 安裝與執行

**需求：** Python 3.10+

```bash
# 安裝依賴
pip install -r requirements.txt

# 啟動伺服器
python3 app.py
```

啟動後開啟瀏覽器前往 [http://localhost:5001](http://localhost:5001)

## 部署到 Render

此專案使用 SQLite，需要**持久磁碟 (Persistent Disk)** 才能讓資料在重新部署後保留，因此採用支援常駐伺服器的 Render（而非 Vercel serverless）。

設定已包含在 `render.yaml`：以 `gunicorn` 啟動、把資料庫透過 `DB_PATH` 環境變數指向掛載的磁碟 `/var/data/ocds.db`。

步驟：

1. 把專案推上 GitHub。
2. 在 [Render](https://render.com) 點 **New → Blueprint**，選擇此 repo，Render 會自動讀取 `render.yaml`。
3. 部署完成後即可使用所提供的網址。

> ⚠️ 持久磁碟需要 **Starter（付費）以上方案**；Render 的 free 方案沒有 disk，資料會在每次重啟後消失。
> 若想完全免費並保留資料，可改用 **Fly.io**（volume 有免費額度）；告訴我即可幫你補上 `Dockerfile` 與 `fly.toml`。

部署用設定檔：`render.yaml`、`Procfile`、`requirements.txt`（含 `gunicorn`）。

## 專案結構

```
decision/
├── app.py          # Flask 路由與 API
├── database.py     # SQLite 初始化與連線
├── logic.py        # 決策評分演算法
├── requirements.txt
└── templates/
    ├── index.html  # 主介面
    └── uml.html    # 系統架構圖
```

## API 端點

| 方法 | 路由 | 說明 |
|------|------|------|
| GET | `/api/decisions` | 取得所有決策 |
| POST | `/api/decisions` | 新增決策 |
| DELETE | `/api/decisions/<id>` | 刪除決策 |
| POST | `/api/decisions/<id>/complete` | 標記完成 |
| POST | `/api/decisions/<id>/options` | 新增選項 |
| PUT | `/api/options/<id>` | 更新選項 |
| DELETE | `/api/options/<id>` | 刪除選項 |
| GET | `/api/decisions/<id>/analyze` | 分析並推薦最佳選項 |
