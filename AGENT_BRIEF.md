# 主題匯流訊號報 · AGENT_BRIEF

> **這份是規格，含完整的執行管線定義（第 4 節）。**
> 排程任務的 prompt 是這份管線的**執行骨架**——只放順序與分支判斷，
> 細節（門檻、字數、格式、禁令）一律回這份查。見 `MAINTENANCE.md` 第 3 節。
> 兩份是一組，改了規格就要同步改排程 prompt——這是既有兩套系統歷史上最常犯的錯。

---

## 0. 這套系統要解決什麼問題

四個知識庫目前各自獨立運作，沒有任何機制在做**跨庫比對**：

| 庫 | 性質 | 單獨看能回答 | 獨立性 |
|---|---|---|---|
| 投顧知識庫 | 敘事．每日．新聞 | 發生了什麼 | 獨立 |
| 節目知識庫 | 敘事．每日．專業討論 | 聰明人在想什麼 | 獨立 |
| AI 泡沫監控 | **量化**．每交易日．自動抓取 | 客觀狀態是什麼 | 獨立（不看新聞） |
| 每日五圖 | **量化重製**．每日．自行製圖 | 敘事講的事，數字是多少 | **選題與投顧同源** |

> ⚠️ **每日五圖不是第四個獨立來源。**
> 它的 `about.upstream[0]` 就是 `advisory-knowledge-hub` 的當日檔——選題是從投顧庫挑出來的。
> 所以「投顧在講 ＋ 圖表也在畫」**不構成兩票**，那是同一則新聞被數兩次，
> 跟「量化佐證取自 `events`」是同一個坑，只是換了層皮。
>
> 它真正的價值在另一半：**圖表的數字是自行從 Yahoo／FRED 重製的**，
> 所以它是**量化側的第二個裁判**——把敘事講的模糊說法逼成一個可回查的數字
> （「油價崩了」→ 自 3/31 高點 −32.9%）。角色定位與計票規則見第 5 節。

把它們疊起來才看得到的訊號有四種，這是本系統唯一的產出：

| 訊號 | 定義 | 為什麼有價值 |
|---|---|---|
| **三方共振** | 三個獨立來源同時指向同一件事 | 最強訊號。量化與敘事各自到達同一結論，幾乎不可能是雜訊 |
| **關鍵背離** | 敘事在講、指標沒動（或反過來） | **本系統的核心價值**。敘事會提前、指標會落後，落差就是可交易的時間差 |
| **共識裂縫** | 一庫已收斂、另一庫仍在對撞 | 市場定價可能跑在證據前面 |
| **單邊訊號** | 只有一庫在講 | 尚未被定價的早期訊號。只標記，不判斷 |

**產出不是資訊，是訊號的合成。**
如果某一期讀起來像「本週新聞回顧」，那就是做失敗了。

> ⚠️ **訊號類型 ≠ 章節結構。** 上表是四種**訊號類型**，不是四個章節。
> 章節結構固定為七節（見第 3.0 節），其中「共識裂縫」沒有專屬章節——
> 它是可以掛在任何一節某條 item 上的 `tags` 標籤。
> 理由：裂縫不是每週都有，硬留一個常常空著的章節會逼出湊數的內容。
> 反過來，章節裡有兩節不是訊號類型而是**閱讀切面**：
> 「台股」（使用者的實際部位在台股，不管訊號屬哪一類都額外集中講一次）
> 與「圖表側寫」（每日五圖把敘事逼成數字，值得單獨看一輪）。

---

## 1. 資料來源

四庫皆為公開 GitHub repo，**用 `git clone --depth 1` 取得，不要用 WebFetch 逐檔抓**
（單日檔 100–300KB，WebFetch 會用小模型摘要，資料會失真）。

```
https://github.com/GunDamnBoy/advisory-knowledge-hub     → data/YYYY-MM-DD.json、data/index.json
https://github.com/GunDamnBoy/podcast-knowledge-digest   → data/YYYY-MM-DD.json、data/index.json
https://github.com/GunDamnBoy/ai-bubble-monitor          → data.json（單檔，含約 17 天 history）
https://github.com/GunDamnBoy/chart-of-the-day           → data/YYYY-MM-DD.json、data/index.json
```

> **架構優勢：取資料這一段全部公開，不需要本機、不需要自建轉錄管線。**
> 這與既有兩套系統不同（那兩套要讀本機逐字稿／要跑抓取），維護負擔低很多。
> **但發布這一段仍然依賴本機**：用 `device_commit_files` 寫回 `~/convergence-weekly`，
> 再由既有的 launchd agent `com.kenny.dashpush` 每 180 秒 push 上去。
> 連不到本機時的退路見第 4 節第 7 步。

