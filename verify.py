#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主題匯流訊號報 · 發布前檢查

用法：
    python3 verify.py data/2026-08-03.json --adv /path/adv.txt --pod /path/pod.txt --bub /path/bub/data.json

檢查六件事：
 1. 單期 JSON 與 index.json 可解析、必備欄位齊全
 2. index.json 帶有本期的量化快照（跨期趨勢圖的唯一資料來源，漏了圖會斷）
 3. 敘事側每一條 evidence 都能在 adv.txt / pod.txt 裡逐字回查到
    （含 list[] 的條目——單邊訊號整節用 list 而非 evidence，一樣要逐字）
 4. 量化側每一條 evidence 引用的指標 id 確實存在於 bub 的 indicators / tw / stage
 5. 六維現值與變動 vs history（變動＝現值 − history 第一筆）
 6. 量化佐證不得取自 events——那是 Google News，會造成同一則新聞被數兩次，
    「三方共振」就會是假的。這一項是 FAIL，不是 warn。

注意 --bub 吃的是**原始 bub/data.json**，不是壓縮過的 bub.txt。

任何一項 FAIL 就不要發布。本檔是發布前檢查，跑在寫檔之後、推送之前。
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

    fails, warns, skipped = [], [], []
    d = json.load(open(a.issue, encoding='utf-8'))
    idx_path = a.index or os.path.join(os.path.dirname(a.issue), 'index.json')
    idx = json.load(open(idx_path, encoding='utf-8'))
    print(f"[ok ] JSON 解析：{a.issue} · {idx_path}")

    # --- 1. 必備欄位 ---
    for k in ('date','issue','label','stamp','range','headline','coverage','verdict',
              'quant','sections','watch','gaps','about'):
        if k not in d: fails.append(f"單期 JSON 缺欄位 {k}")
    q = d.get('quant', {})
    for k in ('composite','zone','stage','twHeat','dims'):
        if k not in q: fails.append(f"quant 缺欄位 {k}")
    if len(q.get('dims', [])) != 6: fails.append("quant.dims 應為 6 維")
    # 外殼寫死「零／五／六」，中間交給 sections，因此必須恰為 4 節
    if len(d.get('sections', [])) != 4:
        fails.append(f"sections 應為 4 節（實際 {len(d.get('sections', []))}）——"
                     f"外殼的章節編號假設會被打破")
    n_field = len(fails)
    print(f"[{'ok ' if not n_field else 'FAIL'}] 必備欄位與章節數")

    # --- 2. index 快照 ---
    n0 = len(fails)
    me = next((i for i in idx.get('issues', []) if i['date'] == d['date']), None)
    if not me:
        fails.append("index.json 沒有本期")
    else:
        for k in ('composite','dims','twHeat','stage','file','issue','label','short','headline'):
            if k not in me: fails.append(f"index 本期缺 {k}（跨期趨勢圖會斷）")
        if set(me.get('dims', {})) != {'D1','D2','D3','D4','D5','D6'}:
            fails.append("index 本期 dims 不完整（跨期趨勢圖會斷）")
    print(f"[{'ok ' if len(fails) == n0 else 'FAIL'}] index.json 量化快照")

    # --- 3. 敘事側逐字回查 ---
    corpus = ''
    for p in (a.adv, a.pod):
        if p and os.path.exists(p): corpus += open(p, encoding='utf-8').read()
    ev = [(it, e) for s in d['sections'] for it in s['items'] for e in it.get('evidence', [])]
    narr = [e for _, e in ev if e.get('s') != '監控']
    # 單邊訊號整節用 list[] 而非 evidence[]，但「佐證一律逐字」是無條件的規則，
    # 所以 list 也要回查。src 裡有「監控」的視為量化側，不做 substring。
    lst = [l for s in d['sections'] for it in s['items'] for l in it.get('list', [])]
    lst_narr = [l for l in lst if '監控' not in str(l.get('src', ''))]
    if not corpus:
        warns.append("未提供 --adv/--pod，跳過敘事側回查")
        skipped.append("敘事側逐字回查")
    else:
        bad = []
        for e in narr:
            frag = core_clause(e['t'])
            if len(frag) >= 8 and frag not in corpus:
                bad.append(f"evidence {e['d']} {e.get('s')}｜{frag[:48]}")
        for l in lst_narr:
            frag = core_clause(l.get('body', ''))
            if len(frag) >= 8 and frag not in corpus:
                bad.append(f"list {l.get('src','')[:16]}｜{frag[:48]}")
        n = len(narr) + len(lst_narr)
        if bad: fails.append(f"敘事側 {len(bad)} 條佐證無法逐字回查")
        print(f"[{'ok ' if not bad else 'FAIL'}] 敘事側佐證回查："
              f"{n} 條（evidence {len(narr)}＋list {len(lst_narr)}），失敗 {len(bad)}")
        for b in bad: print("        ✗", b)

    # --- 4. 量化側指標存在性 ---
    quant_ev = [e for _, e in ev if e.get('s') == '監控']
    if not (a.bub and os.path.exists(a.bub)):
        warns.append("未提供 --bub，跳過量化側檢查")
        skipped.append("量化側存在性／六維變動／events 檢查")
    else:
        b = json.load(open(a.bub, encoding='utf-8'))
        # 合法的量化欄位名＝21 項指標 id ＋ 台股項目 id ＋ 頂層量化欄位（stage / composite
        # / twheat / 六維 id）。docstring 一直說 stage 算數，舊實作漏掉了。
        ids = ({i['id'] for i in b['indicators']}
               | {i['id'] for i in b['tw']['items']}
               | {'stage', 'composite', 'twheat'}
               | {f'd{n}' for n in range(1, 7)})
        evt_titles = ' '.join(e['t'] for e in b.get('events', []))
        bad, no_code = [], 0
        for e in quant_ev:
            used = set(re.findall(r'<code>([a-z0-9_]+)</code>', e['t']))
            if not used: no_code += 1
            unknown = used - ids
            if unknown: bad.append(f"{e['d']}｜未知指標 id {sorted(unknown)}")
        if bad: fails.append(f"量化側 {len(bad)} 條引用了不存在的指標 id")
        if no_code:
            warns.append(f"量化側有 {no_code} 條佐證沒有用 <code>指標id</code> 包住欄位名，"
                         f"這幾條的存在性檢查形同空轉（規格：量化佐證要附欄位名）")
        print(f"[{'ok ' if not bad else 'FAIL'}] 量化側指標存在性：{len(quant_ev)} 條，失敗 {len(bad)}")
        for x in bad: print("        ✗", x)

        # 六維現值與變動 vs history（變動＝現值 − history 第一筆）
        h = b.get('history', [])
        if h:
            n1 = len(fails)
            first = h[0]
            for dim in q['dims']:
                cur = b['dims'][dim['id']]
                delta = round(cur - first['dims'][dim['id']], 1)
                if abs(dim['v'] - cur) > .05:
                    fails.append(f"{dim['id']} 現值 {dim['v']} ≠ 監控 {cur}")
                if abs(dim['delta'] - delta) > .05:
                    fails.append(f"{dim['id']} 變動 {dim['delta']} ≠ 實算 {delta}")
            print(f"[{'ok ' if len(fails) == n1 else 'FAIL'}] "
                  f"六維現值與變動 vs history（基準 {first['date']}）")

        # 量化佐證不得出自 events：那是 Google News，用它會讓同一則新聞
        # 被當成兩個獨立來源，「三方共振」就是假的。這是 FAIL，不是 warn。
        evt_bad = []
        for e in quant_ev:
            frag = core_clause(e['t'])
            if len(frag) >= 10 and frag in evt_titles:
                evt_bad.append(f"{e['d']}｜{frag[:48]}")
        for l in lst:
            if '監控' not in str(l.get('src', '')): continue
            frag = core_clause(l.get('body', ''))
            if len(frag) >= 10 and frag in evt_titles:
                evt_bad.append(f"list {l.get('src','')[:16]}｜{frag[:48]}")
        if evt_bad:
            fails.append(f"{len(evt_bad)} 條量化佐證取自 events（Google News）——"
                         f"同一則新聞被當成兩個獨立來源，共振是假的")
        print(f"[{'ok ' if not evt_bad else 'FAIL'}] 量化佐證未取自 events")
        for x in evt_bad: print("        ✗", x)

    print()
    for w in warns: print("[warn]", w)
    if fails:
        print(f"\n❌ FAILED（{len(fails)}）")
        for f in fails: print("   -", f)
        sys.exit(1)
    # 缺參數會讓整批檢查被跳過，而跳過不算 FAIL——
    # 「沒有 FAIL」不等於「檢查有跑」，所以這裡不給綠燈。
    if skipped:
        print(f"\n⚠️  沒有 FAIL，但有 {len(skipped)} 批檢查被跳過：{'、'.join(skipped)}")
        print("    這不是通過。補上缺的參數重跑後才能發布。")
        sys.exit(2)
    print("\n✅ 全部通過，可以發布")

if __name__ == '__main__':
    main()
