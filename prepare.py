#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主題匯流訊號報 · 備料（排程流程的第一步，機械環節全部在這裡）

用法：
    python3 prepare.py [--work work] [--no-clone] [--site …] [--emit-skeleton]

做的事（全部確定性，不需要模型參與）：
  1. clone **五庫**（adv / pod / bub / cotd / res；--no-clone 可重用既有的 work/）
  2. 依 AGENT_BRIEF.md 第 4 節「備料」的摘要層規格產出四份摘要層：
       work/adv.txt   每卡一行，body 截斷自動下調（110→80→60→45）以壓在 60K 內
       work/pod.txt   每集三行＋完整 crossCut，目標 ≤24K（summary 截斷 420→300→220）
       work/bub.txt   composite＋三層＋quadrant＋triggers＋22 項指標＋stage＋tw＋events
       work/cotd.txt  每張圖六行（不含 series/option），超過 15K 先截 reading 至 300 字
       work/res.txt   crosscut 全文＋每筆分析師原句＋watch，目標 ≤30K（**不含 summary**）
       work/stances.json  外資報告的立場帳本原樣複製一份，給 publish 的閘門讀
  3. 寫 work/PREP.md，段落依序：🛑 上游改版偵測（指紋 diff，變更時才出現）→ 涵蓋統計
     → 上一期資訊與 watch 全文 → **量化底盤全文** → triggers 狀態表 →
     **訊號帳本**（戰績＋未結案帳目逼驗收）→ 樣本偏薄旗標 → 零新增資料提示 → 骨架說明
  3b. --emit-skeleton 時另寫 work/skeleton.json：單期 JSON 骨架。
     quant 的**數值**欄位全部抄好（composite／zone／stage.current／twHeat／quadrant／
     三層與變動／triggers 全帶），但 dims[].note、stage.delta、callout、quant.note
     仍標「（填：…）」——那幾欄是判斷不是抄寫。
  4. 印出 PREP.md 到 stdout——排程主線只需要讀這份與摘要層，不必碰任何原始 JSON