### 1.1 四庫的資料結構

**投顧知識庫**
```
date, weekday, stamp, headline, keptDates, cards(數量), overview{snap,focus}, essay,
sections[{title,en,id,intro,groups[{label,accent,cards[]}]}], about{run}
card: {src, tag, tagcls, date, deep(bool), title, body[], bullets[], url, tone}
index.json: updated, updatedLabel, count, days[]          ← 健康度哨兵要看這兩欄
```

**節目知識庫**
```
date, label, generatedAt, crossCut{title,intro,points[{title,body}]}, postscript,
episodes[{id,showKey,show,title,meta,published,hosts,guest,source,url,chars,
          summary,takeaways,sections,quotes}]
index.json: updated, updatedLabel, count, days[]          ← 同上
```
> 單期檔本身沒有 `updated` / `updatedLabel`，那兩欄在各庫的 `index.json`。
> 第 5 節「記錄資料缺口」要檢查的就是這兩欄有沒有停住——實測第 001 期就抓到節目庫
> 連兩次執行沒更新 `updated`，前端顯示時間是錯的。
⚠️ `takeaways` / `sections` / `meta` 是**字串化的 Python list**，要用 `ast.literal_eval`，不是標準 JSON。

**AI 泡沫監控**（單一 `data.json`）——**2026-08-04 起為 v2 架構**
```
meta{version:2,built,lastAutoRun}, composite(float),
dims{L1,L2,L3}, dimMeta{L1..L3:{name,w,note}},          ← v2：三層，w 加總 = 1.0
quadrant{heat,support,regime},                          ← v2 新增
triggers[{id,name,state,value,note,asof}],              ← v2 新增
zones[], indicators[{id,dim,name,value,disp,score,zone,anchors,dir,asof}],   ← 22 項
tw{heat, items[], subs, subWeights, officialPE, idx_hist, margin_hist, revTable, revMonth},
stage{current,label,stages[],checklist[{item,state,evi}],note},
events[{d,t,url}], history[{date,composite,dims{},tw}], charts{}, params{}
```

> ⚠️ **v1 → v2 是不可換算的改版。** 2026-08-03 以前是六維 `D1`–`D6`（按主題分群），
> 08-04 起是三層 `L1`／`L2`／`L3`（按資料更新頻率分群）：
> L1 市場與情緒 0.35／L2 資金與信用 0.35／L3 基本面兌現 0.30。
> **兩者不是同一組東西，禁止互相映射。** 硬接起來就是假的趨勢，
> 而跨期趨勢正是本系統相對於「翻舊文章」的唯一差異。
>
> `history` 內 08-03 以前的舊筆 `dims` 仍是 `D1`–`D6`，這是監控庫刻意保留的。
> **算「本期變動」時，基準只能取與現值同一組鍵的最早一筆**，不可跨改版相減。
> `verify.py` 已實作這條，跨架構會直接擋下。
>
> `indicators` 的 id 在 v2 也全換了（`cape`／`mag7`／`gsy_runup`…），
> 舊期引用的 `hyoas`／`circular` 等在新版不存在。

**每日五圖**
```
date, weekday, headline, standfirst, window{data_asof,note},
about{upstream[], run, qa_flags[{chart,series,date,pct,z}]},
charts[5]{slug, slot, theme, title, subtitle, kind, source, note,
          series[{name,dates[],values[],color,axis,style}],   ← 很大，勿讀進上下文
          markers[], takeaway, reading, so_what, watch[], tags[],
          provenance{inspired_by{outlet,title,url}},           ← slot「重製圖」必填
          files{png,svg}, option{...}}                         ← ECharts 設定，勿讀
index.json: title, updated, days[{date,weekday,headline,charts,themes[],slots[]}]
```
> ⚠️ **單日 100KB，其中 96KB 是 `option` 與 `series`——這兩個欄位絕對不要讀進上下文。**
> 真正有用的判讀（`takeaway`＋`reading`＋`so_what`）全部加起來只有約 2,400 字。
> 五個 slot 固定為：當日主圖／市場異動圖／重製圖／主題深掘／軌道圖｜〈軌道名〉。
> `about.qa_flags` 是圖表庫自己標記的資料品質疑慮，**要轉寫進本報的 `gaps`**。
> 注意它的 `index.json` **沒有 `updatedLabel` 也沒有 `count`**（只有 `title`／`updated`／`days[]`），
> 所以第 5 節「查各庫 `updatedLabel` 有沒有停住」那條哨兵規則對這一庫不適用，
> 改看 `updated` 與 `window.data_asof`。

