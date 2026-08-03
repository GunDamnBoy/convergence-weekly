# 主題匯流訊號報 · 維護說明

規格在 `AGENT_BRIEF.md`。這一份放**維護流程、排程 prompt、已知的坑與事故紀錄**。

**寫東西前先想清楚放哪一份：** 新的事實細節寫 brief，新的「為什麼」寫這裡第 6 節，
排程 prompt 只在流程或分支改變時才動。

---

## 1. 首次上架

```bash
# 1) 在 GitHub 建一個 public repo，名稱：convergence-weekly
# 2) 本機：
cd ~
# 把交付的資料夾放到這裡，成為 ~/convergence-weekly
cd ~/convergence-weekly
git init
git add -A
git commit -m "主題匯流訊號報 v0.3：站台架構、第 001 期"
git branch -M main
git remote add origin https://github.com/GunDamnBoy/convergence-weekly.git
git push -u origin main

# 3) GitHub → Settings → Pages → Source: Deploy from a branch → main / (root)
# 4) 約一分鐘後：https://gundamnboy.github.io/convergence-weekly/
```

**接上自動推送**：既有的 `com.kenny.dashpush`（每 180 秒）如果是逐一列出資料夾的，
要把 `~/convergence-weekly` 加進它的清單；如果是掃描某個母目錄的，放對位置即可。
加完之後改一個字測試，確認 180 秒內會自己推上去。

---

## 2. 標準修改流程

1. 改 `AGENT_BRIEF.md`（規格）
2. **只在流程或分支判斷改變時**才動排程 prompt，用
   `mcp__scheduled-tasks__update_scheduled_task` 同步（taskId：`convergence-weekly`）。
   ⚠️ `prompt` 是**整份取代，不是局部編輯**——送出前確認所有段落都帶上了，漏掉的段落等於刪除。
3. 在 brief 第 6 節加變更紀錄，**寫清楚為什麼改**，不只是改了什麼
4. 動到單期 JSON schema 時，`index.html` 的 `renderItem` / `renderQuant` 與
   `build_issue.py` 都要跟著改——**這三處是一組**
5. 事故經過與被否決的選項寫本檔第 6 節

**改完務必自問一次：這條規則排程執行時讀得到嗎？**
排程每次觸發都是全新 session，只讀 `AGENT_BRIEF.md` 與 prompt 本身。
只寫在本檔（維護文件）的規則，排程永遠不會知道——v0.4 就是這樣掉了三條關鍵規則。

---

## 3. 排程 prompt（整份取代用）

> 建立方式：`create_trigger`，cron **`30 13 * * 0`**（UTC）＝ 台北每週日 21:30。
> 每次觸發都是全新 session，所以 prompt 必須完整、獨立、不依賴任何對話記憶。

