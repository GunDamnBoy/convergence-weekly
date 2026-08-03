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
2. **只在流程或分支判斷改變時**才動排程 prompt，用 `update_trigger` 同步。
   ⚠️ `prompt` 是**整份取代，不是局部編輯**——送出前確認所有段落都帶上了，漏掉的段落等於刪除。
3. 在 brief 第 6 節加變更紀錄，**寫清楚為什麼改**，不只是改了什麼
4. 動到單期 JSON schema 時，`index.html` 的 `renderItem` / `renderQuant` 與
   `build_issue.py` 都要跟著改——**這三處是一組**
5. 事故經過與被否決的選項寫本檔第 6 節

---

## 3. 排程 prompt（整份取代用）

> 建立方式：`create_trigger`，cron **`30 13 * * 0`**（UTC）＝ 台北每週日 21:30。
> 每次觸發都是全新 session，所以 prompt 必須完整、獨立、不依賴任何對話記憶。

```
你要產出「主題匯流訊號報」的新一期——把三個知識庫做跨庫比對，找出共振、背離、裂縫與早期訊號。
全程繁體中文（台灣用語）。完整規格見 repo 內的 AGENT_BRIEF.md，開工前先讀它。

第 1 步：取資料
  git clone --depth 1 https://github.com/GunDamnBoy/convergence-weekly.git site
  git clone --depth 1 https://github.com/GunDamnBoy/advisory-knowledge-hub adv
  git clone --depth 1 https://github.com/GunDamnBoy/podcast-knowledge-digest pod
  git clone --depth 1 https://github.com/GunDamnBoy/ai-bubble-monitor bub
  讀 site/AGENT_BRIEF.md（全部）與 site/data/index.json（看上一期是第幾期、講了什麼）。
  敘事側取過去 7 個日曆天；量化側取 bub/data.json 的 history 全部。
  缺天正常，記下實際涵蓋範圍。

第 2 步：壓縮成摘要層（寫 Python，不要把原始 JSON 讀進上下文）
  adv → adv.txt，pod → pod.txt，bub → bub.txt。格式見 brief 第 4 節第 2 步。
  注意 pod 的 takeaways/sections/meta 是字串化的 Python list，要 ast.literal_eval。

第 3 步：兩個子代理平行萃取敘事側（必須平行、必須互相看不到對方的檔案）
  子代理 A 讀 adv.txt → 8–14 個主題（敘事重心、出現強度、有無轉向、3–5 條逐字佐證）
           ＋「只出現一次但值得注意的訊號」5–8 條
  子代理 B 讀 pod.txt → 8–12 個主題（核心主張、講者分歧最重要、出現強度、2–4 條逐字佐證）
           ＋「podcast 已在講但新聞沒跟上的事」5–8 條
  兩者都要求：佐證逐字取自檔案，寧可少寫也不要編。

第 4 步：主線自己合成（不要外包）。順序有講究——
  先自己讀 bub.txt 把六維變動攤開，再拿兩份敘事主題去對。
  反過來做會讓你只找得到「指標支持敘事」的部分，找不到背離。
  章節：零 量化底盤／一 三方共振／二 關鍵背離／三 台股／四 單邊訊號／五 下週該盯什麼／六 回饋。
  開頭「本期判斷」3 段，必須表態，不要寫「值得持續觀察」這種話。
  背離那一節必須寫出裁判方法：用什麼數字、跨過什麼門檻就知道哪一邊對。
  同時比對上一期的 watch 清單：上期點名要盯的事，這期發生了嗎？有的話寫進本期判斷。

第 5 步：寫檔（schema 見 brief 第 3 節，可參考 site/build_issue.py）
  site/data/YYYY-MM-DD.json ← 本期全文
  site/data/index.json      ← 加入本期，含 composite / dims / twHeat / stage 快照
                               （這是跨期趨勢圖的唯一資料來源，每期都必須寫）
  不要改寫任何既有的 data/*.json，不要動 index.html 除非 schema 變了。
  用 device_commit_files 寫回本機 ~/convergence-weekly，交給 com.kenny.dashpush 自動推送。

第 6 步：驗證（不可略過）
  寫 Python 把本期每一條 evidence 的關鍵子字串拿回 adv.txt/pod.txt/bub.txt 做 substring 比對。
  找不到就修正該條引用或刪除它，重跑直到全部通過。
  再用 node --check 驗 index.html 的 script 區塊（若有動到）。

第 7 步：交付
  用 SendUserFile 附上本期 JSON，並在訊息裡寫三行：本期最重要的判斷、
  上一期 watch 清單的驗收結果、發現的資料缺口。
  同時附上線上網址（記得帶 cache-buster）。
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

---

## 5. 待辦與觀察中

- [ ] 首次上架（見第 1 節）與接上 `com.kenny.dashpush`
- [ ] 建立排程任務（cron `30 13 * * 0` UTC）
- [ ] 投顧知識庫只保留 3 天封存檔——確認是設計還是異常；會直接影響本系統樣本厚度
- [ ] 觀察：累積 4 期後檢視「跨期趨勢」四格是否選對了指標（目前為 composite / D4 / D5 / 台股熱度）
- [ ] 觀察：`feedback` 章節提出的建議有沒有被實際採納，沒有的話這一節要不要留

---

## 6. 事故與決策檔案

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