---

## 2. 時間窗口與節奏

- 每週日台北 **21:30** 執行（投顧與圖表庫早上更新、節目庫凌晨更新，排在晚上確保四庫當天的檔都到齊）。
  排程 cron `30 21 * * 0`，**本地時間、非 UTC**（詳見 `MAINTENANCE.md` 第 3 節的警語）。
- **敘事側**（投顧、節目、每日五圖）取過去 7 個日曆天；
  **量化側**取 `history` 全部（約 17 個交易日），
  「本期變動」＝**頂層 `dims` 現值 − `history` 中與現值同一組鍵的最早一筆**。
  > 兩個容易寫錯的地方：
  > ① 是「對**現值**」，不是「對 `history` 最後一筆」——監控庫盤後更新時 `history`
  >   會落後頂層一格，兩者不相等。
  > ② 基準**必須與現值同架構**。`history` 跨越了 2026-08-04 的 v1→v2 改版，
  >   08-03 以前是 `D1`–`D6`、之後是 `L1`–`L3`，取到舊筆就是拿三層去減六維。
  > 兩條 `verify.py` 都會擋。
- 四庫日期不會對齊——投顧與圖表庫每天更新、節目只有工作日、監控只有交易日。
  **這是正常的，不要試圖對齊。** 如實記錄實際涵蓋範圍，寫進 `range`。
  > `range` 記錄的是**實際拿到的涵蓋範圍**，不是上面那個 7 天窗口。
  > 兩者不相等是正常的（第 001 期窗口 7 天、實際敘事側只涵蓋 6 天），不要為了對齊窗口而虛報。
- 缺天不是失敗。但若投顧側 **≤ 3 天**或節目側 ≤ 2 天，必須在 `about.run` 註明樣本偏薄，
  且**共振判定要保守**（樣本薄時容易把巧合當共振）。
  每日五圖 2026-08-05 才開始運作，**前幾期天數必然偏少**，
  少於 3 天時「圖表側寫」那一節就寫「本期樣本不足，只列可用的幾張」，不要硬湊五張。

### 2.1 零新增資料時不產期

若重新取回的四庫資料與上一期**完全相同**（例如同一天內重跑、或所有來源都還沒更新），
**不要產期**。要產就得覆寫既有單期檔（違反永不改寫）或把日期虛報成隔天（違反涵蓋範圍如實記錄），
兩條路都是壞的。

正確做法：**停下來，在交付訊息裡寫明「本次未產期」與原因（各庫的實際最新日期）**，
不寫任何檔案。這不是失敗，是設計。

> 2026-08-03 排程建立後首次手動觸發就遇到這個情況，當時是靠臨場判斷停下來的；
> 寫進規格是為了讓它變成必然，不是每次都賭運氣。

---

## 3. 產出格式：站台架構

比照既有兩庫：**外殼與資料分離，歷史全部保留。**

```
convergence-weekly/
├─ index.html            ← 外殼。極少需要動
├─ data/
│   ├─ index.json        ← 期別清單 ＋ 每期量化快照（跨期趨勢圖靠它）
│   └─ YYYY-MM-DD.json   ← 每期一檔，永不刪除、永不改寫
├─ build_issue.py        ← **已凍結在第 001 期（v1 六維、4 節），不要照抄它的結構。**
│                          它示範的是「怎麼寫檔、怎麼更新 index.json」這層機制
│                          （含保留 errata、防覆寫閘門），那部分與版本無關仍然有效。
│                          現行 schema 一律以本節為準
├─ prepare.py            ← **備料**（每週第 1–2 步）：clone 四庫、產出四份摘要層、
│                          印 PREP.md（涵蓋統計＋上期 watch＋triggers 狀態＋零新增判定）。
│                          排程只跑它，不要自己寫摘要程式
├─ make_index.py         ← **index 快照組裝**（第 5 步後半）：從單期 JSON 自動組
│                          quantVer／quadrant／trigLit／updated，保留 errata
├─ verify.py             ← **發布前檢查**。每期必跑，不要自己重寫一支
├─ healthcheck.py        ← 維護用的唯讀健康檢查（跑在維護時，不在產出流程裡）
├─ AGENT_BRIEF.md        ← 本檔（規格）
├─ MAINTENANCE.md        ← 維護說明、排程 prompt、事故紀錄
├─ CHANGELOG.md          ← 逐版變更紀錄、度量趨勢、回溯要點（維護者才讀）
└─ README.md
```

### 3.0 章節結構（固定七節）