```
你要產出「主題匯流訊號報」的新一期——把三個知識庫做跨庫比對，找出共振、背離、裂縫與早期訊號。
產出不是資訊，是訊號的合成。讀起來像「本週新聞回顧」就是做失敗了。
全程繁體中文（台灣用語）。完整規格見 repo 內的 AGENT_BRIEF.md，開工前先完整讀它。
本 prompt 只是流程骨架；門檻、字數、格式、禁令一律以 AGENT_BRIEF.md 為準。

第 1 步：取資料
  git clone --depth 1 https://github.com/GunDamnBoy/convergence-weekly.git site
  git clone --depth 1 https://github.com/GunDamnBoy/advisory-knowledge-hub adv
  git clone --depth 1 https://github.com/GunDamnBoy/podcast-knowledge-digest pod
  git clone --depth 1 https://github.com/GunDamnBoy/ai-bubble-monitor bub
  讀 site/AGENT_BRIEF.md（全部）與 site/data/index.json
  （看上一期是第幾期、講了什麼，並抄下上一期的 watch 清單，第 4 步要驗收）。
  敘事側取過去 7 個日曆天；量化側取 bub/data.json 的 history 全部，
  「本期變動」以 history 第一筆對現值計算。
  缺天正常，如實記下實際涵蓋範圍寫進 range（range 記錄實際拿到的，不是 7 天窗口本身）。
  ⚠️ 樣本不足的處置：若投顧側 < 3 天或節目側 < 2 天，必須在 about.run 註明樣本偏薄，
     且共振判定要保守（樣本薄時容易把巧合當共振）。
     投顧庫目前只保留 3 天封存檔，所以這個分支幾乎每期都會踩到，不要當成例外。

第 2 步：壓縮成摘要層（寫 Python，不要把原始 JSON 讀進上下文）
  adv → adv.txt：每卡一行「{★if deep}({src}/{tag}) {title} || {bullets[0] 前 110 字}」，
                 依日期與 group 分層，保留每日 headline 與 overview.snap。目標 40–60K 字。
  pod → pod.txt：每集三行（▸{show}｜{title} / 摘要前 420 字 / 每條 takeaway 的 title），
                 完整保留每日 crossCut（pod 側最濃縮的部分，不可省略）。目標 12–20K 字。
  bub → bub.txt：composite ＋ 六維現值與變動 ＋ 21 項指標（含 zone/score/asof）
                 ＋ stage 全文與 checklist ＋ tw ＋ events。這份很小，可直接讀。
  超過目標大小就縮 body 截斷長度，不要減少卡片則數——覆蓋率比細節重要。
  注意 pod 的 takeaways/sections/meta 是字串化的 Python list，要 ast.literal_eval。

第 3 步：兩個子代理平行萃取敘事側（必須平行、必須互相看不到對方的檔案）
  這是正確性問題不是效率問題：同一個上下文讀完兩庫，會在後讀的那庫尋找前一庫講過的東西，
  「共振」就變成自我實現的預言。不要合併、不要讓其中一個知道另一個存在。
  子代理 A 讀 adv.txt → 8–14 個主題（敘事重心、出現強度、有無轉向、3–5 條逐字佐證）
           ＋「只出現一次但值得注意的訊號」5–8 條
  子代理 B 讀 pod.txt → 8–12 個主題（核心主張、講者分歧最重要、出現強度、2–4 條逐字佐證）
           ＋「podcast 已在講但新聞沒跟上的事」5–8 條
  兩者都要求：佐證逐字取自檔案，寧可少寫也不要編。

第 4 步：主線自己合成（不要外包）。順序有講究——
  先自己讀 bub.txt 把六維變動攤開，再拿兩份敘事主題去對。
  反過來做會讓你只找得到「指標支持敘事」的部分，找不到背離——
  而背離是這套系統唯一無可取代的產出。
  章節固定六節（詳見 brief 第 3.0 節）：
    零 量化底盤（外殼渲染 quant）／一 三方共振 resonance／二 關鍵背離 divergence／
    三 台股 taiwan／四 單邊訊號 single／五 下週該盯什麼 watch／六 回饋 feedback
  sections 必須恰為 4 節（一～四），編號寫在各節自己的 title 裡，verify.py 會擋。
  「共識裂縫」沒有專屬章節，它是掛在 item 上的 tags 標籤。
  開頭「本期判斷」3 段，必須表態，不要寫「值得持續觀察」這種話。
  驗收上一期的 watch 清單：上期點名要盯的事，這期發生了嗎？跨過門檻了嗎？
  有結果的寫進本期 verdict。少了這條回圈，每期都是重新開始。

  寫每一條時遵守 brief 第 5 節全部品質規則，其中最容易漏的：
  · 佐證一律逐字，不改寫不潤飾。引自 crossCut 的要標明「當日交叉觀察，引 ○○節目」，
    不可偽裝成集數標題。
  · 量化佐證要附欄位名並用 <code> 包住：寫
    「指標 <code>hyoas</code> = 2.84%、zone green、score 25.8」，
    不要寫「高收益債利差偏低」。verify.py 靠 <code> 抓 id 做存在性檢查。
  · 量化佐證絕對不能取自 events——那是 Google News，用它會讓同一則新聞
    在投顧側算一次、監控側再算一次，共振就是假的。只能取自 indicators/dims/stage/tw。
    verify.py 會 FAIL。（events 只能拿來當哨兵，核對投顧側漏了什麼。）
  · 背離那一節必須寫出裁判方法：用什麼數字、跨過什麼門檻就知道哪一邊對。
  · 單邊訊號只標記不判斷。用 list[] 而非 evidence[]，但一樣要逐字。
  · 不要為了湊滿章節而硬掰。真的沒有背離就寫「本週三庫高度一致，這本身是訊號」。
  · 不要重述新聞。每一條都要有「因為三庫都／只有一庫講，所以⋯⋯」這層推論。
  · 數字打架就寫出來。三庫對同一數字有出入時，把出入本身當成發現，不要挑一個用。
  · 記錄資料缺口：缺天、各庫 index.json 的 updatedLabel 過期、指標 asof 落後、卡片數異常，
    這四項每期都要查，一律寫進單期 JSON 的 gaps 欄位
    （不是只在交付訊息裡講——gaps 是 verify.py 的必備欄位，漏了會 FAIL）。

第 5 步：寫檔（schema 見 brief 第 3 節，可參考 site/build_issue.py）
  site/data/YYYY-MM-DD.json ← 本期全文
  site/data/index.json      ← 加入本期，含 composite / dims 六維 / twHeat / stage 快照
                               （這是跨期趨勢圖的唯一資料來源，每期都必須寫齊；
                                 D1/D2/D3/D6 目前不繪製但仍要寫，之後換指標才有歷史）
  updated / updatedLabel 填當下的實際發布時間，不是排程時刻 21:30。
  不要改寫任何既有的 data/*.json，不要動 index.html 除非 schema 真的變了
  （變了就是 brief 第 3 節、build_issue.py、index.html 三處一起改）。

第 6 步：驗證（不可略過，跑在推送之前）
  用 repo 內現成的 verify.py，不要自己重寫一支：
    python3 site/verify.py site/data/YYYY-MM-DD.json \
      --adv adv.txt --pod pod.txt --bub bub/data.json
  ⚠️ --bub 吃的是原始 bub/data.json，不是第 2 步壓縮出來的 bub.txt。
  它檢查六件事：必備欄位與章節數、index.json 量化快照、敘事側逐字回查（含 list[]）、
  量化側欄位名存在性、六維現值與變動 vs history、量化佐證未取自 events。
  任何一項 FAIL 就不要發布——回去修正該條引用或刪除它，重跑到全部通過。
  若動過 index.html，另外抽出 <script> 區塊跑 node --check。

第 7 步：發布與交付
  用 device_commit_files 寫回本機 ~/convergence-weekly，交給 com.kenny.dashpush 自動推送。
  退路：若連不到本機，改用 SendUserFile 附上本期 JSON 與 index.json，
        並明確告知使用者需要手動放進 repo——不要靜靜地跳過發布。
  在訊息裡寫三行：本期最重要的判斷、上一期 watch 清單的驗收結果、發現的資料缺口。
  同時附上線上網址（帶 cache-buster），並確認頁面上的期別按鈕數量與跨期趨勢的點數，
  而不只是看最新一期的日期。
```

