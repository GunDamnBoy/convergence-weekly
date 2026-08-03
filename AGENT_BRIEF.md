# 主題匯流訊號報 · AGENT_BRIEF

> **這份是規格。** 流程骨架在排程任務的 prompt 裡（見 `MAINTENANCE.md` 第 3 節）。
> 兩份是一組，改了規格就要同步改排程 prompt——這是既有兩套系統歷史上最常犯的錯。

---

## 0. 這套系統要解決什麼問題

三個知識庫目前各自獨立運作，沒有任何機制在做**跨庫比對**：

| 庫 | 性質 | 單獨看能回答 |
|---|---|---|
| 投顧知識庫 | 敘事．每日．新聞 | 發生了什麼 |
| 節目知識庫 | 敘事．每日．專業討論 | 聰明人在想什麼 |
| AI 泡沫監控 | **量化**．每交易日．自動抓取 | 客觀狀態是什麼 |

把三個疊起來才看得到的訊號有四種，這是本系統唯一的產出：

| 訊號 | 定義 | 為什麼有價值 |
|---|---|---|
| **三方共振** | 三個獨立來源同時指向同一件事 | 最強訊號。量化與敘事各自到達同一結論，幾乎不可能是雜訊 |
| **關鍵背離** | 敘事在講、指標沒動（或反過來） | **本系統的核心價值**。敘事會提前、指標會落後，落差就是可交易的時間差 |
| **共識裂縫** | 一庫已收斂、另一庫仍在對撞 | 市場定價可能跑在證據前面 |
| **單邊訊號** | 只有一庫在講 | 尚未被定價的早期訊號。只標記，不判斷 |

**產出不是資訊，是訊號的合成。**
如果某一期讀起來像「本週新聞回顧」，那就是做失敗了。

---

## 1. 資料來源

三庫皆為公開 GitHub repo，**用 `git clone --depth 1` 取得，不要用 WebFetch 逐檔抓**
（單日檔 100–300KB，WebFetch 會用小模型摘要，資料會失真）。

```
https://github.com/GunDamnBoy/advisory-knowledge-hub     → data/YYYY-MM-DD.json、data/index.json
https://github.com/GunDamnBoy/podcast-knowledge-digest   → data/YYYY-MM-DD.json、data/index.json
https://github.com/GunDamnBoy/ai-bubble-monitor          → data.json（單檔，含 15 天 history）
```

> **架構優勢：資料全部公開，本系統不需要連上本機、不需要 launchd。**
> 這與既有兩套系統不同，維護負擔低很多。唯一需要本機的環節是最後的 git push
> （由既有的 `com.kenny.dashpush` 每 180 秒自動處理）。

### 1.1 三庫的資料結構

**投顧知識庫**
```
date, weekday, stamp, headline, keptDates, cards(數量), overview{snap,focus}, essay,
sections[{title,en,id,intro,groups[{label,accent,cards[]}]}], about{run}
card: {src, tag, tagcls, date, deep(bool), title, body[], bullets[], url, tone}
```

**節目知識庫**
```
date, label, generatedAt, crossCut{title,intro,points[{title,body}]}, postscript,
episodes[{id,showKey,show,title,meta,published,hosts,guest,source,url,chars,
          summary,takeaways,sections,quotes}]
```
⚠️ `takeaways` / `sections` / `meta` 是**字串化的 Python list**，要用 `ast.literal_eval`，不是標準 JSON。

**AI 泡沫監控**（單一 `data.json`）
```
meta{built,lastAutoRun}, composite(float), dims{D1..D6}, dimMeta{D1..D6:{name,w,note}},
zones[], indicators[{id,dim,name,value,disp,score,zone,anchors,dir,asof}],   ← 21 項
tw{heat, items[{id,name,value,disp,score,note,src,asof}]},
stage{current,label,stages[],checklist[{item,state,evi}],note},
events[{d,t,url}], history[{date,composite,dims{},tw}], charts{}, params{}
```
`history` 保留約 15 個交易日，這是計算「本期變動」的來源。

---

## 2. 時間窗口與節奏

- 每週日台北 **21:30** 執行（排在投顧知識庫週日夜間更新之後，確保拿得到當週最新一天）。
- **敘事側**取過去 7 個日曆天；**量化側**取 `history` 全部（約 15 個交易日），
  「本期變動」以 history 第一筆對最後一筆計算。
- 三庫日期不會對齊——投顧有週日更新、節目只有工作日、監控只有交易日。
  **這是正常的，不要試圖對齊。** 如實記錄實際涵蓋範圍，寫進 `range` 與頁尾。
- 缺天不是失敗。但若投顧側 < 3 天或節目側 < 2 天，必須在 `about.run` 註明樣本偏薄，
  且**共振判定要保守**（樣本薄時容易把巧合當共振）。

---

## 3. 產出格式：站台架構

比照既有兩庫：**外殼與資料分離，歷史全部保留。**