「零」由外殼寫死；中間各節由 `sections` 驅動，**編號寫在各節自己的 `title` 字串裡**；
尾巴兩節的編號由外殼**依 `sections` 長度動態計算**。
`sections` 的 id 與順序必須是下表那五個，`verify.py` 會擋。

| # | id | 節名 | 規則 |
|---|---|---|---|
| 零 | —（外殼寫死） | 量化底盤 | 不是新聞，是這段期間的客觀狀態。由 `quant` 驅動 |
| 一 | `resonance` | 三方共振 | 三個**獨立**來源同時指向。量化佐證不得取自 `events`；**投顧與圖表計為同一票** |
| 二 | `divergence` | 關鍵背離 | **必須給裁判方法**：用什麼數字、跨過什麼門檻就知道哪一邊對。**優先引用 `triggers` 裡已定義的門檻**，見下方 |
| 三 | `taiwan` | 台股 | 閱讀切面。各庫講台股時常在不同層次，把層次差寫出來 |
| 四 | `charts` | **圖表側寫** | 閱讀切面。**敘事講的事，圖表算出來是多少**——見下方規則 |
| 五 | `single` | 單邊訊號 | **只標記不判斷**。用 `list[]` 而非 `evidence[]`，但一樣要逐字 |
| 六 | —（外殼寫死） | 下週該盯什麼 | 由 `watch[]` 驅動。每條可觀察、可證偽 |
| 七 | —（外殼寫死） | 回饋給來源系統 | 由 `feedback[]` 驅動。選填，沒有就不出現 |

**第二節「關鍵背離」的裁判方法要優先引用 `triggers`：**

監控庫 v2 提供 7 條**已經定義好門檻的觸發器**（`hy80` HY 利差 3 個月走闊 ≥80bp、
`ccc12` CCC 利差 ≥12%、`gsy150` SOXX 24 個月漲幅 ≥150%、`cpi4` CPI 年增 ≥4%、
`policy_gap` 政策利率 ≥ 名目 GDP 成長、`y10_5` 美債 10 年 ≥5%、`megaipo` 巨型 IPO 完成），
每條都附 `state`（0／1）與當前 `value`。

- 背離的裁判方法**先看有沒有現成的 trigger 對得上**，有就直接引用它的門檻與 `state`。
  自己另外定義門檻是次選——現成的那組是客觀、跨期一致、且會自動更新的。
- `watch[]` 也一樣：**能對應到 trigger 的條目要寫出 trigger id**，
  下一期驗收時就是查 `state` 有沒有翻轉，不必再靠人工判斷。
  第 001 期的 watch 有一條「10 年期美債升破 5%」當時在監控庫沒有對應欄位、無法程式化驗收，
  v2 的 `y10_5` 正好補上——這條回饋迴圈是閉合的。
- 7 條全部帶進 `quant.triggers`，**不要挑**。沒亮的那幾條本身就是資訊
  （「這些事都還沒發生」是一個判斷，不是空白）。

**第四節「圖表側寫」的規則：**

- 這一節的職責是**數字落地**：把其他各庫用形容詞講的事，換成圖表庫算出來的具體數字。
  「敘事說油價崩了 → 圖表算出自 3/31 高點 −32.9%」這種句型才是這一節要的。
- **證據只能取自圖表庫自行重製的數字**（`series` 算出來的變動、`takeaway` 裡的數值）。
  它的選題來自投顧庫，所以**選題本身不是證據**——不要寫「圖表庫也關注這件事」。
- 五張圖不必每張都寫。挑**能和其他庫對話的**，其餘略過。
- 圖表庫的判讀（`so_what`）與其他庫矛盾時，**把矛盾寫出來**，不要挑一邊。
- `about.qa_flags` 轉寫進本報的 `gaps`。

「共識裂縫」不是章節，是掛在 item 上的 `tags` 標籤（見第 0 節）。
要增減章節數或動 schema，**這一組要一起改**：本節、`index.html`、
`verify.py` 與 `healthcheck.py`（`CANON` 與必備欄位）、`make_index.py` 與 `prepare.py`
（前者硬依賴 `quant` 的欄位、後者硬依賴上一期的 `watch` 與 index 條目）。
`build_issue.py` 已凍結，不在組內。

> 第 001 期是 4 節（無 `charts`），`verify.py` 以 `LEGACY` 清單放行。
> 舊期不回頭補寫——歷史全部保留的另一面是歷史不美化。

### 3.1 單期 JSON schema