exit code：0 正常；3 = 五庫全部沒有比上一期更新的資料（依規格 §2.1 不應產期）
"""
import json, os, sys, re, ast, subprocess, argparse, datetime as dt, zoneinfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cwlib import (baseline, dim_ids, schema_ver, is_lit, zone_label,
                   upstream_fingerprint, diff_fingerprint, need)

REPOS = {
    # **系統 id 是 advisory-knowledge-hub，repo 是 advisory-rewrite —— 兩者不同。**
    # 2026-09-29 才發現：同名的舊 repo 停在 2026-08-18、clone 照樣成功、只是窗口內
    # 沒有檔，於是第 008、009 兩期都把「抓錯 repo」寫成了「投顧庫窗口內無檔」。
    # 排程 prompt 第 1 步會 grep 這一行確認來源，改名時兩邊一起改。
    "adv":  "https://github.com/GunDamnBoy/advisory-rewrite",
    "pod":  "https://github.com/GunDamnBoy/podcast-knowledge-digest",
    "bub":  "https://github.com/GunDamnBoy/ai-bubble-monitor",
    "cotd": "https://github.com/GunDamnBoy/chart-of-the-day",
    # 第五庫，2026-08-23 加入。**它的上游是券商 PDF，與新聞不同源**，
    # 所以計票上是獨立的第四票（見 checks/convergence.py 的 VOICE 表）。
    "res":  "https://github.com/GunDamnBoy/broker-research-digest",
}

def sh(args, what=""):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        sys.exit(f"❌ {what or args[0]} 超過 180 秒無回應——上游（GitHub）可能掛了或網路異常。")
    if r.returncode:
        sys.exit(f"指令失敗：{' '.join(args)}\n{r.stderr[:500]}")

def jload(p):
    return json.load(open(p, encoding="utf-8"))

def pylit(v):
    """pod 的 takeaways/sections/meta 是字串化的 Python list。"""
    if isinstance(v, (list, dict)): return v
    try: return ast.literal_eval(v)
    except Exception: return []

def dated_files(d, lo, hi):
    out = []
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        m = re.match(r"(20\d\d-\d\d-\d\d)\.json$", f)
        if m and lo <= m.group(1) <= hi:
            out.append((m.group(1), os.path.join(d, f)))
    return out

def build_adv(files):
    """每卡一行；截斷長度自動下調（110→80→60→45），不減卡片則數。bullets 空時退用 body[0]。"""
    def render(trunc):
        parts, ncard = [], 0
        for date, fp in files:
            d = jload(fp)
            parts.append(f"\n===== {date}｜{d.get('headline','')} =====")
            snap = (d.get("overview") or {}).get("snap", "")
            if snap: parts.append(f"[snap] {snap}")
            for s in d.get("sections", []):
                for g in s.get("groups", []):
                    parts.append(f"-- {s.get('title','')}／{g.get('label','')} --")
                    for c in g.get("cards", []):
                        ncard += 1
                        star = "★" if c.get("deep") else ""
                        first = (c.get("bullets") or c.get("body") or [""])[0]
                        parts.append(f"{star}({c.get('src','')}/{c.get('tag','')}) "
                                     f"{c.get('title','')} || {str(first)[:trunc]}")
        return "\n".join(parts), ncard
    # 目標 40–60K；來源庫已擴編（26 家、7 天可達 800+ 卡），截斷到底仍超標時
    # 接受超標並如實回報——規格說了覆蓋率比細節重要，不減卡片則數。
    for trunc in (110, 80, 60, 45):
        txt, ncard = render(trunc)
        if len(txt) <= 60000: break
    return txt, ncard, trunc

def build_pod(files):
    """crossCut 一律全文（規格：不可省略）；超標時只縮 summary 截斷。"""
    def render(slim):
        parts, nep = [], 0
        for date, fp in files:
            d = jload(fp)
            parts.append(f"\n===== {date}｜{d.get('label','')} =====")
            cc = d.get("crossCut") or {}
            if cc:
                parts.append(f"[交叉觀察] {cc.get('title','')}\n{cc.get('intro','')}")
                for p in cc.get("points", []):
                    parts.append(f"  · {p.get('title','')}：{p.get('body','')}")
            for e in d.get("episodes", []):
                nep += 1
                parts.append(f"▸{e.get('show','')}｜{e.get('title','')}")
                parts.append(str(e.get("summary",""))[:slim])
                tks = [t.get("title", t) if isinstance(t, dict) else str(t)
                       for t in pylit(e.get("takeaways", []))]
                if tks: parts.append("takeaways: " + "｜".join(map(str, tks)))
        return "\n".join(parts), nep
    for slim in (420, 300, 220):
        txt, nep = render(slim)
        if len(txt) <= 24000: break
    return txt, nep, slim

def build_bub(b):
    p = [f"composite = {b.get('composite')}",
         f"meta.built = {(b.get('meta') or {}).get('built')}"]
    h = b.get("history", [])
    cur_keys = set(b.get("dims", {}))
    same = sorted([r for r in h if set(r.get("dims", {})) == cur_keys],
                  key=lambda r: r.get("date",""))
    first = same[0] if same else None
    p.append("\n[層分數]（變動＝現值 − 同架構最早一筆"
             f"{'（'+first['date']+'）' if first else '——history 無同架構筆，無變動可算'}）")
    for k in sorted(b.get("dims", {})):
        cur = b["dims"][k]; m = (b.get("dimMeta") or {}).get(k, {})
        dl = f"　變動 {round(cur - first['dims'][k],1):+}" if first else "　變動 —（無同架構基準）"
        p.append(f"  {k} {m.get('name','')} w={m.get('w','')}: {cur}{dl}　{str(m.get('note') or '')[:60]}")
    qd = b.get("quadrant") or {}
    if qd: p.append(f"\n[象限] heat={qd.get('heat')} support={qd.get('support')} regime={qd.get('regime')}")
    tg = b.get("triggers") or []
    if tg:
        p.append(f"\n[觸發器]（{sum(1 for x in tg if x.get('state'))}/{len(tg)} 已觸發）")
        for x in tg:
            p.append(f"  {'●' if x.get('state') else '○'} {x['id']}: {x.get('name','')}"
                     f"｜value={x.get('value')}｜asof={x.get('asof')}")
    p.append(f"\n[指標 {len(b.get('indicators',[]))} 項]")
    for i in b.get("indicators", []):
        p.append(f"  {i['id']}({i.get('dim','')}) {i.get('name','')} = {i.get('disp', i.get('value'))}"
                 f"｜zone {i.get('zone')}｜score {i.get('score')}｜asof {i.get('asof')}")
    st = b.get("stage") or {}
    p.append(f"\n[階段] current={st.get('current')}（{st.get('label','')}）")
    if st.get("note"): p.append(f"  note: {st['note']}")
    for c in st.get("checklist", []):
        p.append(f"  {'☑' if c.get('state') else '☐'} {c.get('item','')}｜{str(c.get('evi',''))[:80]}")
    tw = b.get("tw") or {}
    p.append(f"\n[台股] heat={tw.get('heat')}")
    for i in tw.get("items", []):
        p.append(f"  {i['id']} {i.get('name','')} = {i.get('disp', i.get('value'))}"
                 f"｜score {i.get('score')}｜asof {i.get('asof')}")
    ev = b.get("events") or []
    p.append(f"\n[events {len(ev)} 則]（Google News——只能當哨兵核對投顧側漏了什麼，**不得當量化佐證**）")
    for e in ev[:40]:
        p.append(f"  {e.get('d','')}｜{e.get('t','')}")
    return "\n".join(p)

def build_cotd(files):
    def render(rlim):
        parts, nch = [], 0
        for date, fp in files:
            d = jload(fp)
            parts.append(f"\n===== {date}｜{d.get('headline','')} =====")
            if d.get("standfirst"): parts.append(d["standfirst"])
            for c in d.get("charts", []):
                nch += 1
                parts.append(f"▸{c.get('slot','')}｜{c.get('theme','')}｜{c.get('title','')}")
                parts.append(f"  {c.get('subtitle','')}")
                parts.append(f"  takeaway: {c.get('takeaway','')}")
                parts.append(f"  so_what: {c.get('so_what','')}")
                r = str(c.get("reading",""))
                parts.append(f"  reading: {r if rlim is None else r[:rlim]}")
                if c.get("watch"): parts.append(f"  watch: {'｜'.join(map(str,c['watch']))}")
                if c.get("tags"):  parts.append(f"  tags: {'/'.join(map(str,c['tags']))}")
            qa = (d.get("about") or {}).get("qa_flags") or []
            for q in qa:
                parts.append(f"  [qa_flag] {q}")
        return "\n".join(parts), nch
    txt, nch = render(None)
    for rlim in (300, 200):      # 先截 reading；takeaway/so_what 一律全文
        if len(txt) <= 15000: break
        txt, nch = render(rlim)
    return txt, nch

def build_res(files):
    """外資報告週摘 → `res.txt`。回 (文字, 報告份數, 原句筆數)。

    ## 吃 `crosscut` 與 `stances`，**不吃 `summary`**

    量出來（2026-08-23，當期 23 份）：`summary` 合計 106,449 字元，
    `stances` 81 筆的原句＋中譯合計 16,352 字元 —— **15%**。

    - `summary` 是寫給人讀的精華，而它**已經被 `crosscut` 綜合過了**。
      再讀一次等於兩個系統對同一批 PDF 做同一件事，下游那次還看得比較少。
    - `crosscut` 是**賣方這一票的立場本身**。它已經在做跨券商的共振與分歧分析
      （原文：「兩家看的是同一組資料、給出相反的方向」），所以匯流讀它、不重做它。
    - `stances` 是分析師的逐字原句，帶主題、頁碼、券商、日期、到期日 ——
      **這個庫裡訊號密度最高、而且是唯一可證偽的那一層**。

    ## 上限 30K，是量出來的不是拍的

    2026-08-23 實測（當期 23 份、81 筆原句，合計 23,657 字元）：

    | 組成 | 字元 | 占比 |
    |---|---|---|
    | 原句 `quote` | 12,292 | **52.0%** |
    | 中譯 `quote_zh` | 4,060 | 17.2% |
    | 報告標題行 | 3,112 | 13.2% |
    | `crosscut`（全文，不截） | 2,205 | 9.3% |
    | 其餘（theme／watch／notes） | 1,988 | 8.4% |

    第一版把上限拍成 20K，於是每一期都會超標 —— 而**一條天天被違反的規格
    就不是規格**。上限改成 30K，那是實測值加約 25% 的餘裕。

    ## 截原句，不減筆數 —— 而這個階梯平時不會動

    原句平均 **152 字元**，本來就低於階梯最低的那一階（160），
    所以在 30K 的上限下它一次都不會觸發。**那是刻意留著的**：
    某一週要是進來一份原句特別長的報告（平均 >250 字），它才會動。

    **不要為了讓階梯「有用」而把上限調低** —— 52% 的內容是原句，
    而原句是這個庫裡唯一可證偽的那一層。少一筆原句等於少一條可以被裁決的主張。
    """
    def render(qlim):
        parts, nrep, nst = [], 0, 0
        for date, fp in files:
            d = jload(fp)
            parts.append(f"\n===== {date}｜{d.get('week','')}｜"
                         f"{d.get('reports_count', len(d.get('reports') or []))} 份 =====")
            cc = d.get("crosscut")
            if cc:
                # **`crosscut` 一律全文。** 它是賣方那一票的立場，截斷等於改立場。
                parts.append("【跨報告觀察（賣方這一票的立場）】")
                parts.append(str(cc))
            for r in (d.get("reports") or []):
                nrep += 1
                parts.append(f"▸{r.get('broker','')}｜{r.get('title','')}"
                             f"｜{r.get('date','')}｜{r.get('pages','?')}頁"
                             + (f"｜{'/'.join(r.get('tags') or [])}" if r.get("tags") else ""))
                for st in (r.get("stances") or []):
                    nst += 1
                    q = str(st.get("quote") or "")
                    parts.append(f"  ◆{st.get('theme','')}｜p{st.get('page','?')}｜"
                                 + (q if qlim is None else q[:qlim]))
                    if st.get("quote_zh"):
                        parts.append(f"    {st['quote_zh']}")
            for w in (d.get("watch") or []):
                parts.append(f"  [watch] {w}")
            for n in (d.get("notes") or []):
                parts.append(f"  [note] {n}")
        return "\n".join(parts), nrep, nst
    txt, nrep, nst = render(None)
    for qlim in (300, 220, 160):
        if len(txt) <= 30000: break
        txt, nrep, nst = render(qlim)
    return txt, nrep, nst


def due_stances(res_dir, today, horizon=7):
    """**到期待裁決的分析師主張。** 回 (清單, 總筆數, 已裁決筆數)。

    外資報告的 `stances.json` 是一份可證偽帳本：96 筆原句，帶
    `due`（報告日 + 3 個月）、`status`、`verdict`。**而沒有任何流程在判它們。**

    匯流是唯一同時看得到「主張」（券商原句）與「證據」（量化指標、新聞、節目）
    的地方，而且它是週頻，正好對得上到期節奏 —— 所以裁決歸這裡。

    窗口是 `today + horizon`，**刻意往前看一週**：到期當週才發現要判，
    那一期已經沒有時間去找證據了。

    **回空清單與「找不到帳本」要分得開** —— 前者是這一週沒有到期的，
    後者是上游改了檔案位置，而兩者在輸出上長得一模一樣。
    """
    p = os.path.join(res_dir, "data", "stances.json")
    if not os.path.exists(p):
        return None, 0, 0        # None ＝ 沒有帳本，跟「這週沒有到期的」是兩件事
    items = (jload(p) or {}).get("items") or []
    done = sum(1 for x in items if (x.get("verdict") or "").strip())
    cut = str(dt.date.fromisoformat(str(today)) + dt.timedelta(days=horizon))
    due = [x for x in items
           if not (x.get("verdict") or "").strip() and str(x.get("due", "")) <= cut]
    due.sort(key=lambda x: (x.get("due", ""), x.get("id", "")))
    return due, len(items), done


def build_skeleton(bub, site, adv_f, pod_f, cotd_f, prev, today, counts, res_cov=None):
    """產出單期 JSON 骨架：所有能從資料推導的欄位全部填好。

    仍要填的是所有標「（填：…）」的欄位：headline／stamp／verdict／sections（含 lede
    與 items）／watch／gaps／about.run，以及 quant 裡的 dims[].note／stage.delta／
    callout／quant.note 四處。calls 有空殼佔位，依 brief 3.2 末的登帳準則填。
    quant 整區是純機械的（全部從 bub 抄），手打既慢又容易抄錯——
    第 002 期就是手打 quant 時把 watch 的 trigger id 標成 indicator id。
    """
    h = bub.get("history", [])
    cur = bub.get("dims", {})
    first, same = baseline(bub)
    dm = bub.get("dimMeta", {})
    dims = []
    for k in sorted(cur):
        m = dm.get(k, {})
        dims.append({
            "id": k, "name": m.get("name", ""),
            "w": f"{int(round(float(m.get('w', 0))*100))}%",
            "v": cur[k],
            "delta": round(cur[k] - first["dims"][k], 1) if first else None,   # None＝無基準，前端印「—」；不要填 0.0 假裝持平
            "note": "（填：這一層本期為什麼動／沒動）",
        })
    qd = bub.get("quadrant") or {}
    st = bub.get("stage") or {}
    lit = [c for c in st.get("checklist", []) if c.get("state")]
    zl = zone_label(bub) or "（填：對照 bub.txt 的 zones）"
    issue_no = prev["issue"] + 1
    _nd = sorted({x[0] for x in (adv_f + pod_f + cotd_f)})
    def _dlabel(a, b):
        # 跨年時保留年份，否則「12/28 – 01/03」讀起來像倒著寫
        if a[:4] != b[:4]:
            return f"{a.replace('-','/')} – {b.replace('-','/')}"
        return f"{a[5:].replace('-','/')} – {b[5:].replace('-','/')}"
    rng_n = _dlabel(_nd[0], _nd[-1]) if _nd else "—"
    _built = str((bub.get("meta") or {}).get("built") or "")[:10]
    rng_q = _dlabel(same[0]["date"], _built) if same and re.match(r"20\d\d-\d\d-\d\d$", _built) else "—"
    return {
        "date": str(today), "issue": issue_no,
        "label": f"第 {issue_no:03d} 期 · {today.year} 年 {today.month} 月 {today.day} 日",
        "schemaVer": "2",
        "stamp": f"五庫比對．第 {issue_no:03d} 期",
        "range": {"quant": rng_q, "narrative": rng_n},
        "headline": "（填：一句話，要有觀點，不是主題標籤）",
        "coverage": [
            {"k": "投顧知識庫", "v": f"{len(adv_f)} 天 / {counts.get('card',0)} 則卡片"},
            {"k": "節目知識庫", "v": f"{len(pod_f)} 天 / {counts.get('ep',0)} 集"},
            {"k": "AI 泡沫監控", "v": f"history {len(h)} 筆 / {len(bub.get('indicators',[]))} 項指標"},
            {"k": "每日五圖", "v": f"{len(cotd_f)} 天 / {counts.get('chart',0)} 張"},
            # 第五庫。2026-09-29 前骨架只吐四列，排程每期手補 —— 規格改了、骨架沒跟上。
            {"k": "外資報告週摘", "v": res_cov or "0 期（本窗口無）"},
        ],
        "verdict": ["（填：段 1，必須表態）", "（填：段 2，上一期 watch 逐條驗收）",
                    "（填：段 3，本期唯一無可取代的發現）"],
        "quant": {
            "schemaVer": schema_ver(bub),
            "composite": bub.get("composite"),
            "zone": zl,
            "note": f"基準 {first['date'] if first else '—'}（同架構最早一筆）"
                    f"　（填：一句話說明 composite 這期為什麼動）",
            "stage": {"current": st.get("current"), "label": st.get("label", ""),
                      "lit": f"{len(lit)}／{len(st.get('checklist', []))}",
                      "delta": "（填：本期有無新增點亮）"},
            "twHeat": (bub.get("tw") or {}).get("heat"),
            "quadrant": {k: qd.get(k) for k in ("heat", "support", "regime")},
            "triggers": [{k: x[k] for k in ("id", "name", "state", "value", "asof") if k in x}
                         for x in bub.get("triggers", [])],
            "dims": dims,
            "callout": {"h": "（填：這張圖要看的重點）", "body": "（填）"},
        },
        "sections": [
            {"id": i, "title": t, "lede": "（填）", "items": []}
            # v2 六節，順序鎖死（brief §3.0）。2026-09-29 前這裡只有五節、缺 verdicts。
            for i, t in (("resonance", "一 · 三方共振"), ("divergence", "二 · 關鍵背離"),
                         ("verdicts", "三 · 賣方對帳"), ("taiwan", "四 · 台股"),
                         ("charts", "五 · 圖表側寫"), ("single", "六 · 單邊訊號"))
        ],
        # 賣方對帳的機器讀版本（brief §3.0）。本期 0 筆到期時就是空陣列，verdicts 節仍要一個說明 item。
        "rulings": [],
        # ⚠️ 佔位字串裡刻意不寫真的 trigger id、也不放 <code>——
        # 否則 verify.py 第 5.6 項會把佔位當成「提到 trigger 卻標錯」而誤報。
        # 合法 id 清單在 PREP.md 的觸發器表。
        "watch": ["（填：每條可觀察可證偽。能對應觸發器的條目要用行內 code 標出正確的"
                  " trigger id，清單見 PREP.md 觸發器表）"],
        "calls": {"open": [], "close": []},   # 登帳與結案，準則見 brief 3.2 末；PREP.md 的帳本段列了待驗收帳目
        "gaps": ["（填：缺天／各庫 updatedLabel 過期／指標 asof 落後／卡片數異常／圖表庫 qa_flags）"],
        "about": {"run": "（填：本期執行紀錄與樣本厚度）",
                  "method": "prepare.py 備料 → 兩個平行子代理讀敘事側 → 主線併入量化底盤與賣方側合成 → kb-core 閘門（checks/convergence.py）逐字回查後發布"},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="work")
    ap.add_argument("--no-clone", action="store_true")
    ap.add_argument("--emit-skeleton", action="store_true",
                    help="另外寫出 work/skeleton.json：單期 JSON 骨架，quant 整區已填好")
    ap.add_argument("--site", default=os.path.dirname(os.path.abspath(__file__)))
    a = ap.parse_args()
    W = a.work; os.makedirs(W, exist_ok=True)

    if not a.no_clone:
        for k, url in REPOS.items():
            d = os.path.join(W, k)
            if not os.path.isdir(os.path.join(d, ".git")):
                sh(["git", "clone", "--depth", "1", "-q", url, d], f"clone {k}")
            else:
                # 既有 clone 一定要 pull——殘留上週的 work/ 會靜靜地拿舊資料備料
                sh(["git", "-C", d, "pull", "-q", "--ff-only"], f"pull {k}")

    today = dt.datetime.now(zoneinfo.ZoneInfo("Asia/Taipei")).date()
    lo, hi = str(today - dt.timedelta(days=6)), str(today)

    for k, sub in (("adv", "data"), ("pod", "data"), ("cotd", "data"), ("res", "data")):
        dd = os.path.join(W, k, sub)
        if not os.path.isdir(dd):
            sys.exit(f"❌ {k} 的 {sub}/ 目錄不存在——這不是「沒新聞」，是上游改了目錄結構。"
                     f"先去確認該 repo，再依失效模式 3.4 處理。")
    bp = os.path.join(W, "bub", "data.json")
    if not os.path.exists(bp):
        sys.exit("❌ 監控庫的 data.json 不存在——上游可能改了檔案位置。")
    adv_f  = dated_files(os.path.join(W, "adv",  "data"), lo, hi)
    pod_f  = dated_files(os.path.join(W, "pod",  "data"), lo, hi)
    cotd_f = dated_files(os.path.join(W, "cotd", "data"), lo, hi)
    # 外資報告是**週頻**：7 天窗口裡最多一份，常常是零份（它有手動補發，週次會跳）。
    # 零份不是失敗，但要說出來 —— 空的 res.txt 會讓賣方側的佐證檢查
    # vacuously 通過，而那跟「這週券商沒東西」長得一模一樣。
    res_f  = dated_files(os.path.join(W, "res",  "data"), lo, hi)
    bub    = jload(bp)

    adv_t, ncard, trunc = build_adv(adv_f)
    pod_t, nep, slim = build_pod(pod_f)
    bub_t       = build_bub(bub)
    cotd_t, nch = build_cotd(cotd_f)
    res_t, nrep, nst = build_res(res_f)
    if not res_f:
        res_t = ("（本窗口內沒有外資報告週摘 —— 它是週頻且會手動補發，週次會跳。\n"
                 "  這不是失敗，但**賣方側這一週沒有票**，共振計票要照這個事實算。）")
    for name, txt in (("adv", adv_t), ("pod", pod_t), ("bub", bub_t),
                      ("cotd", cotd_t), ("res", res_t)):
        open(os.path.join(W, f"{name}.txt"), "w", encoding="utf-8").write(txt)

    # 上一期資訊（site 的 index.json 與單期檔）
    idx = jload(os.path.join(a.site, "data", "index.json"))
    # **索引鍵是 `days`，不是 `issues`**（2026-08-23 遷移，對齊 kb-core 的發布軌）。
    # 三種狀態要分得開 —— 一個「空的」訊息會把人指去「site 沒 clone 對」，
    # 而真正的原因是 repo 還沒遷移。**大聲失敗但診斷錯，只做對了一半。**
    if idx.get("issues") is not None and idx.get("days") is None:
        sys.exit("❌ 這個 repo 的 index.json 還是舊的 `issues` 鍵 —— "
                 "先跑 kb-core 的 tools/convergence_migrate_index.py。")
    if not idx.get("days"):
        sys.exit("❌ index.json 的 days 是空的——site 沒 clone 對、或這是尚未初始化的 repo。")
    prev = idx["days"][0]
    if "file" not in prev or "issue" not in prev:
        sys.exit("❌ index.json 最新一期缺 file/issue 欄位——index 可能壞了，先跑 healthcheck。")
    prev_full = jload(os.path.join(a.site, prev["file"]))
    latest = {
        "投顧": adv_f[-1][0] if adv_f else "（窗口內無檔）",
        "節目": pod_f[-1][0] if pod_f else "（窗口內無檔）",
        # 監控用 meta.built——history 盤後會落後頂層一格，不能拿它判斷新舊
        "監控": str((bub.get("meta") or {}).get("built") or "（無 meta.built）")[:10],
        "圖表": cotd_f[-1][0] if cotd_f else "（窗口內無檔）",
    }
    # 只有合法日期字串才能參與比較——「（窗口內無檔）」之類的值
    # 在字串比較裡大於任何日期，會讓零新增判定永遠不觸發
    is_date = lambda s: bool(re.match(r"20\d\d-\d\d-\d\d$", str(s)))
    fresh = [k for k, v in latest.items() if is_date(v) and v > prev["date"]]
    tg = bub.get("triggers") or []
    lit_n = sum(1 for x in tg if is_lit(x))

    # ── 上游改版偵測：對 data/upstream.json（上一期發布時的指紋）做明文 diff ──
    fp_now = upstream_fingerprint(bub)
    fp_path = os.path.join(a.site, "data", "upstream.json")
    fp_old = jload(fp_path) if os.path.exists(fp_path) else None
    fp_diff = diff_fingerprint(fp_old, fp_now)

    # ── 訊號帳本：把未結案的判斷攤開，逼本期驗收 ──
    calls_path = os.path.join(a.site, "data", "calls.json")
    calls = jload(calls_path).get("calls", []) if os.path.exists(calls_path) else []
    open_calls = [c for c in calls if c.get("status") == "open"]
    closed = [c for c in calls if c.get("status") in ("hit", "miss", "expired")]
    # void（人工作廢）刻意不計戰績、不列未結案——不是帳目遺失，見 MAINTENANCE 已知的坑
    n_hit = sum(1 for c in closed if c["status"] == "hit")
    n_miss = sum(1 for c in closed if c["status"] == "miss")
    thin = []
    if len(adv_f) <= 3: thin.append(f"投顧僅 {len(adv_f)} 天（≤3，about.run 須註明、共振保守）")
    if len(pod_f) <= 2: thin.append(f"節目僅 {len(pod_f)} 天（≤2，同上）")
    if len(cotd_f) < 3: thin.append(f"圖表僅 {len(cotd_f)} 天（<3，「圖表側寫」只列可用的）")

    md = [f"# PREP · {today}（窗口 {lo} ～ {hi}）\n"]
    if fp_diff:
        md += ["## 🛑 上游改版偵測（監控庫與上一期發布時的指紋不一致）",
               "以下差異**必須寫進本期 `gaps`**；若涉及維度或權重，跨期比較要依規格處理斷點。"]
        md += [f"- {d}" for d in fp_diff]
        md += [""]
    elif fp_old is None:
        md += ["> （首次執行指紋偵測：本期發布後將建立 data/upstream.json 基準）", ""]
    md += [
          "## 涵蓋",
          f"- 投顧 {len(adv_f)} 天／{ncard} 卡（body 截斷 {trunc} 字）→ adv.txt {len(adv_t)//1000}K",
          f"- 節目 {len(pod_f)} 天／{nep} 集（summary 截斷 {slim} 字）→ pod.txt {len(pod_t)//1000}K",
          f"- 監控 history {len(bub.get('history',[]))} 筆 → bub.txt {len(bub_t)//1000}K",
          f"- 圖表 {len(cotd_f)} 天／{nch} 張 → cotd.txt {len(cotd_t)//1000}K",
          (f"- 券商 {len(res_f)} 期／{nrep} 份／原句 {nst} 筆 → res.txt {len(res_t)//1000}K"
           if res_f else "- 券商 **本窗口 0 期**（週頻且會手動補發）→ 賣方側這一週沒有票"),
          f"- 各庫最新：{'　'.join(f'{k} {v}' for k,v in latest.items())}",
          f"\n## 上一期：第 {prev['issue']:03d} 期（{prev['date']}）",
          f"- headline：{prev['headline']}",
          f"- errata：{len(prev.get('errata', []))} 條",
          "\n### 上一期 watch（逐條驗收，結果寫進本期 verdict）"]
    md += [f"{i+1}. {w}" for i, w in enumerate(prev_full.get("watch", []))]
    # ── 量化底盤直接內嵌，主線讀 PREP.md 就有全部量化面 ──
    _cur = bub.get("dims", {})
    _first, _same = baseline(bub)
    _dm = bub.get("dimMeta", {})
    _qd = bub.get("quadrant") or {}
    _st = bub.get("stage") or {}
    _tw = bub.get("tw") or {}
    md += [f"\n## 量化底盤（bub.txt 只在要查特定指標時才需要讀）",
           f"- composite **{bub.get('composite')}**"
           f"　象限 heat {_qd.get('heat')} / support {_qd.get('support')}"
           f"　regime **{_qd.get('regime')}**",
           f"- 階段 stage **{_st.get('current')}**（{_st.get('label','')}）"
           f"　點亮 {sum(1 for c in _st.get('checklist',[]) if c.get('state'))}"
           f"／{len(_st.get('checklist',[]))}"
           f"　台股熱度 **{_tw.get('heat')}**",
           f"- 層分數（變動＝現值 − 同架構最早一筆"
           f"{'，基準 '+_first['date'] if _first else '，history 無同架構筆'}）："]
    for k in sorted(_cur):
        _m = _dm.get(k, {})
        _d = f"{round(_cur[k]-_first['dims'][k],1):+}" if _first else "—"
        md += [f"  - **{k} {_m.get('name','')}**（w {_m.get('w','')}）：{_cur[k]}　變動 {_d}"]
    md += [f"\n## 觸發器（{lit_n}/{len(tg)} 已觸發；背離節裁判方法優先引用）",
           "> `watch[]` 能對應到 trigger 的條目**必須用 `<code>id</code>` 標出下表的 id**"
           "（不是 indicator id），下期驗收才能直接查 `state` 翻轉。`verify.py` 會擋。"]
    md += [f"- {'●' if x.get('state') else '○'} `{x['id']}` {x.get('name','')}"
           f"｜{x.get('value')}｜asof {x.get('asof')}" for x in tg]
    md += [f"\n## 訊號帳本（戰績 {n_hit} 勝 {n_miss} 敗，未結案 {len(open_calls)} 筆）"]
    if open_calls:
        md += ["**逐筆驗收下列未結案判斷**：能裁決的在本期 JSON 的 `calls.close` 結案"
               "（result: hit／miss／expired），裁決理由寫進 verdict；還不能裁決的不要動。"]
        for c in open_calls:
            md += [f"- `{c['id']}`（第 {c.get('issue','?'):03d} 期開）：{c.get('claim','')}"
                   f"｜裁判：{c.get('judge','')}"
                   + (f"｜期限 {c['deadline']}" if c.get("deadline") else "")]
    else:
        md += ["（無未結案帳目。本期若有可證偽的判斷，記得用 `calls.open` 登帳。）"]
    # ── 賣方對帳：把到期的分析師主張攤開，逼本期裁決 ──
    # 跟上面的訊號帳本是同一個機制、不同的帳：那本是匯流自己開的判斷，
    # 這本是**券商說的**。匯流是唯一同時看得到主張與證據的地方，所以裁決歸這裡。
    due, n_st_all, n_st_done = due_stances(os.path.join(W, "res"), today)
    if due is None:
        md += ["\n## ⚠️ 找不到外資報告的立場帳本",
               "`res/data/stances.json` 不存在 —— 上游可能改了檔案位置。"
               "**這跟「這週沒有到期的主張」是兩件事**，要寫進本期 `gaps`。"]
    else:
        md += [f"\n## 賣方對帳（帳本 {n_st_all} 筆，已裁決 {n_st_done} 筆，"
               f"本期到期 {len(due)} 筆）"]
        if due:
            md += ["**逐筆裁決下列分析師主張**，寫進本期 `sections` 的 `verdicts` 節：",
                   "結果三選一 —— 應驗／落空／**未定**。",
                   "**`未定` 必須寫理由。** 沒有理由的未定就是"
                   "「為了讓燈變綠而全部改判無法驗證」，那條機器擋不住，只有你守得住。"]
            for x in due:
                md += [f"- `{x['id']}`（{x.get('broker','')}／{x.get('date','')}／"
                       f"到期 {x.get('due','')}）"
                       f"｜主題：{x.get('theme','')}"
                       f"\n      原句：{str(x.get('quote',''))[:180]}"
                       f"\n      中譯：{str(x.get('quote_zh',''))[:120]}"]
        else:
            md += ["（本期沒有到期的分析師主張。**這不是「都判完了」** ——"
                   f"帳本裡還有 {n_st_all - n_st_done} 筆在觀察中，只是還沒到期。）"]

    if thin:
        md += ["\n## ⚠️ 樣本偏薄"] + [f"- {t}" for t in thin]
    if not fresh:
        md += ["\n## 🛑 零新增資料",
               f"五庫最新日期皆 ≤ 上一期（{prev['date']}）。依規格 §2.1 **不產期**：",
               "在交付訊息寫明「本次未產期」與各庫實際最新日期，不寫任何檔案。"]
    if a.emit_skeleton:
        sk = build_skeleton(bub, a.site, adv_f, pod_f, cotd_f, prev, today,
                            {"card": ncard, "ep": nep, "chart": nch},
                            res_cov=(f"{len(res_f)} 期 / {nrep} 份 / 原句 {nst} 筆" if res_f else None))
        sp = os.path.join(W, "skeleton.json")
        with open(sp, "w", encoding="utf-8") as f:
            json.dump(sk, f, ensure_ascii=False, indent=1)
        md += [f"\n## 骨架已產出：`{sp}`",
               f"第 {sk['issue']:03d} 期。**`quant` 整區已填好**（composite／zone／stage／twHeat／"
               f"quadrant／{len(sk['quant']['dims'])} 層／{len(sk['quant']['triggers'])} 條 triggers），"
               "`date`／`issue`／`label`／`range`／`coverage` 也已填。",
               "你只要填標「（填：…）」的欄位與 `sections[].items`，**不要重打 `quant`**。"]

    # `systems/convergence.py` 的 `build()` 讀 `work/stances.json`。
    # **複製一份而不是叫它去讀 `work/res/data/`** —— work 的形狀是這支的對外契約，
    # 讓下游去猜 clone 出來的目錄結構，等於把上游的目錄佈局變成第二個契約。
    _sp = os.path.join(W, "res", "data", "stances.json")
    if os.path.exists(_sp):
        open(os.path.join(W, "stances.json"), "w", encoding="utf-8").write(
            open(_sp, encoding="utf-8").read())

    out = "\n".join(md)
    open(os.path.join(W, "PREP.md"), "w", encoding="utf-8").write(out)
    print(out)
    if not fresh: sys.exit(3)

if __name__ == "__main__":
    main()