```
convergence-weekly/
├─ index.html            ← 外殼。極少需要動
├─ data/
│   ├─ index.json        ← 期別清單 ＋ 每期量化快照（跨期趨勢圖靠它）
│   └─ YYYY-MM-DD.json   ← 每期一檔，永不刪除、永不改寫
├─ build_issue.py        ← schema 的可執行文件（第 001 期範例）
├─ AGENT_BRIEF.md        ← 本檔（規格）
├─ MAINTENANCE.md        ← 維護說明、排程 prompt、事故紀錄
└─ README.md
```

### 3.1 單期 JSON schema

```jsonc
{
  "date":"2026-08-03", "issue":1, "label":"第 001 期 · ...", "stamp":"...",
  "range":{"quant":"...","narrative":"..."},
  "headline":"一句話，要有觀點，不是主題標籤",
  "coverage":[{"k":"投顧知識庫","v":"3 天 / 約 420 則卡片"}, ...],
  "verdict":["段1","段2","段3"],              // 必須表態，允許 HTML 粗體
  "quant":{
    "composite":53.5, "zone":"過熱警戒區（45–65）", "note":"兩週前 ...",
    "stage":{"current":2.6,"label":"...","lit":"2.5／6","delta":"本週無新增點亮"},
    "twHeat":57.3,
    "dims":[{"id":"D1","name":"...","w":"25%","v":58.2,"delta":-4.3,"note":"...",
             "emph":true,      // 選填：這一維是本期重點，標題加粗
             "zeroish":true}], // 選填：值接近 0，長條改用灰色並給最小寬度
    "callout":{"h":"...","body":"..."}
  },
  "sections":[{"id":"resonance","title":"一 · ...","lede":"...","items":[ITEM]}],
  "watch":["..."],      // 下週該盯什麼：可觀察、可證偽
  "feedback":["..."],   // 回饋給來源系統的建議（選填）
  "gaps":["..."],       // 發現的資料缺口
  "about":{"run":"...","method":"..."}
}
```

`ITEM` 的欄位（全部選填，外殼會按順序渲染有值的部分）：
```jsonc
{
  "hot":true,                                  // 紅框強調
  "tags":[{"t":"三方共振 · 最強","cls":"r"}],    // cls: "r"=實心紅, "o"=紅外框, 省略=灰
  "title":"...",
  "body":["段1","段2"],                         // 純段落
  "cols":[{"h":"量化側","body":"..."}],          // 2 或 3 欄對照，外殼自動判斷欄數
  "list":[{"body":"...","src":"..."}],          // 條列式（單邊訊號用）
  "evidence":[{"d":"08/01","s":"監控","t":"..."}], // s: 監控/投顧/節目
  "call":{"h":"對投顧的含義","body":"..."}
}
```

### 3.2 index.json

```jsonc
{
  "updated":"ISO8601 +08:00", "updatedLabel":"8/3 21:30", "count":N,
  "issues":[{                     // 依日期由新到舊
    "date":"2026-08-03","issue":1,"label":"...","short":"8/3","headline":"...",
    "composite":53.5,"dims":{"D1":58.2,...},"twHeat":57.3,"stage":2.6,
    "file":"data/2026-08-03.json"
  }]
}
```
> **`composite` / `dims` / `twHeat` / `stage` 是跨期趨勢圖的唯一資料來源。**
> 每期都必須寫，否則趨勢圖會斷。這也是本系統相對於「翻舊文章」的關鍵差異。

---

## 4. 執行管線

### 第 1 步：取資料（程式）
三庫 clone，取窗口內檔案。記錄實際涵蓋範圍。

### 第 2 步：壓縮成摘要層（程式，**不要把原始 JSON 讀進上下文**）
- `adv.txt`：每卡一行 `{★if deep}({src}/{tag}) {title} || {bullets[0] 前 110 字}`，
  依日期與 group 分層，保留每日 `headline` 與 `overview.snap`。目標 40–60K 字。
- `pod.txt`：每集三行（`▸{show}｜{title}` / 摘要前 420 字 / 每條 takeaway 的 title），
  **完整保留每日 `crossCut`**（這是 pod 側最濃縮的部分，不可省略）。目標 12–20K 字。
- `bub.txt`：composite ＋ 六維現值與變動 ＋ 21 項指標（含 `zone`、`score`、`asof`）
  ＋ `stage` 全文與 checklist ＋ `tw` ＋ `events`。這份很小，可直接讀。

超過目標大小就縮 body 截斷長度，**不要減少卡片則數**——覆蓋率比細節重要。

### 第 3 步：兩個子代理平行萃取敘事側（**必須平行、必須互相看不到對方的檔案**）
理由：同一個上下文同時讀兩庫，會不自覺讓先讀的框住後讀的，「共振」就變成自我實現的預言。

- **子代理 A（讀 adv.txt）** → 8–14 個主題：敘事重心、出現強度、**有無轉向**、3–5 條逐字佐證；
  另附「只出現一次但值得注意的訊號」5–8 條。