```jsonc
{
  "date":"2026-08-03", "issue":1, "label":"第 001 期 · ...", "stamp":"...",
  "range":{"quant":"...","narrative":"..."},
  "headline":"一句話，要有觀點，不是主題標籤",
  "coverage":[{"k":"投顧知識庫","v":"3 天 / 約 420 則卡片"}, ...],
  "verdict":["段1","段2","段3"],              // 固定 3 段。必須表態，允許 HTML 粗體
  "quant":{
    "schemaVer":"v2",                          // v2 必填。標明讀到的監控庫架構
    "composite":66.6, "zone":"高風險區（65–80）", "note":"兩週前 ...", // note 必填，外殼直接印
    "stage":{"current":2.6,"label":"...","lit":"2.5／6","delta":"本週無新增點亮"},
    "twHeat":57.3,
    // v2 必填。heat ＝（L1＋L2）／2；support ＝ 100 − L3。兩個公式由監控庫定義，直接取用不要自己算
    "quadrant":{"heat":68.0,"support":63.9,"regime":"過熱但有撐（melt-up 風險）"},
    // v2 必填。直接抄監控庫的 triggers，id 與 state 不得改；7 條全帶，不要挑
    "triggers":[{"id":"hy80","name":"HY 利差 3個月走闊 ≥80bp","state":0,
                 "value":"+0bp/3M","asof":"2026-08-03"}],
    "dims":[{"id":"L1","name":"市場與情緒","w":"35%","v":65.5,"delta":-4.3,"note":"...",
             "emph":true,      // 選填：這一維是本期重點，標題加粗
             "zeroish":true}], // 選填：值接近 0，長條改用灰色（＝「別當訊號讀」）。
                               // 長條的最小寬度是外殼無條件的安全網，與本旗標無關
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
  "evidence":[{"d":"08/01","s":"監控","t":"..."}], // s 是封閉集合，只有這四個值：
                                                 // 監控／投顧／節目／圖表。打錯字 verify.py 會 FAIL
  "call":{"h":"對投顧的含義","body":"..."}
}
```

**兩個外殼沒明講、但 `verify.py` 硬依賴的慣例：**

1. **量化佐證必須用 `<code>欄位名</code>` 包住欄位名。**
   ```
   ✅ "t":"指標 <code>hyoas</code> = 2.84%、zone green、score 25.8、三個月 −14bp"
   ❌ "t":"高收益債利差偏低"
   ```
   `verify.py` 用 `<code>([a-z0-9_]+)</code>` 抓出 id 去 `bub` 裡查存在性。沒包 `<code>` 的那條
   不會 FAIL，但檢查形同空轉，會出 warn。合法欄位名＝指標 id（v2 為 22 項，動態讀取）＋ 台股項目 id
   ＋ `stage` / `composite` / `twheat` / `quadrant` / `heat` / `support`
   ＋ 維度 id（兩代並存：v1 的 `d1`–`d6`、v2 的 `l1`–`l3`）。

2. **body 類欄位允許行內 HTML。** `verdict[]`、`cols[].body`、`call.body`、`list[].body`、
   `callout.body`、`watch[]`、`feedback[]`、`gaps[]`、`evidence[].t` 都可用
   `<b>` / `<code>` / `<br>`。逐字回查時 `verify.py` 會先剝標籤，所以加粗不影響驗證。

3. **`list[]` 一樣要逐字回查。** 單邊訊號整節用 `list` 而非 `evidence`，
   但「佐證一律逐字」是無條件的；`src` 裡含「監控」的視為量化側。

### 3.2 index.json

```jsonc
{
  "updated":"ISO8601 +08:00", "updatedLabel":"8/3 21:30", "count":N,
  "issues":[{                     // 依日期由新到舊
    "date":"2026-08-09","issue":2,"label":"...","short":"8/9","headline":"...",
    "quantVer":"v2",                                    // v2 必填。外殼靠它決定哪幾期能連成一條線
    "composite":66.6,"dims":{"L1":65.5,"L2":70.5,"L3":36.1},
    "quadrant":{"heat":68.0,"support":63.9},            // v2 必填
    "trigLit":0,                                        // v2 必填。已觸發的 trigger 數
    "twHeat":57.3,"stage":2.6,
    "file":"data/2026-08-09.json",
    "errata":["..."]                                    // 選填。發布後才發現的問題，見下
  }]
}
```
> **`composite` / `dims` / `twHeat` / `stage` / `quadrant` / `trigLit` 是跨期趨勢圖的唯一資料來源。**
> 每期都必須寫，否則趨勢圖會斷。這也是本系統相對於「翻舊文章」的關鍵差異。
>
> 外殼分兩組畫，因為監控庫 2026-08-04 改版且兩種分群不可換算：
> **連續組**（全期）`composite`／`stage`／`twHeat`——定義跨版本未變；
> **v2 組**（僅 `quantVer==='v2'` 的期別）`L1`／`L2`／`L3`／`quadrant.heat`／`quadrant.support`／
> `trigLit`，
> 從改版後重新起算，圖上標紅色 `v2` 徽章，並在說明文字寫出斷點位置。
> 累積 4 期後檢視這九格選得對不對（見第 6 節待決事項）。

