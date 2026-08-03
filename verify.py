#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主題匯流訊號報 · 發布前檢查

用法：
    python3 verify.py data/2026-08-03.json --adv /path/adv.txt --pod /path/pod.txt --bub /path/bub/data.json

檢查四件事：
 1. 單期 JSON 與 index.json 可解析、必備欄位齊全
 2. index.json 帶有本期的量化快照（跨期趨勢圖的唯一資料來源，漏了圖會斷）
 3. 敘事側每一條 evidence 都能在 adv.txt / pod.txt 裡逐字回查到
 4. 量化側每一條 evidence 引用的指標 id 確實存在於 bub 的 indicators / tw / stage
    （並提醒：量化佐證不得取自 events——那是 Google News，會造成同一則新聞被數兩次）

任何一項 FAIL 就不要發布。
"""
import json, re, html, sys, os, argparse

def clean(s):
    return re.sub(r'<[^>]+>', '', html.unescape(str(s))).strip()

def core_clause(text):
    """把來源標籤剝掉，取出真正該逐字回查的那一段。

    '當日交叉觀察，引 The Market Huddle｜Paul Krake：他點名若有公司率先承認…'
      → 取最後一個 ｜ 之後 → 再切標點 → '他點名若有公司率先承認…'
    """
    t = clean(text)
    t = t.split('｜')[-1]
    t = re.sub(r'^\([^)]*\)\s*', '', t)          # 去掉 (ft/AI 信用) 這種前綴
    parts = re.split(r'[（）()【】「」，、,：:；;。]', t)
    parts = [p.strip() for p in parts if len(p.strip()) >= 8]
    return max(parts, key=len) if parts else t

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('issue')
    ap.add_argument('--adv'); ap.add_argument('--pod'); ap.add_argument('--bub')
    ap.add_argument('--index', default=None)
    a = ap.parse_args()

    fails, warns = [], []
    d = json.load(open(a.issue, encoding='utf-8'))
    idx_path = a.index or os.path.join(os.path.dirname(a.issue), 'index.json')
    idx = json.load(open(idx_path, encoding='utf-8'))
    print(f"[ok ] JSON 解析：{a.issue} · {idx_path}")

    # --- 1. 必備欄位 ---
    for k in ('date','issue','label','range','headline','coverage','verdict',
              'quant','sections','watch','gaps','about'):
        if k not in d: fails.append(f"單期 JSON 缺欄位 {k}")
    q = d.get('quant', {})
    for k in ('composite','zone','stage','twHeat','dims'):
        if k not in q: fails.append(f"quant 缺欄位 {k}")
    if len(q.get('dims', [])) != 6: fails.append("quant.dims 應為 6 維")
    print(f"[{'ok ' if not fails else 'FAIL'}] 必備欄位")

    # --- 2. index 快照 ---
    me = next((i for i in idx.get('issues', []) if i['date'] == d['date']), None)
    if not me:
        fails.append("index.json 沒有本期")
    else:
        for k in ('composite','dims','twHeat','stage','file','issue','short','headline'):
            if k not in me: fails.append(f"index 本期缺 {k}（跨期趨勢圖會斷）")
        if set(me.get('dims', {})) != {'D1','D2','D3','D4','D5','D6'}:
            fails.append("index 本期 dims 不完整（跨期趨勢圖會斷）")
    print(f"[{'ok ' if me else 'FAIL'}] index.json 量化快照")

    # --- 3. 敘事側逐字回查 ---
    corpus = ''
    for p in (a.adv, a.pod):
        if p and os.path.exists(p): corpus += open(p, encoding='utf-8').read()
    ev = [(it, e) for s in d['sections'] for it in s['items'] for e in it.get('evidence', [])]
    narr = [e for _, e in ev if e.get('s') != '監控']
    if not corpus:
        warns.append("未提供 --adv/--pod，跳過敘事側回查")
    else:
        bad = []
        for e in narr:
            frag = core_clause(e['t'])
            if len(frag) >= 8 and frag not in corpus:
                bad.append(f"{e['d']} {e.get('s')}｜{frag[:48]}")
        if bad: fails.append(f"敘事側 {len(bad)} 條佐證無法逐字回查")
        print(f"[{'ok ' if not bad else 'FAIL'}] 敘事側佐證回查：{len(narr)} 條，失敗 {len(bad)}")
        for b in bad: print("        ✗", b)

    # --- 4. 量化側指標存在性 ---
    quant_ev = [e for _, e in ev if e.get('s') == '監控']
    if not (a.bub and os.path.exists(a.bub)):
        warns.append("未提供 --bub，跳過量化側檢查")
    else:
        b = json.load(open(a.bub, encoding='utf-8'))
        ids = {i['id'] for i in b['indicators']} | {i['id'] for i in b['tw']['items']}
        evt_titles = ' '.join(e['t'] for e in b.get('events', []))
        bad = []
        for e in quant_ev:
            used = set(re.findall(r'<code>([a-z0-9_]+)</code>', e['t']))
            unknown = used - ids
            if unknown: bad.append(f"{e['d']}｜未知指標 id {sorted(unknown)}")
        if bad: fails.append(f"量化側 {len(bad)} 條引用了不存在的指標 id")
        print(f"[{'ok ' if not bad else 'FAIL'}] 量化側指標存在性：{len(quant_ev)} 條，失敗 {len(bad)}")
        for x in bad: print("        ✗", x)

        # 六維現值與變動 vs history
        h = b.get('history', [])
        if h:
            first = h[0]
            for dim in q['dims']:
                cur = b['dims'][dim['id']]
                delta = round(cur - first['dims'][dim['id']], 1)
                if abs(dim['v'] - cur) > .05:
                    fails.append(f"{dim['id']} 現值 {dim['v']} ≠ 監控 {cur}")
                if abs(dim['delta'] - delta) > .05:
                    fails.append(f"{dim['id']} 變動 {dim['delta']} ≠ 實算 {delta}")
            print(f"[{'ok ' if not fails else 'FAIL'}] 六維現值與變動 vs history（基準 {first['date']}）")

        # 提醒：量化佐證不得出自 events
        for e in quant_ev:
            frag = core_clause(e['t'])
            if len(frag) >= 10 and frag in evt_titles:
                warns.append(f"{e['d']} 的量化佐證疑似取自 events（Google News），"
                             f"這會讓同一則新聞被當成兩個獨立來源")

    print()
    for w in warns: print("[warn]", w)
    if fails:
        print(f"\n❌ FAILED（{len(fails)}）")
        for f in fails: print("   -", f)
        sys.exit(1)
    print("\n✅ 全部通過，可以發布")

if __name__ == '__main__':
    main()