- **子代理 B（讀 pod.txt）** → 8–12 個主題：核心主張、**講者分歧（最重要）**、出現強度、
  2–4 條逐字佐證；另附「podcast 已在講但新聞沒跟上的事」5–8 條。

兩者都要求：**佐證逐字取自檔案，寧可少寫也不要編。**

### 第 4 步：主線合成（**不可外包**）
合成需要同時握有三邊，這是整套系統唯一無法拆分的環節。
量化側由主線自己讀 `bub.txt`——它很小，而且它是裁判，不該經過另一個模型的轉述。

**比對的順序有講究**：先把量化側的六維變動攤開，再拿兩份敘事主題去對。
反過來做（先讀敘事再看指標）會讓你只找得到「指標支持敘事」的部分，找不到背離。

### 第 5 步：寫檔與發布
1. 寫 `data/YYYY-MM-DD.json`
2. 更新 `data/index.json`（含該期量化快照）
3. 交給既有的 `com.kenny.dashpush` 自動推送
4. 驗證線上狀態時**網址一定要帶 cache-buster**，並確認 `updatedLabel` 而不只是 `issues[0].date`

### 第 6 步：驗證（不可略過）
寫 Python 檢查，把本期每一條 `evidence.t` 的關鍵子字串拿回 `adv.txt` / `pod.txt` / `bub.txt`
做 substring 比對。任何一條找不到，就修正該條引用或刪除它，然後**重跑檢查直到全部通過**。

---

## 5. 品質規則（違反其中任一條就是這期做壞了）

- **佐證一律逐字。** 引卡片標題、集數標題、交叉觀察原文、指標欄位，不改寫、不潤飾。
  引自 `crossCut` 的內容要標明「當日交叉觀察，引 ○○節目」，**不可偽裝成集數標題**。
- **量化佐證要附欄位名。** 寫 `指標 hyoas = 2.84%、zone green、score 25.8`，
  不要寫「高收益債利差偏低」——前者可回查，後者不行。
- **背離那一節必須給出裁判方法。** 只說「兩邊不一致」沒有價值；
  要寫「用什麼數字、跨過什麼門檻，就知道哪一邊對」。
- **不要為了湊滿章節而硬掰。** 某週真的沒有背離，就寫「本週三庫高度一致，這本身是訊號」。
- **不要重述新聞。** 每一條都要包含「因為三庫都／只有一庫講，所以⋯⋯」這層推論。
- **單邊訊號只標記不判斷。** 這是紀律，避免把未驗證的東西講成結論。
- **數字打架就寫出來。** 三庫對同一數字有出入時，把出入本身當成發現，不要挑一個用。
- **記錄資料缺口。** 缺天、`updatedLabel` 過期、指標 `asof` 落後、卡片數異常，
  一律寫進 `gaps`——**這套系統順便是另外三套系統的健康度哨兵**。
- 全程繁體中文（台灣用語）。

---

## 6. 變更紀錄

| 日期 | 版本 | 改了什麼 | 為什麼 |
|---|---|---|---|
| 2026-08-03 | v0.1 | 雙庫（投顧＋節目）原型，單一 HTML 交付 | 驗證跨庫比對能產生單庫看不到的訊號。實測雙向落差都存在：pod 側的「Warsh 刻意要波動度」假說在 adv 側 0 次出現；adv 側的記憶體成本傳導在 pod 側完全沒有主題。 |
| 2026-08-03 | v0.2 | 接入 **AI 泡沫監控**成為第三庫；新增「關鍵背離」章節 | 前兩庫都是敘事，可能一起錯。加入不看新聞的量化庫後，才出現本系統目前最有價值的一條訊號：「敘事在講信用危機、但 HY OAS 三個月是收斂的」——這種訊號雙庫版**結構上不可能產生**。 |
| 2026-08-03 | v0.3 | 改為 GitHub Pages 站台（外殼＋每期 JSON 全保留）；執行時間定為**每週日 21:30**；index.json 加入每期量化快照以支援跨期趨勢圖 | 使用者要求比照既有兩庫上網並保留歷史，便於前後對照觀察趨勢；週日產出讓週一開盤前就有方向。量化快照入 index 是為了讓「趨勢」是真的可畫，而不只是能翻舊文章。 |

### 待決事項

1. **投顧知識庫目前只保留 3 天封存檔**（2026-08-03 觀察）。若長期如此，7 天窗口實際
   只會拿到 3–4 天的新聞側資料，共振判定的樣本會偏薄。
   要嘛延長保留天數，要嘛本系統改為每週自行留存快照。
2. 是否加入第四個來源（券商報告 PDF）作為第四個比對面。四方比對的訊號品質會更高，
   但需要一個穩定的報告輸入管道。
3. `feedback` 章節目前是人看了再處理。若累積穩定，可考慮讓它自動開 issue 到對應的 repo。