**`errata`（選填）**：既有單期檔永不改寫，所以**發布後才發現的問題掛在這裡**，
由外殼渲染成期別按鈕下方的黃色橫幅。原文一個字都不動，錯誤在旁邊講清楚。
這是「歷史全部保留」與「不在頁面上說謊」兩條原則唯一能同時滿足的做法。

---

## 4. 執行管線

### 第 1–2 步：備料（跑 `prepare.py`，不要自己寫）

```bash
git clone --depth 1 https://github.com/GunDamnBoy/convergence-weekly.git site
python3 site/prepare.py --work work --site site
```

它做完取資料與壓縮兩步：clone 四庫、依下列規格產出 `work/adv.txt`／`pod.txt`／
`bub.txt`／`cotd.txt`，並印出 `PREP.md`——涵蓋統計與摘要層大小、各庫最新日期（監控庫以 `meta.built` 為準）、
**上一期資訊（期號／headline／errata 數）與 watch 清單全文**（合成時驗收用）、
**triggers 狀態表**、樣本偏薄旗標、零新增資料提示。
**exit 3 ＝ 四庫都沒有比上一期新的資料**，依 §2.1 不產期，直接進交付說明原因。

主線接著只需要讀 `PREP.md` 與摘要層，**不要碰任何原始 JSON**。

**摘要層規格**（＝ `prepare.py` 的實作規格；改這裡就要改它，反之亦然）：

- `adv.txt`：每卡一行 `{★if deep}({src}/{tag}) {title} || {bullets[0] 截斷}`（`bullets` 空時退用 `body[0]`），
  依日期與 group 分層，保留每日 `headline` 與 `overview.snap`。
  目標 ≤60K 字；截斷自動下調 110→80→60→45，到底仍超標則接受並如實回報——
  **不減卡片則數，覆蓋率比細節重要**（來源庫已擴編至 26 家，7 天可達 800+ 卡）。
- `pod.txt`：每集三行（`▸{show}｜{title}` / 摘要截斷 / takeaway titles），
  **完整保留每日 `crossCut`**（不可省略）。目標 ≤24K；摘要截斷自動下調 420→300→220。
- `bub.txt`：composite ＋ 三層現值與變動（同架構基準）＋ `quadrant` ＋ `triggers`
  ＋ 22 項指標（zone/score/asof）＋ `stage`（checklist 的 `evi` 截 80 字）
  ＋ `tw` 的 `heat` 與 `items`（其餘子欄不入摘要）＋ `events` 前 40 則。
- `cotd.txt`：每張圖六至七行（slot｜theme｜title / subtitle / takeaway / so_what /
  reading / watch / tags）＋ 每日 headline＋standfirst ＋ `qa_flags`。
  **不含 `series` 與 `option`**（單日 100KB 裡的 96KB，無判讀價值）。
  目標 ≤15K；超標先截 `reading` 300→200，`takeaway`／`so_what` 一律全文。

### 第 3 步：兩個子代理平行萃取敘事側（**必須平行、必須互相看不到對方的檔案**）
理由：同一個上下文同時讀兩庫，會不自覺讓先讀的框住後讀的，「共振」就變成自我實現的預言。

- **子代理 A（讀 adv.txt）** → 8–14 個主題：敘事重心、出現強度、**有無轉向**、3–5 條逐字佐證；
  另附「只出現一次但值得注意的訊號」5–8 條。
- **子代理 B（讀 pod.txt）** → 8–12 個主題：核心主張、**講者分歧（最重要）**、出現強度、
  2–4 條逐字佐證；另附「podcast 已在講但新聞沒跟上的事」5–8 條。

兩者都要求：**佐證逐字取自檔案，寧可少寫也不要編。**

### 第 4 步：主線合成（**不可外包**）
合成需要同時握有各邊，這是整套系統唯一無法拆分的環節。
**量化側（`bub.txt` 與 `cotd.txt`）由主線自己讀**——兩份都很小，而且它們是裁判，
不該經過另一個模型的轉述。子代理只負責兩個敘事庫。

> 為什麼圖表庫歸量化側、不派第三個子代理：
> 它的選題來自投顧庫，派子代理獨立萃取「主題」只會複述投顧側已經有的東西，
> 平白多一份會製造假共振的材料。它有價值的是**數字**，而數字要精確、要可回查，
> 正是不該被另一個模型壓縮的那種東西。

