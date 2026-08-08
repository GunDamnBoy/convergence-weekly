#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主題匯流訊號報 · 備料（每週排程的第 1–2 步，機械環節全部在這裡）

用法：
    python3 prepare.py [--work work] [--no-clone] [--site /path/to/convergence-weekly]

做的事（全部確定性，不需要模型參與）：
  1. clone 四庫（adv / pod / bub / cotd；--no-clone 可重用既有的 work/）
  2. 依 AGENT_BRIEF.md 第 4 節第 2 步的規格產出四份摘要層：
       work/adv.txt   每卡一行，body 截斷自動調整以落在 40–60K 字
       work/pod.txt   每集三行＋完整 crossCut，目標 12–20K
       work/bub.txt   composite＋三層＋quadrant＋triggers＋22 項指標＋stage＋tw＋events
       work/cotd.txt  每張圖六行（不含 series/option），超過 15K 先截 reading 至 300 字
  3. 寫 work/PREP.md：涵蓋統計、各庫最新日期、上一期資訊與 watch 清單全文、
     triggers 狀態表、樣本偏薄旗標、零新增資料提示、摘要層大小
  4. 印出 PREP.md 到 stdout——排程主線只需要讀這份與摘要層，不必碰任何原始 JSON

exit code：0 正常；3 = 四庫全部沒有比上一期更新的資料（依規格 §2.1 不應產期）
"""
import json, os, sys, re, ast, subprocess, argparse, datetime as dt

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
    """每卡一行；截斷長度自動下調（110→80→60）讓總量落在 60K 內，不減卡片則數。"""
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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="work")
    ap.add_argument("--no-clone", action="store_true")
    ap.add_argument("--site", default=os.path.dirname(os.path.abspath(__file__)))
    a = ap.parse_args()
    W = a.work; os.makedirs(W, exist_ok=True)

    if not a.no_clone:
        for k, url in REPOS.items():
            d = os.path.join(W, k)
            if not os.path.isdir(os.path.join(d, ".git")):
                sh(f"git clone --depth 1 -q {url} {d}")

    today = dt.date.today()
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
        "監控": max((r.get("date","") for r in bub.get("history", [])), default="?"),
        "圖表": cotd_f[-1][0] if cotd_f else "（窗口內無檔）",
    }
    fresh = [k for k, v in latest.items() if v > prev["date"]]
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
    md += [f"\n## 觸發器（{lit_n}/{len(tg)} 已觸發；背離節裁判方法優先引用）"]
    md += [f"- {'●' if x.get('state') else '○'} `{x['id']}` {x.get('name','')}"
           f"｜{x.get('value')}｜asof {x.get('asof')}" for x in tg]
    if thin:
        md += ["\n## ⚠️ 樣本偏薄"] + [f"- {t}" for t in thin]
    if not fresh:
        md += ["\n## 🛑 零新增資料",
               f"四庫最新日期皆 ≤ 上一期（{prev['date']}）。依規格 §2.1 **不產期**：",
               "在交付訊息寫明「本次未產期」與各庫實際最新日期，不寫任何檔案。"]
    out = "\n".join(md)
    open(os.path.join(W, "PREP.md"), "w", encoding="utf-8").write(out)
    print(out)
    if not fresh: sys.exit(3)

if __name__ == "__main__":
    main()
