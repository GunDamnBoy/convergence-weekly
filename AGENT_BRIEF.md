# 主題匯流訊號報 · AGENT_BRIEF

> ## v2（2026-08-23）：**五庫、六節、走 kb-core 的發布軌、週一下午執行**
>
> 這一版改了六件事，每一件在下面對應的節裡都有完整說明；這裡只列清單，
> **不重複內容**（一個規格只能有一個家）：
>
> | 變更 | 節 |
> |---|---|
> | 第五庫：外資報告週摘，**獨立的第四票**，共振門檻仍是三方 | §0、§1、§5 |
> | 新增第三節「賣方對帳」：裁決到期的分析師主張 | §3、§4 |
> | 發布改走 kb-core 的 `tools/publish.py`（閘門→守衛→推送），dashpush 退場 | §3、§4 |
> | 索引鍵 `issues` → `days` | §3 |
> | 執行時點週日 21:30 → **週一 15:00** | §2 |
> | 檢查搬進 `kb-core/checks/convergence.py`，`verify.py` 退場 | §4 |
>
> **這份是規格，含完整的執行管線定義（第 4 節）。**
> 排程任務的 prompt 是這份管線的**執行骨架**——只放順序與分支判斷，
> 細節（門檻、字數、格式、禁令）一律回這份查。見 `MAINTENANCE.md` 第 3 節。
> 兩份是一組，改了規格就要同步改排程 prompt——這是既有兩套系統歷史上最常犯的錯。
>
> **v2.1（2026-09-29）**：投顧來源改為 `advisory-rewrite`（舊 repo 8/18 起停更，第 008、009 期因此誤報「窗口內無檔」）；帳本折入與指紋基準回到發布軌（kb-core `side_files`）；骨架改吐六節；本檔的發布、檢查、章節數描述全面對齊 v2。詳見 `CHANGELOG.md`。

---

## 0. 這套系統要解決什麼問題

五個知識庫目前各自獨立運作，沒有任何機制在做**跨庫比對**：

| 庫 | 性質 | 單獨看能回答 | 獨立性 |
|---|---|---|---|
| 投顧知識庫 | 敘事．每日．新聞 | 發生了什麼 | 獨立 |
| 節目知識庫 | 敘事．每日．專業討論 | 聰明人在想什麼 | 獨立 |
| AI 泡沫監控 | **量化**．每交易日．自動抓取 | 客觀狀態是什麼 | 獨立（不看新聞） |
| 每日五圖 | **量化重製**．每日．自行製圖 | 敘事講的事，數字是多少 | **選題與投顧同源** |
| 外資報告週摘 | **賣方研究**．每週＋手動．券商 PDF | 分析師對客戶說了什麼 | 獨立（上游是券商 PDF） |

> ⚠️ **每日五圖不是第四個獨立來源。**
> 它的 `about.upstream[0]` 就是 `advisory-knowledge-hub`（系統 id；repo 是 `advisory-rewrite`）的當日檔——選題是從投顧庫挑出來的。
> 所以「投顧在講 ＋ 圖表也在畫」**不構成兩票**，那是同一則新聞被數兩次，
> 跟「量化佐證取自 `events`」是同一個坑，只是換了層皮。
>
> 它真正的價值在另一半：**圖表的數字是自行從 Yahoo／FRED 重製的**，
> 所以它是**量化側的第二個裁判**——把敘事講的模糊說法逼成一個可回查的數字
> （「油價崩了」→ 自 3/31 高點 −32.9%）。角色定位與計票規則見第 5 節。

> **外資報告週摘是獨立的第四票，但門檻沒有提到四方。**
> 它的上游是券商 PDF，與 Google News、與投顧的來源都不同源，所以計票上獨立。
> 但分析師寫的跟新聞報的常常是同一批事件，四方到齊會罕見到不能用；
> 而三方的價值本來就在「量化與敘事各自到達同一結論」。
> **多一個獨立來源是讓三方更容易被驗證，不是讓門檻更高。**
>
> 它還帶來一件別的庫沒有的東西：`stances.json` 是一份**帶到期日的可證偽帳本**，
> 而在匯流接手之前沒有任何流程在判它們。裁決歸這裡 ——
> **匯流是唯一同時看得到「主張」與「證據」的地方**。見第 3 節「賣方對帳」。
>
> ⚠️ **不要重讀那 23 份報告。** 它的 `crosscut` 已經在做跨券商的共振與分歧分析，
> 匯流讀那份綜合、把它當一票。重做等於兩個系統對同一批 PDF 做同一件事，
> 而下游那次還看得比較少。

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
> 章節結構固定為 `sections` 六節＋外殼三塊（見第 3.0 節），其中「共識裂縫」沒有專屬章節——
> 它是可以掛在任何一節某條 item 上的 `tags` 標籤。
> 理由：裂縫不是每週都有，硬留一個常常空著的章節會逼出湊數的內容。
> 反過來，章節裡有兩節不是訊號類型而是**閱讀切面**：
> 「台股」（使用者的實際部位在台股，不管訊號屬哪一類都額外集中講一次）
> 與「圖表側寫」（每日五圖把敘事逼成數字，值得單獨看一輪）。

---

## 1. 資料來源