**比對的順序有講究**：先把量化側（監控庫的層分數與象限、圖表庫的重製數字）攤開，再拿兩份敘事主題去對。
反過來做（先讀敘事再看指標）會讓你只找得到「指標支持敘事」的部分，找不到背離。

**驗收上一期的 `watch` 清單**：上期點名要盯的事，這期發生了嗎？跨過門檻了嗎？
有結果的要寫進本期 `verdict`。這條回圈是本系統會不會累積判斷力的分水嶺——
少了它，每期都是重新開始，`watch` 就只是好看的收尾。

### 第 5 步：寫檔

1. 寫 `data/YYYY-MM-DD.json`（**不得改寫任何既有單期檔**）
2. 跑 `python3 site/make_index.py site/data/YYYY-MM-DD.json`——
   它自動組出快照（`quantVer`／`quadrant`／`trigLit`）、填當下實際發布時間、保留 `errata`。
   **不要手工編輯 `index.json`。**
3. 不要動 `index.html`，除非 schema 真的變了（變了就是一組一起改，清單見第 3.0 節末）

### 第 6 步：驗證（不可略過，跑在推送之前）

**用 repo 內現成的 `verify.py`，不要自己重寫一支。**

```bash
python3 verify.py data/YYYY-MM-DD.json \
  --adv /path/adv.txt --pod /path/pod.txt --cotd /path/cotd.txt \
  --bub /path/bub/data.json
# --index 可省略，預設取 issue 同目錄的 index.json
```

> ⚠️ `--bub` 吃的是**原始 `bub/data.json`**，不是備料壓縮出來的 `bub.txt`；
> `--cotd` 則相反，吃的是**壓縮過的 `cotd.txt`**（它走敘事側 substring 回查）。
> 敘事側才是 substring 回查；量化側做的是欄位名存在性與數值核對。
>
> ⚠️ **四個路徑參數一個都不能省。** 缺任何一個，該批檢查會被整批跳過。
> 三份敘事摘要層（`--adv`／`--pod`／`--cotd`）是**全有或全無**：
> 只給其中一兩份會讓缺的那庫的佐證全部「查不到」而變成假 FAIL，所以缺一個就整批跳過。
> **跳過不算 FAIL，但也不給綠燈**——`verify.py` 會印黃燈並回傳 `exit 2`。
> 「沒有 FAIL」不等於「檢查有跑」；看到黃燈就是還不能發布。

它檢查九件事：必備欄位與章節結構（`sections` 的 id 與順序）、`evidence[].s` 合法值、
`index.json` 量化快照（v2 另驗 `quantVer`／`quadrant`／`trigLit`）、敘事側逐字回查（含 `list[]`）、
**共振的來源獨立性（投顧與圖表計為同一票）**、量化側欄位名存在性、
層／維現值與變動 vs `history`（**不跨改版相減**）、**觸發器對帳（id 與 state 對監控庫、
`trigLit` 對得上）**、量化佐證未取自 `events`。

**任何一項 FAIL 就不要發布。** 回去修正該條引用或刪除它，重跑到全部通過。
若動過 `index.html`，另外抽出 `<script>` 區塊跑 `node --check`。

### 第 7 步：發布與交付

1. 用 `device_commit_files` 寫回本機 `~/convergence-weekly`，
   交給 `com.kenny.dashpush`（每 180 秒）自動推送
   > ⚠️ **不要對本機的 `~/convergence-weekly` 跑任何 git 指令，`git status` 也不行。**
   > `com.kenny.dashpush` 每 180 秒會自己 commit＋push，你跑 git 會留下
   > `.git/index.lock` 把它擋住，之後就再也推不上去。
   > 沙箱裡 clone 出來的複本要怎麼跑 git 都可以，這條只針對本機那一份。
2. **連不到本機時的退路**：改用 `SendUserFile` 附上本期 JSON 與 `index.json`，
   並明確告知使用者需要手動放進 repo——不要靜靜地跳過發布
3. 驗證線上狀態時**網址一定要帶 cache-buster**，
   並確認頁面上的**期別按鈕數量**與**跨期趨勢的點數**，而不只是看 `issues[0].date`
4. 交付訊息寫三行：本期最重要的判斷、**上一期 `watch` 清單的驗收結果**、發現的資料缺口

---

## 5. 品質規則（違反其中任一條就是這期做壞了）

- **佐證一律逐字。** 引卡片標題、集數標題、交叉觀察原文、指標欄位，不改寫、不潤飾。
  引自 `crossCut` 的內容要標明「當日交叉觀察，引 ○○節目」，**不可偽裝成集數標題**。
