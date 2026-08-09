#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主題匯流訊號報 · 備料（排程流程的第一步，機械環節全部在這裡）

用法：
    python3 prepare.py [--work work] [--no-clone] [--site …] [--emit-skeleton]

做的事（全部確定性，不需要模型參與）：
  1. clone 四庫（adv / pod / bub / cotd；--no-clone 可重用既有的 work/）
  2. 依 AGENT_BRIEF.md 第 4 節第 2 步的規格產出四份摘要層：
       work/adv.txt   每卡一行，body 截斷自動下調（110→80→60→45）以壓在 60K 內
       work/pod.txt   每集三行＋完整 crossCut，目標 ≤24K（summary 截斷 420→300→220）
       work/bub.txt   composite＋三層＋quadrant＋triggers＋22 項指標＋stage＋tw＋events
       work/cotd.txt  每張圖六行（不含 series/option），超過 15K 先截 reading 至 300 字
  3. 寫 work/PREP.md：涵蓋統計與摘要層大小、各庫最新日期、上一期資訊與 watch 清單全文、
     **量化底盤全文**（composite／象限／階段／台股熱度／三層變動）、triggers 狀態表、
     樣本偏薄旗標、零新增資料提示
  3b. --emit-skeleton 時另寫 work/skeleton.json：單期 JSON 骨架。
     quant 的**數值**欄位全部抄好（composite／zone／stage.current／twHeat／quadrant／
     三層與變動／triggers 全帶），但 dims[].note、stage.delta、callout、quant.note
     仍標「（填：…）」——那幾欄是判斷不是抄寫。
  4. 印出 PREP.md 到 stdout——排程主線只需要讀這份與摘要層，不必碰任何原始 JSON