---

## 4. 已知的坑

- **不要跑任何 git 指令，含 `git status`。**
  本機 `com.kenny.dashpush` 每 180 秒自動推送，跑 git 會留下 `.git/index.lock` 擋住推送。
  要看狀態只用 `cat` / `ls` / `grep` / `tail`。
  （例外：第 1 節的首次上架，那時 dashpush 還沒接上。）
- **不要刪除或改寫既有的 `data/YYYY-MM-DD.json`。** 歷史全部保留是這套系統的核心。
- **不要只改 brief 或只改排程 prompt 其中一邊。**
- **`index.json` 的量化快照漏寫，趨勢圖就會斷。** 這是最容易犯又最不容易發現的錯——
  頁面不會報錯，只會少一個點。發布後請實際看一眼趨勢圖的期數對不對。
- **pod 的 `takeaways` 不是 JSON。** 直接 `json.loads` 會炸。
- **樣本薄時不要硬判共振。** 投顧側只有 3 天時，同一件事出現在兩天不算「跨天延續」。
- **三方共振要真的是三方獨立。** 監控庫的 `events` 欄位本身就是 Google News，
  如果某條「共振」的量化側證據其實只是 `events` 裡的一則新聞，那不是共振，是同一則新聞被數了兩次。
  **量化側的佐證只能取自 `indicators` / `dims` / `stage` / `tw`，不能取自 `events`。**
  （v0.4 起這條同時寫在 `AGENT_BRIEF.md` 第 5 節與排程 prompt，`verify.py` 會 FAIL。）