- **量化佐證要附欄位名，而且要用 `<code>` 包住。**
  寫 `指標 <code>hyoas</code> = 2.84%、zone green、score 25.8`，
  不要寫「高收益債利差偏低」——前者可回查，後者不行。
- **計票時投顧與圖表算同一票。**
  「三方共振」要的是三個**獨立**聲音：敘事新聞側（投顧＋圖表，合計一票）、
  節目側、量化側。每日五圖的選題取自投顧庫，所以「投顧在講＋圖表也在畫」是一票不是兩票。
  `verify.py` 會對 `resonance` 節裡標了「共振」的 item 實際計算獨立聲音數，不足三個直接 FAIL。
- **量化佐證只能取自 `indicators` / `dims` / `stage` / `tw`，絕對不能取自 `events`。**
  `events` 欄位本身就是 Google News。拿它當量化側證據，等於讓**同一則新聞**
  在投顧側算一次、在監控側再算一次，「三方共振」就是假的——
  而共振是這套系統宣稱最強的訊號。`verify.py` 會 FAIL 這種情況。
  > 那為什麼備料（第 1–2 步）還要把 `events` 放進 `bub.txt`？
  > 因為它有用：可以拿來**核對投顧側是不是漏了某條新聞**（哨兵用途）。
  > 它是背景資訊，不是證據。
- **背離那一節必須給出裁判方法。** 只說「兩邊不一致」沒有價值；
  要寫「用什麼數字、跨過什麼門檻，就知道哪一邊對」。
- **「本期判斷」必須表態。** 不要寫「值得持續觀察」這種話——那是把判斷推給讀者。
- **不要為了湊滿章節而硬掰。** 某週真的沒有背離，就寫「本週四庫高度一致，這本身是訊號」。
- **不要重述新聞。** 每一條都要包含「因為幾個庫都／只有一庫講，所以⋯⋯」這層推論。
- **單邊訊號只標記不判斷。** 這是紀律，避免把未驗證的東西講成結論。
- **數字打架就寫出來。** 各庫對同一數字有出入時，把出入本身當成發現，不要挑一個用。
- **記錄資料缺口。** 缺天、各庫 `index.json` 的 `updatedLabel` 過期、指標 `asof` 落後、
  卡片數異常、**每日五圖的 `about.qa_flags`**，這五項每期都要查，
  **一律寫進單期 JSON 的 `gaps` 欄位**（不是只在交付訊息裡講；
  `gaps` 是 `verify.py` 的必備欄位，漏了會 FAIL）——
  **這套系統順便是另外四套系統的健康度哨兵**。
- 全程繁體中文（台灣用語）。

---

## 6. 待決事項

**完整變更紀錄（v0.1 起）已移至 `MAINTENANCE.md` 第 7 節**——那是維護者要讀的歷史，
每週排程不需要它。排程只要知道：**現行規格就是本檔此刻的內容**。

### 待決事項

1. ~~投顧知識庫只保留 3 天封存檔~~ → **已自行解決**（2026-08-06 覆核）。
   該庫目前保留 6 天（07-30、08-02～08-06），7 天窗口實際拿得到 5–6 天，
   樣本偏薄分支不再是每期必踩。門檻仍維持 `≤ 3`／`≤ 2`（v0.5 由 `< 3` 改來，
   因為剛好 3 天時舊寫法永遠不會觸發）。
   **待觀察**：保留天數是否穩定在 6 天，還是會再縮回去。
2. ~~是否加入第四個來源~~ → v0.5 已加入「每日五圖」，但它不是獨立來源（見第 0 節）。
   **真正獨立的第四個比對面仍然缺席**：券商報告 PDF 是候選，需要穩定的輸入管道。
3. `feedback` 章節目前是人看了再處理。若累積穩定，可考慮讓它自動開 issue 到對應的 repo。
4. 跨期趨勢九格選得對不對，累積 4 期後檢視（連續組 3 格 ＋ v2 組 6 格）。
5. ~~監控庫 v2 的 `triggers` 尚未接入~~ → v0.6 已接入（見第 3.0 節背離節規則與 3.1 schema）。
   **待觀察**：7 條門檻目前全部 `state=0`，等第一條亮起來時檢視
   「已定義門檻」與「自己定義的門檻」在背離節裡的比例是否合理。
6. **每日五圖 2026-08-05 才上線**，前幾期樣本必然偏薄；
   累積兩週後檢視「圖表側寫」這一節是否真的產出數字落地，而不是變成圖說重述。