exit code：0 正常；3 = 四庫全部沒有比上一期更新的資料（依規格 §2.1 不應產期）
"""
import json, os, sys, re, ast, subprocess, argparse, datetime as dt, zoneinfo

REPOS = {
    "adv":  "https://github.com/GunDamnBoy/advisory-knowledge-hub",
    "pod":  "https://github.com/GunDamnBoy/podcast-knowledge-digest",
    "bub":  "https://github.com/GunDamnBoy/ai-bubble-monitor",
    "cotd": "https://github.com/GunDamnBoy/chart-of-the-day",
}

def sh(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"指令失敗：{cmd}\n{r.stderr[:500]}")

def jload(p):
    return json.load(open(p, encoding="utf-8"))

def lit(v):
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
                       for t in lit(e.get("takeaways", []))]
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
        dl = f"　變動 {round(cur - first['dims'][k],1):+}" if first else ""
        p.append(f"  {k} {m.get('name','')} w={m.get('w','')}: {cur}{dl}　{m.get('note','')[:60]}")
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

def build_skeleton(bub, site, adv_f, pod_f, cotd_f, prev, today, counts):
    """產出單期 JSON 骨架：所有能從資料推導的欄位全部填好。

    主線只需要填 verdict / sections / watch / gaps / about.run。
    quant 整區是純機械的（全部從 bub 抄），手打既慢又容易抄錯——
    第 002 期就是手打 quant 時把 watch 的 trigger id 標成 indicator id。
    """
    h = bub.get("history", [])
    cur = bub.get("dims", {})
    same = sorted([r for r in h if set(r.get("dims", {})) == set(cur)],
                  key=lambda r: r.get("date", ""))
    first = same[0] if same else None
    dm = bub.get("dimMeta", {})
    dims = []
    for k in sorted(cur):
        m = dm.get(k, {})
        dims.append({
            "id": k, "name": m.get("name", ""),
            "w": f"{int(round(float(m.get('w', 0))*100))}%",
            "v": cur[k],
            "delta": round(cur[k] - first["dims"][k], 1) if first else 0.0,
            "note": "（填：這一層本期為什麼動／沒動）",
        })
    qd = bub.get("quadrant") or {}
    st = bub.get("stage") or {}
    lit = [c for c in st.get("checklist", []) if c.get("state")]
    # zones 是依 max 升冪的門檻表（無 lo/hi），取第一個 max ≥ composite 的
    _c = bub.get("composite", 0)
    _zs = [z for z in bub.get("zones", []) if isinstance(z, dict) and "max" in z]
    _zs.sort(key=lambda z: z["max"])
    zone = next((z for z in _zs if _c <= z["max"]), (_zs[-1] if _zs else None))
    _prev_max = None
    for _z in _zs:
        if _z is zone: break
        _prev_max = _z["max"]
    zone_label = (f"{zone['label']}（{(_prev_max or 0)}–{zone['max']}）" if zone
                  else "（填：對照 bub.txt 的 zones）")
    issue_no = prev["issue"] + 1
    _nd = sorted({x[0] for x in (adv_f + pod_f + cotd_f)})
    rng_n = f"{_nd[0][5:].replace('-','/')} – {_nd[-1][5:].replace('-','/')}" if _nd else "—"
    _built = str((bub.get("meta") or {}).get("built") or "")[:10]
    rng_q = (f"{same[0]['date'][5:].replace('-','/')} – {_built[5:].replace('-','/')}"
             if same and _built else "—")
    return {
        "date": str(today), "issue": issue_no,
        "label": f"第 {issue_no:03d} 期 · {today.year} 年 {today.month} 月 {today.day} 日",
        "stamp": "（填：一句話定位本期，例如「四庫比對．第 N 期」）",
        "range": {"quant": rng_q, "narrative": rng_n},
        "headline": "（填：一句話，要有觀點，不是主題標籤）",
        "coverage": [
            {"k": "投顧知識庫", "v": f"{len(adv_f)} 天 / {counts.get('card',0)} 則卡片"},
            {"k": "節目知識庫", "v": f"{len(pod_f)} 天 / {counts.get('ep',0)} 集"},
            {"k": "AI 泡沫監控", "v": f"history {len(h)} 筆 / {len(bub.get('indicators',[]))} 項指標"},
            {"k": "每日五圖", "v": f"{len(cotd_f)} 天 / {counts.get('chart',0)} 張"},
        ],
        "verdict": ["（填：段 1，必須表態）", "（填：段 2，上一期 watch 逐條驗收）",
                    "（填：段 3，本期唯一無可取代的發現）"],
        "quant": {
            "schemaVer": f"v{(bub.get('meta') or {}).get('version', 2)}",
            "composite": bub.get("composite"),
            "zone": zone_label,
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
            for i, t in (("resonance", "一 · 三方共振"), ("divergence", "二 · 關鍵背離"),
                         ("taiwan", "三 · 台股"), ("charts", "四 · 圖表側寫"),
                         ("single", "五 · 單邊訊號"))
        ],
        # ⚠️ 佔位字串裡刻意不寫真的 trigger id、也不放 <code>——
        # 否則 verify.py 第 5.6 項會把佔位當成「提到 trigger 卻標錯」而誤報。
        # 合法 id 清單在 PREP.md 的觸發器表。
        "watch": ["（填：每條可觀察可證偽。能對應觸發器的條目要用行內 code 標出正確的"
                  " trigger id，清單見 PREP.md 觸發器表）"],
        "gaps": ["（填：缺天／各庫 updatedLabel 過期／指標 asof 落後／卡片數異常／圖表庫 qa_flags）"],
        "about": {"run": "（填：本期執行紀錄與樣本厚度）",
                  "method": "prepare.py 備料 → 兩個平行子代理讀敘事側 → 主線併入量化底盤合成 → verify.py 逐字回查"},
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
                sh(f"git clone --depth 1 -q {url} {d}")
            else:
                # 既有 clone 一定要 pull——殘留上週的 work/ 會靜靜地拿舊資料備料
                sh(f"git -C {d} pull -q --ff-only")

    today = dt.datetime.now(zoneinfo.ZoneInfo("Asia/Taipei")).date()
    lo, hi = str(today - dt.timedelta(days=6)), str(today)

    adv_f  = dated_files(os.path.join(W, "adv",  "data"), lo, hi)
    pod_f  = dated_files(os.path.join(W, "pod",  "data"), lo, hi)
    cotd_f = dated_files(os.path.join(W, "cotd", "data"), lo, hi)
    bub    = jload(os.path.join(W, "bub", "data.json"))

    adv_t, ncard, trunc = build_adv(adv_f)
    pod_t, nep, slim = build_pod(pod_f)
    bub_t       = build_bub(bub)
    cotd_t, nch = build_cotd(cotd_f)
    for name, txt in (("adv", adv_t), ("pod", pod_t), ("bub", bub_t), ("cotd", cotd_t)):
        open(os.path.join(W, f"{name}.txt"), "w", encoding="utf-8").write(txt)

    # 上一期資訊（site 的 index.json 與單期檔）
    idx = jload(os.path.join(a.site, "data", "index.json"))
    prev = idx["issues"][0]
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
    lit_n = sum(1 for x in tg if x.get("state"))
    thin = []
    if len(adv_f) <= 3: thin.append(f"投顧僅 {len(adv_f)} 天（≤3，about.run 須註明、共振保守）")
    if len(pod_f) <= 2: thin.append(f"節目僅 {len(pod_f)} 天（≤2，同上）")
    if len(cotd_f) < 3: thin.append(f"圖表僅 {len(cotd_f)} 天（<3，「圖表側寫」只列可用的）")

    md = [f"# PREP · {today}（窗口 {lo} ～ {hi}）\n",
          "## 涵蓋",
          f"- 投顧 {len(adv_f)} 天／{ncard} 卡（body 截斷 {trunc} 字）→ adv.txt {len(adv_t)//1000}K",
          f"- 節目 {len(pod_f)} 天／{nep} 集（summary 截斷 {slim} 字）→ pod.txt {len(pod_t)//1000}K",
          f"- 監控 history {len(bub.get('history',[]))} 筆 → bub.txt {len(bub_t)//1000}K",
          f"- 圖表 {len(cotd_f)} 天／{nch} 張 → cotd.txt {len(cotd_t)//1000}K",
          f"- 各庫最新：{'　'.join(f'{k} {v}' for k,v in latest.items())}",
          f"\n## 上一期：第 {prev['issue']:03d} 期（{prev['date']}）",
          f"- headline：{prev['headline']}",
          f"- errata：{len(prev.get('errata', []))} 條",
          "\n### 上一期 watch（逐條驗收，結果寫進本期 verdict）"]
    md += [f"{i+1}. {w}" for i, w in enumerate(prev_full.get("watch", []))]
    # ── 量化底盤直接內嵌，主線讀 PREP.md 就有全部量化面 ──
    _h = bub.get("history", [])
    _cur = bub.get("dims", {})
    _same = sorted([r for r in _h if set(r.get("dims", {})) == set(_cur)],
                   key=lambda r: r.get("date", ""))
    _first = _same[0] if _same else None
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
    if thin:
        md += ["\n## ⚠️ 樣本偏薄"] + [f"- {t}" for t in thin]
    if not fresh:
        md += ["\n## 🛑 零新增資料",
               f"四庫最新日期皆 ≤ 上一期（{prev['date']}）。依規格 §2.1 **不產期**：",
               "在交付訊息寫明「本次未產期」與各庫實際最新日期，不寫任何檔案。"]
    if a.emit_skeleton:
        sk = build_skeleton(bub, a.site, adv_f, pod_f, cotd_f, prev, today,
                            {"card": ncard, "ep": nep, "chart": nch})
        sp = os.path.join(W, "skeleton.json")
        with open(sp, "w", encoding="utf-8") as f:
            json.dump(sk, f, ensure_ascii=False, indent=1)
        md += [f"\n## 骨架已產出：`{sp}`",
               f"第 {sk['issue']:03d} 期。**`quant` 整區已填好**（composite／zone／stage／twHeat／"
               f"quadrant／{len(sk['quant']['dims'])} 層／{len(sk['quant']['triggers'])} 條 triggers），"
               "`date`／`issue`／`label`／`range`／`coverage` 也已填。",
               "你只要填標「（填：…）」的欄位與 `sections[].items`，**不要重打 `quant`**。"]

    out = "\n".join(md)
    open(os.path.join(W, "PREP.md"), "w", encoding="utf-8").write(out)
    print(out)
    if not fresh: sys.exit(3)

if __name__ == "__main__":
    main()