**五庫**皆為公開 GitHub repo，**用 `git clone --depth 1` 取得，不要用 WebFetch 逐檔抓**
（單日檔 100–300KB，WebFetch 會用小模型摘要，資料會失真）。

```
https://github.com/GunDamnBoy/advisory-rewrite           → data/YYYY-MM-DD.json、data/index.json
                       （系統 id 仍叫 advisory-knowledge-hub；同名 repo 8/18 起停更，**不要 clone 它**）
https://github.com/GunDamnBoy/podcast-knowledge-digest   → data/YYYY-MM-DD.json、data/index.json
https://github.com/GunDamnBoy/ai-bubble-monitor          → data.json（單檔，含 history 日序列）
https://github.com/GunDamnBoy/chart-of-the-day           → data/YYYY-MM-DD.json、data/index.json
https://github.com/GunDamnBoy/broker-research-digest     → data/YYYY-MM-DD.json、data/stances.json
```

> **外資報告要吃 `crosscut` 與 `stances`，不要吃 `summary`。**
> 2026-08-23 量測（當期 23 份）：`summary` 合計 106,449 字元，
> `stances` 81 筆的原句＋中譯只有 16,352（**15%**），而後者是逐字、帶頁碼、
> 唯一可證偽的那一層。`prepare.py` 的 `build_res` 照這個規格做。

> **架構優勢：取資料這一段全部公開，不需要本機、不需要自建轉錄管線。**
> 這與既有兩套系統不同（那兩套要讀本機逐字稿／要跑抓取），維護負擔低很多。
> **但發布這一段仍然依賴本機**：草稿寫進 `~/outbox/convergence/`，
> 由 launchd agent `com.kenny.kbpublish.convergence`（每 60 秒）跑
> `kb-core/tools/publish.py`：閘門 → 不可改寫守衛 → 衍生檔（帳本、指紋）→ 原子寫入 → 索引對帳 → rebase → push → 回執。
> **dashpush 已退場**，「檔案一進 `data/` 就等於發布」那條約束連同它一起消失 ——
> 新軌是**閘門過了才寫、寫了才推**。**連不到本機時沒有退路**：停下來、在交付訊息大聲回報，不要把草稿塞到別的地方。

### 1.1 各庫的資料結構（外資報告週摘的形狀見 `prepare.py` 的 `build_res`）

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
> kb-core 閘門（`quant_reconcile`）已實作這條，跨架構會直接擋下。
>
> `indicators` 在 v2 為 22 項、id 有增有減（`cape`／`mag7`／`gsy_runup` 等為新增），
> 但不是整組換掉——`hyoas`／`circular` 等舊 id 仍在。合法欄位名以當期監控庫實際的 id 為準。

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

- 每週一台北 **15:00** 執行（Cowork 桌面的夾資料夾排程，**本地時間**；
  見 `MAINTENANCE.md` 第 3 節）。
  > **改到週一，理由是量出來的**：兩個最有價值的新輸入都在舊時點（週日 21:30）
  > 之後才到 —— 外資報告週摘**週日 23:00** 發布、泡沫監控的每週質化覆核是
  > **週一 09:03**。照舊時點跑，本期永遠讀到上一週的券商研究、
  > 以及還沒覆核的量化底盤。代價是「上週回顧」晚一個工作日交付。
  >
  > **時點被兩端夾住，15:00 是中間**：
  >
  > | 邊界 | 是什麼 | 為什麼 |
  > |---|---|---|
  > | 下界 ~13:30 | 五圖 11:30 起跑，慢的週次約兩小時落地 | 早於它就讀不到週一的圖，且兩個代理會互相排隊 |
  > | 上界 20:00 | Cowork 用量尖峰起點（5:00–11:00 AM PT ＝台北 20:00–隔天 02:00） | 這一支是四套裡最重的，踩進去消耗特別快 |
  >
  > 原訂的 21:00 在尖峰內。15:00 離上界五小時 —— **這一套還沒有實測軌跡，
  > 那五小時就是給未知留的**。有了實測長度再決定要不要往後挪。
- **敘事側**（投顧、節目、每日五圖）取過去 7 個日曆天；
  **量化側**取 `history` 全部（長度以當期實際為準），
  「本期變動」＝**頂層 `dims` 現值 − `history` 中與現值同一組鍵的最早一筆**。
  > 兩個容易寫錯的地方：
  > ① 是「對**現值**」，不是「對 `history` 最後一筆」——監控庫盤後更新時 `history`
  >   會落後頂層一格，兩者不相等。
  > ② 基準**必須與現值同架構**。`history` 跨越了 2026-08-04 的 v1→v2 改版，
  >   08-03 以前是 `D1`–`D6`、之後是 `L1`–`L3`，取到舊筆就是拿三層去減六維。
  > 兩條 kb-core 閘門都會擋。
- 五庫日期不會對齊——投顧與圖表庫每天更新、節目只有工作日、監控只有交易日。
  **這是正常的，不要試圖對齊。** 如實記錄實際涵蓋範圍，寫進 `range`。
  > `range` 記錄的是**實際拿到的涵蓋範圍**，不是上面那個 7 天窗口。
  > 兩者不相等是正常的（第 001 期窗口 7 天、實際敘事側只涵蓋 6 天），不要為了對齊窗口而虛報。