- **`verify.py --bub` 吃的是原始 `bub/data.json`，不是 `bub.txt`。**
  餵壓縮檔進去會直接壞掉。敘事側才是 substring 回查，量化側做的是欄位名存在性與數值核對。
- **`build_issue.py` 有防覆寫閘門。** 既有單期檔存在時它會拒跑（要 `--force`）。
  這是刻意的：那支檔案會被當範例反覆閱讀，很容易被順手執行而洗掉歷史。
- **`sections` 必須恰為 4 節。** `index.html` 把「零／五／六」寫死，
  「一～四」的編號寫在各節自己的 `title` 裡。多一節少一節都會讓編號錯亂，`verify.py` 會擋。

---

## 5. 待辦與觀察中

- [x] 首次上架（見第 1 節）——已上架，本機與遠端同步
- [x] 建立排程任務（cron `30 13 * * 0` UTC）——2026-08-03 v0.4 巡檢時建立
- [ ] **確認 `~/.dashpush/auto-push.sh` 的 repo 清單有沒有 `convergence-weekly`。**
      v0.4 巡檢時在沙箱看不到該檔（healthcheck 出 WARN），未能確認。
      驗證方法：改一個字，看 180 秒內會不會自己推上去。
- [ ] 投顧知識庫只保留 3 天封存檔——確認是設計還是異常；會直接影響本系統樣本厚度
- [ ] 觀察：累積 4 期後檢視「跨期趨勢」五格是否選對了指標
      （目前為 composite / stage / D4 / D5 / 台股熱度）
- [ ] 觀察：`feedback` 章節提出的建議有沒有被實際採納，沒有的話這一節要不要留
- [ ] 觀察：第 002 期是第一期由排程自動產出的。要特別看三件事——
      `gaps` 有沒有寫進 JSON、量化佐證有沒有包 `<code>`、上一期 `watch` 有沒有真的被驗收

---

## 6. 事故與決策檔案

### 2026-08-03（v0.4 巡檢）｜三份文件各自都「看起來對」，但關鍵規則掉在縫裡

建站後第一次維護巡檢。`healthcheck.py` 全綠（PASS 19 / FAIL 0），
主線自己讀完三份文件也覺得大致同步。**派兩個獨立子代理去比對，抓出 20 處不同步。**
這再次驗證了維護 skill 裡「子代理獨立比對是固定步驟」這條規則——
機械式檢查抓不到敘述性矛盾，而主線讀完自己寫的東西會傾向認為它是對的。

最傷的三處，共同特徵是**每一份文件單獨看都沒有錯，錯在沒有任何一份包含完整規則**：

1. **「量化佐證不得取自 `events`」只活在 `MAINTENANCE.md` 第 4 節與 `verify.py`。**
   `AGENT_BRIEF.md` 沒有、排程 prompt 沒有。而排程每次觸發都是全新 session，
   只讀 brief 與 prompt——**它從來不會知道這條禁令存在**。
   更糟的是 brief 第 4 節第 2 步還明文要求把 `events` 打進 `bub.txt` 餵給主線，
   等於把違規素材端到面前卻不附警語。
2. **`verify.py` 存在，但兩份文件都只說「寫 Python 檢查」。**
   等於每週叫代理重新發明一支較差的檢查器；而且兩份都把 `--bub` 誤寫成吃 `bub.txt`，
   實際上它吃原始 `data.json`。照文件做會直接壞掉。
3. **樣本不足處置（< 3 天 / < 2 天）整條沒進排程 prompt。**
   而投顧庫就是只保留 3 天——這個分支幾乎每期都會踩到，卻沒寫在會被執行的那份裡。

