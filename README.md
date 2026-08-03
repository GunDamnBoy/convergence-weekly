# 主題匯流訊號報

把三個各自獨立運作的知識庫疊在一起，每週產出一份**訊號合成**——
不是新聞回顧，是「三個獨立來源放在一起才看得到的東西」。

🔗 https://gundamnboy.github.io/convergence-weekly/

## 來源

| 庫 | 性質 |
|---|---|
| [advisory-knowledge-hub](https://github.com/GunDamnBoy/advisory-knowledge-hub) | 敘事．每日．新聞 |
| [podcast-knowledge-digest](https://github.com/GunDamnBoy/podcast-knowledge-digest) | 敘事．每日．專業討論 |
| [ai-bubble-monitor](https://github.com/GunDamnBoy/ai-bubble-monitor) | **量化**．每交易日．自動抓取 |

## 四種訊號

- **三方共振** — 三個獨立來源同時指向同一件事
- **關鍵背離** — 敘事在講、指標沒動（或反過來）。本系統的核心價值
- **共識裂縫** — 一庫已收斂、另一庫仍在對撞
- **單邊訊號** — 只有一庫在講。只標記，不判斷

## 節奏

每週日台北 21:30 更新。歷史全部保留，`data/index.json` 存有每期的量化快照，
站台會據此畫出跨期趨勢。

## 檔案

```
index.html          外殼，極少需要動
data/index.json     期別清單 ＋ 每期量化快照
data/*.json         每期一檔，永不刪除、永不改寫
build_issue.py      schema 的可執行文件
AGENT_BRIEF.md      規格
MAINTENANCE.md      維護說明、排程 prompt、事故紀錄
```

規格見 [AGENT_BRIEF.md](AGENT_BRIEF.md)，維護見 [MAINTENANCE.md](MAINTENANCE.md)。