- 缺天不是失敗。但若投顧側 **≤ 3 天**或節目側 ≤ 2 天，必須在 `about.run` 註明樣本偏薄，
  且**共振判定要保守**（樣本薄時容易把巧合當共振）。
  每日五圖少於 3 天時，「圖表側寫」那一節就寫「本期樣本不足，只列可用的幾張」，不要硬湊五張。

### 2.1 零新增資料時不產期

若重新取回的五庫資料與上一期**完全相同**（例如同一天內重跑、或所有來源都還沒更新），
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
convergence-weekly/                ← 資料 repo（發布目的地，`.kb-data-repo` = convergence-weekly）
├─ index.html            ← 外殼。極少需要動
├─ data/                 ← **只有 kb-core 的 publish 會寫這裡**
│   ├─ index.json        ← 期別清單 ＋ 每期量化快照（跨期趨勢圖靠它）＋ 各期 errata
│   ├─ calls.json        ← 訊號帳本：publish 每期折入 calls.open／close（`side_files`）
│   ├─ upstream.json     ← 監控庫指紋基準：publish 發布最新一期時更新（`side_files`）
│   └─ YYYY-MM-DD.json   ← 每期一檔，永不刪除、永不改寫
├─ prepare.py            ← **備料**（每週第 1 步）：clone 五庫、產出五份摘要層與 PREP.md，
│                          加 --emit-skeleton 另寫 work/skeleton.json（v2 六節骨架，quant 已填）。
│                          排程只跑它，不要自己寫摘要程式，也不要讀它的原始碼
├─ cwlib.py              ← prepare.py 的共用函式（baseline／指紋 diff）。**指紋函式
│                          與 kb-core `systems/convergence.py` 的 `upstream_fingerprint` 成對**
├─ work/                 ← 語料與草稿暫存（gitignore）。閘門從這裡讀語料回查佐證
├─ AGENT_BRIEF.md        ← 本檔（規格）
├─ MAINTENANCE.md        ← 維護說明、事故與待辦
├─ CHANGELOG.md          ← 逐版變更紀錄（維護者才讀）
├─ README.md
└─ ~~publish.py／verify.py／make_index.py／build_issue.py／healthcheck.py~~
                           ← **v2 全部退場**，仍在 repo 裡但**不要再跑**（讀的是舊的
                             `issues` 索引鍵）。發布、閘門、哨兵都在 kb-core：