**教訓：判斷一條規則有沒有真的生效，要問的不是「有沒有寫下來」，
而是「執行時會被讀到的那幾份文件裡有沒有」。** 寫在維護文件裡的規則，排程讀不到。

### 2026-08-03（v0.4）｜為什麼「共識裂縫」降級為標籤，而不是補一個章節

brief 第 0 節宣告四種訊號（共振／背離／裂縫／單邊）是「本系統唯一的產出」，
但實作的四節是 `resonance` / `divergence` / **`taiwan`** / `single`——
裂縫從未落地，台股節則從未在 brief 出現過。

被否決的選項是「補第五節：共識裂縫」。否決理由：裂縫不是每週都有，
硬留一個常常空著的章節，會直接違反「不要為了湊滿章節而硬掰」那條品質規則——
留白的框會逼出內容。

改成把**訊號類型**與**章節結構**明確拆開：類型仍是四種，裂縫變成可掛在任一節的 `tags` 標籤；
章節則正式定義為固定六節，並承認台股節是**閱讀切面**而非訊號類型
（使用者的實際部位在台股，所以不管訊號屬哪一類都額外集中講一次）。

### 2026-08-03（v0.4）｜為什麼修 `build_issue.py` 的內容、卻不重生第 001 期

`build_issue.py` 的 `about.run` 寫死「已對 **40 條**佐證做過回查」，實際只有 21 條 evidence
（含 `list` 也才 31）。同一支檔案的一條量化 evidence 沒有用 `<code>` 包欄位名，
導致 `verify.py` 對它的檢查形同空轉。

修了 `build_issue.py`（條數改為由結構實算、補上 `<code>`），
但**沒有重生 `data/2026-08-03.json`**——歷史全部保留是這套系統的核心，
已發布的一期就是已發布的樣子。代價是這兩處 `build_issue.py` 與第 001 期的實際檔案不再一致；
接受這個代價，因為 `build_issue.py` 的職責是「schema 的可執行文件」，它要當好範例，
而不是當第 001 期的存檔備份。

同時給 `build_issue.py` 加了**防覆寫閘門**（既有單期檔存在就拒跑，要 `--force`）。
理由：它會被當範例反覆閱讀，很容易被順手 `python3 build_issue.py` 一下就洗掉歷史。

### 2026-08-03｜為什麼一定要用兩個平行子代理，而不是一個上下文讀完兩庫

第 001 期建置時實測：若同一個上下文先讀新聞庫再讀 podcast 庫，
它會傾向在 podcast 裡尋找「新聞已經講過的東西」，於是「共振」變成自我實現的預言，
而真正有價值的「只有 podcast 在講」會被系統性地漏掉。
兩個子代理各自不知道對方存在，交回來的清單才是可以拿來比對的獨立樣本。
**這是固定步驟，不是可選項。**

### 2026-08-03｜為什麼量化側由主線自己讀，不派子代理

量化庫很小（一個 `data.json`），而且它在這套系統裡的角色是**裁判**。
裁判的證詞不應該經過另一個模型的轉述——子代理的摘要會把「score 25.8、zone green」
壓縮成「利差偏低」，而背離判定需要的正是前者那種可回查的精確值。

### 2026-08-03｜為什麼合成順序是「先量化、後敘事」

第一次做的時候順序反了（先讀完兩份敘事主題，再去看指標），
結果只找到「指標支持敘事」的三條共振，一條背離都沒找到。
把順序改成先把六維變動攤開、再拿敘事去對，當場就浮出本期最重要的那條
（敘事在講信用危機、HY OAS 三個月卻是收斂的）。
**先看裁判怎麼說，再聽雙方陳述。**

### 2026-08-03｜被否決的選項：把趨勢做成單一多線圖

原本想在跨期趨勢用一張多線折線圖同時畫 composite / D4 / D5 / 台股熱度。
否決理由：四條線量級接近、互相纏繞，而且需要一組通過色盲檢測的類別色，
與「白底紅灰」的品牌配色衝突。
**改成四格小圖（small multiples），各自縮放、單色紅線**——
只比較方向不比較高低，正好符合這幾個指標的實際用途（看誰在升、誰在降），
也避開了類別配色的問題。