kb-core/                           ← 共用底盤（launchd 直接跑這裡的檔）
├─ tools/publish.py      ← 唯一發布路徑：閘門 → 不可改寫守衛 → 衍生檔 → 原子寫入 → rebase → push → 回執
├─ systems/convergence.py← payload 組法、index 快照、errata-only 守衛、**帳本折入與指紋基準**
├─ checks/convergence.py ← 閘門的全部檢查（唯一正本）
├─ tools/convergence_verify.py       ← 本機預驗，只讀不寫
├─ tools/convergence_rulings_apply.py← 賣方裁決寫回 stances.json
└─ skills/convergence/SKILL.md       ← 排程 prompt 的正本
```

### 3.0 章節結構（`sections` 六節＋外殼三塊）

「零」由外殼寫死；中間各節由 `sections` 驅動，**編號寫在各節自己的 `title` 字串裡**；
尾巴兩節的編號由外殼**依 `sections` 長度動態計算**。
`sections` 的 id 與順序必須是下表一到六那六個，閘門（`SECTION_SETS`）會擋。

| # | id | 節名 | 規則 |
|---|---|---|---|
| 零 | —（外殼寫死） | 量化底盤 | 不是新聞，是這段期間的客觀狀態。由 `quant` 驅動 |
| 一 | `resonance` | 三方共振 | 三個**獨立**來源同時指向（v2 起共有**四個**聲音可選）。量化佐證不得取自 `events`；**投顧與圖表計為同一票** |
| 二 | `divergence` | 關鍵背離 | **必須給裁判方法**：用什麼數字、跨過什麼門檻就知道哪一邊對。**優先引用 `triggers` 裡已定義的門檻**，見下方 |
| 三 | `verdicts` | **賣方對帳**（v2 新增） | 當週到期的分析師主張逐筆裁決。機器讀的那一份在**頂層 `rulings[]`**，這一節是它的人讀版本 |
| 四 | `taiwan` | 台股 | 閱讀切面。各庫講台股時常在不同層次，把層次差寫出來 |
| 五 | `charts` | **圖表側寫** | 閱讀切面。**敘事講的事，圖表算出來是多少**——見下方規則 |
| 六 | `single` | 單邊訊號 | **只標記不判斷**。用 `list[]` 而非 `evidence[]`，但一樣要逐字 |
| 七 | —（外殼寫死） | 下週該盯什麼 | 由 `watch[]` 驅動。每條可觀察、可證偽 |
| 八 | —（外殼寫死） | 資料缺口回報 | 由 `feedback[]` 驅動，**v2 收窄成只寫資料層的缺陷**（見下方） |

`sections` 的 id 與順序鎖死為
`resonance → divergence → verdicts → taiwan → charts → single`（**6 節**），
由頂層 `schemaVer: "2"` 宣告。舊期沒有這個欄位，走 5 節或 4 節的舊組合。
**判準是資料自己的宣告，不是日期** —— 日期門檻是一個「記得改」的東西，
而忘記改的那次不會有徵兆。

**第三節「賣方對帳」的規則：**

- 資料在頂層 `rulings[]`：`{id, result, why}`。`id` 是 `stances.json` 的條目 id。
- `result` 用外資報告 `research/anchors.json` 的 `status_vocab`：
  **應驗／部分應驗／落空／無法驗證**，加上匯流自己的 **延後**。
  > **詞彙不是自己訂的。** `status_vocab` 跟 podcast 的 `observations.json` 逐字相同，
  > anchors 寫著理由：「同一個判斷的詞彙只有一套，不然兩個庫的『部分應驗』
  > 會慢慢變成兩件事」。
- **每一筆都要寫 `why`。** 裁決沒有理由就不是裁決。
- 「延後」不寫回帳本，那幾筆維持 `觀察中`、下一期照樣被撈出來。
  **「還判不了」不該長得像「判完了」。**
- **到期而完全沒被碰的，是安靜地掉的** —— 判不了就寫「延後」加理由，不要略過。

**第八節「資料缺口回報」v2 收窄：**
只寫「某庫的資料有問題」（欄位缺、時間戳停住、數字對不上）。
判斷類的回饋 v2 有了機械管道（裁決寫回 `stances.json`），不再寫這裡。
理由：v1 三期共 11 條建議，**沒有任何機制知道它們有沒有被採納**。

**第二節「關鍵背離」的裁判方法要優先引用 `triggers`：**

監控庫 v2 提供 7 條**已經定義好門檻的觸發器**（`hy80` HY 利差 3 個月走闊 ≥80bp、
`ccc12` CCC 利差 ≥12%、`gsy150` SOXX 24 個月漲幅 ≥150%、`cpi4` CPI 年增 ≥4%、
`policy_gap` 政策利率 ≥ 名目 GDP 成長、`y10_5` 美債 10 年 ≥5%、`megaipo` 巨型 IPO 完成），
每條都附 `state`（0／1）與當前 `value`。

- 背離的裁判方法**先看有沒有現成的 trigger 對得上**，有就直接引用它的門檻與 `state`。
  自己另外定義門檻是次選——現成的那組是客觀、跨期一致、且會自動更新的。
- `watch[]` 也一樣：**能對應到 trigger 的條目必須用 `<code>trigger_id</code>` 標出正確的 id**，
  下一期驗收時就是查 `state` 有沒有翻轉，不必再靠人工判斷。
  **閘門會擋**（`watch_bound`）：提到某個 trigger 卻沒標、或標成 indicator id（`ccc` 不是 `ccc12`、
  `stage` 不是 `hy80`）都是 FAIL。第 002 期 7 條 `watch` 裡有 4 條踩到這個。
  第 001 期的 watch 有一條「10 年期美債升破 5%」當時在監控庫沒有對應欄位、無法程式化驗收，
  v2 的 `y10_5` 正好補上——這條回饋迴圈是閉合的。
- 7 條全部帶進 `quant.triggers`，**不要挑**。沒亮的那幾條本身就是資訊
  （「這些事都還沒發生」是一個判斷，不是空白）。

**第五節「圖表側寫」的規則：**

- 這一節的職責是**數字落地**：把其他各庫用形容詞講的事，換成圖表庫算出來的具體數字。
  「敘事說油價崩了 → 圖表算出自 3/31 高點 −32.9%」這種句型才是這一節要的。
- **證據只能取自圖表庫自行重製的數字**（`series` 算出來的變動、`takeaway` 裡的數值）。
  它的選題來自投顧庫，所以**選題本身不是證據**——不要寫「圖表庫也關注這件事」。
- 五張圖不必每張都寫。挑**能和其他庫對話的**，其餘略過。
- 圖表庫的判讀（`so_what`）與其他庫矛盾時，**把矛盾寫出來**，不要挑一邊。
- `about.qa_flags` 轉寫進本報的 `gaps`。

「共識裂縫」不是章節，是掛在 item 上的 `tags` 標籤（見第 0 節）。
要增減章節數或動 schema，**這一組要一起改**（本清單是唯一正本）：
本節與 3.1、`index.html`（含 `S()` 白名單——新增可含 HTML 的欄位時要確認跳脫路徑）、
**`prepare.py`**（`build_skeleton()` 硬依賴整份單期 schema；`PREP.md` 的量化底盤與觸發器兩區也是）、
**kb-core `checks/convergence.py`**（`SECTION_SETS`、`VOICE`、必備欄位與各檢查）、
**kb-core `systems/convergence.py`**（`index_entry` 硬依賴 `quant` 欄位；`fold_calls` 硬依賴 `calls` schema；
`upstream_fingerprint` 與 `cwlib.py` 的同名函式**必須逐欄相同**，否則 PREP 每期亮 🛑）、
以及排程 prompt（kb-core `skills/convergence/SKILL.md`）裡描述骨架與章節的段落。
退場的 `verify.py`／`publish.py`／`make_index.py`／`healthcheck.py`／`build_issue.py` 不在組內。

> 第 001 期是 4 節（無 `charts`）、第 002～003 期是 5 節（無 `verdicts`），閘門以 `SECTION_SETS` 的舊組合放行。
> 舊期不回頭補寫——歷史全部保留的另一面是歷史不美化。

### 3.1 單期 JSON schema

```jsonc
{
  "schemaVer":"2",                             // v2 必填：六節組合的宣告
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
  "about":{"run":"...","method":"..."},
  "rulings":[{"id":"<stances.json 條目 id>","result":"應驗|部分應驗|落空|無法驗證|延後","why":"..."}],
  "calls":{"open":[...],"close":[...]}   // 見 3.2 末
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
  "evidence":[{"d":"8/1","s":"監控","t":"..."}], // s 是封閉集合，只有這五個值：
                                                 // 監控／投顧／節目／圖表／券商。打錯字閘門會 FAIL
  "call":{"h":"對投顧的含義","body":"..."}
}
```

**三個外殼沒明講、但閘門硬依賴的慣例：**

1. **量化佐證必須用 `<code>欄位名</code>` 包住欄位名。**
   ```
   ✅ "t":"指標 <code>hyoas</code> = 2.84%、zone green、score 25.8、三個月 −14bp"
   ❌ "t":"高收益債利差偏低"
   ```
   閘門用 `<code>([a-z0-9_]+)</code>`（**只吃小寫**，寫 `l1` 不寫 `L1`）抓出 id 去 `bub` 裡查存在性。沒包 `<code>` 的那條
   不會 FAIL，但檢查形同空轉，會出 warn。合法欄位名＝指標 id（v2 為 22 項，動態讀取）＋ 台股項目 id
   ＋ `stage` / `composite` / `twheat` / `quadrant` / `heat` / `support`
   ＋ 維度 id（兩代並存：v1 的 `d1`–`d6`、v2 的 `l1`–`l3`）。

2. **body 類欄位允許行內 HTML。** `verdict[]`、`cols[].body`、`call.body`、`list[].body`、
   `callout.body`、`watch[]`、`feedback[]`、`gaps[]`、`evidence[].t` 都可用
   `<b>` / `<code>` / `<br>`。逐字回查時閘門會先剝標籤，所以加粗不影響驗證。

3. **`list[]` 一樣要逐字回查。** 單邊訊號整節用 `list` 而非 `evidence`，
   但「佐證一律逐字」是無條件的；`src` 裡含「監控」的視為量化側。

4. **`list[].body` 與 `evidence[].t` 被「全片段」逐字回查**，所以它們必須是**純原句**；
   自己的分析放 `body[]`／`cols[]`／`call.body`（那幾欄不回查）。

### 3.2 index.json

```jsonc
{
  "updated":"ISO8601 +08:00", "updatedLabel":"8/24 21:12", "count":N,
  "days":[{                       // **v2 起是 `days` 不是 `issues`** ——                     // 依日期由新到舊
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

**`calls`（選填，v1.0 起）——訊號帳本的來源**：

```jsonc
"calls": {
  "open": [                                   // 本期新開的可證偽判斷
    {"id":"c003-1",                           // 全域唯一，建議 c<期號>-<序號>
     "kind":"divergence|watch|verdict",
     "claim":"CCC 利差將在兩期內升破 12%",      // 判斷本身，一句話
     "judge":"<code>ccc12</code> state 翻轉",  // 裁判方法：能對應 trigger 就寫 trigger
     "deadline":"2026-08-30"}                  // 選填
  ],
  "close": [                                  // 對過往帳目的結案裁決
    {"id":"c002-1","result":"hit|miss|expired|void","note":"一句話裁決理由"}
  ]
}
```

kb-core 的 publish 在閘門之後、寫入之前把它機械折入 `data/calls.json`
（`systems/convergence.py` 的 `side_files` → `fold_calls`），折入時驗證：
open 的 id 全域唯一、open 必附 claim＋judge、close 引用的帳目存在、result 在合法值域、
**已結案的帳目不得改判**（同一個 result 再結一次是 no-op，保留原結案——那是重述不是改判）。
任何一條不過回 **exit 10**，`data/` 一個位元組都不動。
> 2026-08-23 搬進 kb-core 時這段折帳沒有跟過來，帳本停住五週（第 004～009 期），
> 同一筆 c003-5 因此被四期分別判成 miss／hit／hit／miss。2026-09-29 補回並依各期回補，
> 帳本以第一次裁決為準。
`result` 的 `void`（作廢）**僅供人工維護**（例如上游移除了裁判用的 trigger）——
排程合成時只用 `hit`／`miss`／`expired`；void 帳目不計戰績也不列未結案。
站台的「判斷紀錄」區塊直接讀帳本顯示戰績。
**登帳準則**：只登可證偽的（有裁判方法＋可觀察）；背離節的甲/乙裁決、有門檻的 watch
是天然的帳目；「值得觀察」這種不可證偽的敘述不准登帳。
`PREP.md` 每期會把未結案帳目攤開逼驗收——能裁決的必須在 `calls.close` 結案。

**`errata`（選填）**：既有單期檔永不改寫，所以**發布後才發現的問題掛在這裡**，
由外殼渲染成期別按鈕下方的黃色橫幅。原文一個字都不動，錯誤在旁邊講清楚。
這是「歷史全部保留」與「不在頁面上說謊」兩條原則唯一能同時滿足的做法。

---

## 4. 執行管線

### 第 1–2 步：備料（跑 `prepare.py`，不要自己寫）

確切指令（暫存目錄、`--work` 為何要指容器本地、語料要複製到哪）在排程 prompt 第 1、1b 步，
這裡只寫它做什麼。它做完取資料與壓縮兩步：clone **五庫**、依下列規格產出
`work/adv.txt`／`pod.txt`／`bub.txt`／`cotd.txt`／`res.txt`（另複製 `stances.json`），並印出 `PREP.md`，段落依序——
**🛑 上游改版偵測**（監控庫指紋 vs `data/upstream.json` 的明文 diff，變更時才出現；
**列出的差異必須全部寫進本期 `gaps`**，涉及維度或權重時跨期比較依 §0 斷點規則處理）、
涵蓋統計與摘要層大小、各庫最新日期（監控庫以 `meta.built` 為準）、
**上一期資訊（期號／headline／errata 數）與 watch 清單全文**（合成時驗收用）、
**量化底盤全文**、**triggers 狀態表**、**訊號帳本**（戰績＋未結案帳目逼驗收——
能裁決的必須在本期 `calls.close` 結案）、**賣方對帳**（當週到期的分析師主張）、
樣本偏薄旗標、零新增資料提示。
**exit 3 ＝ 五庫都沒有比上一期新的資料**，依 §2.1 不產期，直接進交付說明原因。

主線接著只需要讀 `PREP.md` 與摘要層，**不要碰任何原始 JSON**，
也**不要讀 `prepare.py` 或 kb-core 的原始碼**——用法本節與排程 prompt 已經寫完，讀原始碼零收益。
`bub.txt` 只在要查某個特定指標的 `score`／`zone`／`asof` 時才需要讀。

`--emit-skeleton` 另外寫出 `work/skeleton.json`：**v2 單期骨架**（`schemaVer:"2"`、六節、
五列 `coverage`、空的 `rulings[]` 都已就位），`quant` 的**數值欄位**也已從監控庫抄好。
但 `quant` 裡有四處仍要你填——`dims[].note`、`stage.delta`、`callout`、`quant.note`——
**那四欄是判斷不是抄寫**。

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

兩者都要求：**佐證逐字取自檔案，寧可少寫也不要編**；
**一次把整份檔案讀完，不要分段讀**——分段會產生多次快取寫入（×2 權重），是實測可見的成本。

### 第 4 步：主線合成（**不可外包**）
合成需要同時握有各邊，這是整套系統唯一無法拆分的環節。
**量化側由主線自己讀**——**先看 `PREP.md` 的「量化底盤」區塊**（composite／象限／階段／
台股熱度／三層變動／觸發器表都在那裡）與 `cotd.txt`；需要查某個特定指標的
`score`／`zone`／`asof` 時才另外讀 `bub.txt`。它們是裁判，不該經過另一個模型的轉述。子代理只負責兩個敘事庫。

> 為什麼圖表庫歸量化側、不派第三個子代理：
> 它的選題來自投顧庫，派子代理獨立萃取「主題」只會複述投顧側已經有的東西，
> 平白多一份會製造假共振的材料。它有價值的是**數字**，而數字要精確、要可回查，
> 正是不該被另一個模型壓縮的那種東西。

**比對的順序有講究**：先把量化側攤開（`PREP.md` 的量化底盤 ＋ `cotd.txt` 的重製數字），再拿兩份敘事主題去對。
反過來做（先讀敘事再看指標）會讓你只找得到「指標支持敘事」的部分，找不到背離。

**驗收上一期的 `watch` 清單**：上期點名要盯的事，這期發生了嗎？跨過門檻了嗎？
有結果的要寫進本期 `verdict`。這條回圈是本系統會不會累積判斷力的分水嶺——
少了它，每期都是重新開始，`watch` 就只是好看的收尾。

### 第 5 步：寫草稿、本機預驗

1. **以 `work/skeleton.json` 為底**寫草稿。骨架的 `quant` 數值欄位**直接沿用、不要重打**
   （第 002 期就是手打時把 `watch` 的 trigger id 標成 indicator id）。
   要填的是全部標「（填：…）」的欄位、`sections[].items`、`watch`、`gaps`、`rulings[]`，
   以及 **`calls`**（登帳準則見 §3.2 末——只登可證偽的，能結案的要結案）。
2. **不要直接寫 `data/`**——那是閘門的另一邊。
3. 先跑 kb-core 的 `tools/convergence_verify.py <草稿> --repo … --work …`：
   與發布閘門同一組檢查、只讀不寫、十秒內回答。**0 FAIL** 才往下；
   SKIPPED 只允許 `index_snapshot` 一條（發布前索引裡本來就還沒有本期），
   其他任何 SKIPPED 代表語料沒到位——**SKIPPED 不是 PASS**。
4. 不要動 `index.html`，除非 schema 真的變了（變了就是一組一起改，清單見第 3.0 節末）。

閘門住在 kb-core 的 `checks/convergence.py`（那裡是唯一正本），檢查九大類：
**A 結構**（必備欄位、章節 id 與順序、**每節至少一個 item**、值域 0–100）
**B index 快照值層級對帳**（composite／dims／twHeat／stage／quadrant／trigLit 逐欄等值）
**C 敘事佐證**（**逐來源**逐字回查、**全片段**、含 `list[]`、日期格式 `M/D`、
**同段佐證不得跨 item 重複**、共振來源獨立性——投顧＋圖表計一票）
**D 量化佐證**（`<code>欄位名</code>` 存在、**數字逐個對回監控庫**、不得取自 `events`）
**E 量化對帳**（現值與變動 vs `history` 不跨改版、quant 抄寫欄位 vs 監控庫逐欄 diff、觸發器對帳）
**F watch 的 trigger 綁定**（提到 id 必須 `<code>` 正確標；綁 indicator 而**確實沒有
對應 trigger** 的出 WARN 不出 FAIL —— 那是規格允許的次選）
**G 賣方裁決的完整性**（當週到期的每一筆都要處理、result 在 `status_vocab` 值域、
每一筆都要有理由、不重複結案）
**H `gaps` 非空**（空著跟「五庫都很健康」長得一模一樣，而五庫的日期本來就不會對齊）
**I 佐證來源封閉集合**（監控／投顧／節目／圖表／**券商**五個值）

### 第 6 步：發布與交付

1. 草稿寫進 **`~/outbox/convergence/<日期>.draft.json`**（寫完用 `wc -c` 確認落地），
   由 launchd `com.kenny.kbpublish.convergence`（每 60 秒）跑 kb-core `tools/publish.py`：
   閘門 → 不可改寫守衛 → **帳本折入與指紋基準** → 原子寫入 → 索引 → rebase → push → 回執。
   回執 `~/outbox/convergence/<日期>.receipt.json` 的 `exit`：
   0 已發布｜10 內容沒過閘門或帳本折不進去（看 `detail`，改草稿重交）｜
   11 該期已存在且內容不同（**不改草稿**，掛 errata）｜12 輸入或目的地壞掉（停下回報）｜
   13 空輪次（草稿沒被看到，查檔名與目錄層級）｜14 網路或 git（會自己重試，不要重寫草稿）｜
   15 rebase 衝突或 repo 有別人沒提交的變更（停下回報，重跑不會好）。
   **「沒有回執」與「回執說失敗」是兩件事**——前者代表 publish 根本沒跑。
   > **`work/` 底下的語料與 `bub/data.json` 一定要在**，缺了 `build()` 會 raise、
   > 回執是 BAD_INPUT：空語料會讓每一條逐字比對的檢查 vacuously 通過。
2. **裁決寫回**（exit 0 之後）：跑 kb-core `tools/convergence_rulings_apply.py <本期 JSON>
   --stances …`，**先不加 `--apply` 看要改哪幾筆**，確認後再加。把 `rulings[]` 的終局裁決
   寫進 `broker-research-digest/data/stances.json` 的 `status`／`verdict`／`verdictDate`。
   **「延後」不寫回** —— 那幾筆維持觀察中，下一期照樣會被撈出來。
   `rulings[]` 為空時它是 no-op，照樣跑一次留紀錄。
3. 驗證線上狀態時**網址一定要帶 cache-buster**，
   並確認頁面上的**期別按鈕數量**與**跨期趨勢的點數**，而不只是看 `days[0].date`。
4. 交付訊息**五行**：本期最重要的判斷、**上一期 `watch` 的驗收結果**、
   本期裁決了幾筆賣方主張（各結果幾筆）、**帳本戰績**（讀發布後的 `data/calls.json`：
   N 勝 M 敗 K 未決）、發現的資料缺口；末行寫發布狀態（exit 0 附 commit）。

### 發布後才發現問題：errata

既有單期檔永不改寫。**最新一期**的 errata 走同一條發布軌：在草稿加 `errata`、其餘一字不動，
重交 outbox（`errata_only` 守衛只准加勘誤，勘誤只准加不准撤）。
**較舊的一期**不能走發布軌——閘門會拿今天的語料與監控庫重驗舊期，`quant_reconcile` 與
逐字回查必然 FAIL——所以直接在 `data/index.json` 該期 entry 加 `errata`（第 001、002 期的前例），
下一次發布會把它一起 commit。外殼從 index 渲染勘誤橫幅。

---

## 5. 品質規則（違反其中任一條就是這期做壞了）

- **佐證一律逐字。** 引卡片標題、集數標題、交叉觀察原文、指標欄位，不改寫、不潤飾。
  引自 `crossCut` 的內容要標明「當日交叉觀察，引 ○○節目」，**不可偽裝成集數標題**。
- **量化佐證要附欄位名，而且要用 `<code>` 包住。**
  寫 `指標 <code>hyoas</code> = 2.84%、zone green、score 25.8`，
  不要寫「高收益債利差偏低」——前者可回查，後者不行。
- **計票時投顧與圖表算同一票；券商是獨立的第四票。**
  v2 起有**四個獨立聲音**：敘事新聞側（投顧＋圖表，合計一票）、節目側、量化側、**賣方側**。
  每日五圖的選題取自投顧庫，所以「投顧在講＋圖表也在畫」是一票不是兩票；
  外資報告的上游是券商 PDF，與新聞不同源，所以它獨立。
  **但「三方共振」的門檻沒有跟著提到四方** —— 理由見第 0 節。
  `checks/convergence.py` 的 `resonance_independent` 會對標了「共振」的 item
  實際計算獨立聲音數，不足三個直接 FAIL。`VOICE` 表把投顧與圖表映到同一個 key，
  **寫在程式裡而不只是文件裡** —— 前兩次證明了只寫在文件裡的規則會漂移。
- **量化佐證只能取自 `indicators` / `dims` / `stage` / `tw`，絕對不能取自 `events`。**
  `events` 欄位本身就是 Google News。拿它當量化側證據，等於讓**同一則新聞**
  在投顧側算一次、在監控側再算一次，「三方共振」就是假的——
  而共振是這套系統宣稱最強的訊號。閘門（`quant_grounded`）會 FAIL 這種情況。
  > 那為什麼備料（第 1–2 步）還要把 `events` 放進 `bub.txt`？
  > 因為它有用：可以拿來**核對投顧側是不是漏了某條新聞**（哨兵用途）。
  > 它是背景資訊，不是證據。
- **格式硬規則（閘門會 FAIL 的四條，寫錯就得整期重跑）：**
  `evidence[].d` 一律 `M/D`（如 `8/5`，不帶年）；同一段佐證**不得跨 item 重複使用**
  （兩個判斷共用一段引文，至少其中一個站不住）；每節至少一個 item
  （真沒有就寫「本週無」的說明 item，不留空陣列）；量化數值一律 0–100 值域。
- **背離那一節必須給出裁判方法。** 只說「兩邊不一致」沒有價值；
  要寫「用什麼數字、跨過什麼門檻，就知道哪一邊對」。
- **「本期判斷」必須表態。** 不要寫「值得持續觀察」這種話——那是把判斷推給讀者。
- **不要為了湊滿章節而硬掰。** 某週真的沒有背離，就寫「本週五庫高度一致，這本身是訊號」。
- **不要重述新聞。** 每一條都要包含「因為幾個庫都／只有一庫講，所以⋯⋯」這層推論。
- **單邊訊號只標記不判斷。** 這是紀律，避免把未驗證的東西講成結論。
- **數字打架就寫出來。** 各庫對同一數字有出入時，把出入本身當成發現，不要挑一個用。
- **記錄資料缺口。** 缺天、各庫 `index.json` 的 `updatedLabel` 過期、指標 `asof` 落後、
  卡片數異常、**每日五圖的 `about.qa_flags`**，這五項每期都要查，
  **一律寫進單期 JSON 的 `gaps` 欄位**（不是只在交付訊息裡講；
  `gaps` 是閘門的必備欄位，漏了會 FAIL）——
  **這套系統順便是另外五套系統的健康度哨兵**。
- 全程繁體中文（台灣用語）。

---

## 6. 待決事項

**完整變更紀錄（v0.1 起）在 `CHANGELOG.md`**——含逐檔改動、度量趨勢、被否決的選項、
回溯要點與失效模式歸納。那是維護者要讀的歷史，每週排程不需要它。
排程只要知道：**現行規格就是本檔此刻的內容**。


1. ~~投顧知識庫只保留 3 天封存檔~~ → **已自行解決**（2026-08-06 覆核）。
   該庫目前保留 6 天（07-30、08-02～08-06），7 天窗口實際拿得到 5–6 天，
   樣本偏薄分支不再是每期必踩。門檻仍維持 `≤ 3`／`≤ 2`（v0.5 由 `< 3` 改來，
   因為剛好 3 天時舊寫法永遠不會觸發）。
   **待觀察**：保留天數是否穩定在 6 天，還是會再縮回去。
2. ~~是否加入第四個來源~~ → v0.5 已加入「每日五圖」（非獨立來源），**v2（2026-08-23）已加入外資報告週摘作為獨立的第四票**（見第 0 節）。
3. `feedback` 章節目前是人看了再處理。若累積穩定，可考慮讓它自動開 issue 到對應的 repo。
4. 跨期趨勢九格選得對不對，累積 4 期後檢視（連續組 3 格 ＋ v2 組 6 格）。
5. ~~監控庫 v2 的 `triggers` 尚未接入~~ → v0.6 已接入（見第 3.0 節背離節規則與 3.1 schema）。
   **待檢視（條件已滿足）**：`gsy150` 自 2026-08-09（第 002 期）起 `state=1`，
   第 002、003 期 `trigLit` 皆為 1。可以檢視「已定義門檻」與「自己定義的門檻」
   在背離節裡的比例是否合理。
6. **每日五圖 2026-08-05 才上線**（第 003 期起已是滿窗 7 天）；
   累積兩週後檢視「圖表側寫」這一節是否真的產出數字落地，而不是變成圖說重述。
7. ~~上游改版沒有主動偵測機制。~~ **v1.0 已解決**（v2 搬家時基準的寫入掉了、v2.1 補回：
   讀基準在 `cwlib.py`、寫基準在 kb-core `systems/convergence.py`，兩份函式成對）：`cwlib.upstream_fingerprint`
   取七項指紋（dims 鍵／權重／triggers 全文／indicators／tw／checklist／zones），
   publish 成功後存 `data/upstream.json`，下次 `prepare.py` 比對並在 `PREP.md`
   頂部印 🛑 明文 diff。留此紀錄：當年只比 `meta.version` 的構想不夠——
   權重改了 version 常常不動，指紋要取「意義會變」的東西。
