#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主題匯流訊號報 · 發布前檢查

用法：
    python3 verify.py data/2026-08-03.json --adv /path/adv.txt --pod /path/pod.txt \
        --cotd /path/cotd.txt --bub /path/bub/data.json

檢查十件事：
 1. 單期 JSON 與 index.json 可解析、必備欄位齊全、章節 id 與順序合規
 2. index.json 帶有本期的量化快照（跨期趨勢圖的唯一資料來源，漏了圖會斷）
 3. 敘事側每一條 evidence 都能在 adv.txt / pod.txt / cotd.txt 裡逐字回查到
    （含 list[] 的條目——單邊訊號整節用 list 而非 evidence，一樣要逐字）
 3.4 evidence[].s 只能是 監控／投顧／節目／圖表 四者之一。
    打錯字會讓計票靜靜少一票，而錯誤訊息還會誤導成「來源不夠獨立」，所以先擋下來。
 3.5 標為「共振」的 item 真的有三個獨立來源。
    **投顧與圖表計為同一票**——每日五圖的選題取自 advisory-knowledge-hub，
    「投顧在講＋圖表也在畫」是同一則新聞被數兩次，不是兩個獨立來源。
 4. 量化側每一條 evidence 引用的指標 id 確實存在於 bub 的 indicators / tw / stage
 5. 層／維現值與變動 vs history（變動＝現值 − **同架構最早一筆**，不跨改版相減）
 5.5 觸發器對帳：quant.triggers 的 id 與 state 必須與監控庫一致，
    index.json 的 trigLit（已觸發數）也要對得上。
 5.6 watch[] 的 trigger 綁定：提到 trigger 名稱就必須用 <code>正確 id</code> 標，
    否則下期無法自動驗收 state 翻轉（v0.6 接 triggers 的全部意義就在這）。
 6. 量化佐證不得取自 events——那是 Google News，會造成同一則新聞被數兩次。
    這一項是 FAIL，不是 warn。

注意 --bub 吃的是**原始 bub/data.json**，不是壓縮過的 bub.txt。
--cotd 則是壓縮過的 cotd.txt（敘事回查用）。

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
    ap.add_argument('--cotd', help='每日五圖的摘要層 cotd.txt（敘事回查用）')
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
    for k in ('composite','zone','note','stage','twHeat','dims'):
        if k not in q: fails.append(f"quant 缺欄位 {k}")
    # 監控庫 2026-08-04 由 v1（六維 D1–D6）改版為 v2（三層 L1–L3）。
    # 兩種分群不可換算，所以這裡依版本各驗各的，不做轉換。
    v2 = q.get('schemaVer') == 'v2' or (not q.get('schemaVer') and len(q.get('dims', [])) == 3)
    want_ids = ['L1','L2','L3'] if v2 else ['D1','D2','D3','D4','D5','D6']
    got_ids = [x.get('id') for x in q.get('dims', [])]
    if got_ids != want_ids:
        fails.append(f"quant.dims 的 id 與順序應為 {want_ids}（{'v2 三層' if v2 else 'v1 六維'}），實際 {got_ids}")
    if v2:
        if 'schemaVer' not in q:
            fails.append("v2 的 quant 必須明寫 schemaVer:'v2'——少了它，之後沒人分得出斷點在哪")
        qd = q.get('quadrant')
        if not isinstance(qd, dict) or not {'heat','support','regime'} <= set(qd):
            fails.append("v2 的 quant 缺 quadrant{heat,support,regime}")
        tg = q.get('triggers')
        if not isinstance(tg, list) or not tg:
            fails.append("v2 的 quant 缺 triggers[]——背離節的裁判方法要優先引用它，"
                         "上一期 watch 的驗收也靠它")
        else:
            for x in tg:
                if not {'id','name','state'} <= set(x):
                    fails.append(f"triggers 條目缺 id/name/state：{x}")
    # 章節：v0.5 起加入「圖表側寫」成為 5 節；第 001 期是 4 節，兩者都要能過。
    # 外殼的尾段編號已改為依 sections 長度動態計算，所以這裡只驗 id 與順序。
    CANON = ['resonance', 'divergence', 'taiwan', 'charts', 'single']
    LEGACY = ['resonance', 'divergence', 'taiwan', 'single']
    sec_ids = [s.get('id') for s in d.get('sections', [])]
    if sec_ids not in (CANON, LEGACY):
        fails.append(f"sections 的 id 與順序不合規：{sec_ids}\n"
                     f"          應為 {CANON}（v0.5 起）或 {LEGACY}（v0.4 以前的舊期）")
    n_field = len(fails)
    print(f"[{'ok ' if not n_field else 'FAIL'}] 必備欄位與章節結構（{len(sec_ids)} 節）")

    # --- 2. index 快照 ---
    n0 = len(fails)
    me = next((i for i in idx.get('issues', []) if i['date'] == d['date']), None)
    if not me:
        fails.append("index.json 沒有本期")
    else:
        need = ['composite','dims','twHeat','stage','file','issue','label','short','headline']
        if v2: need += ['quantVer','quadrant','trigLit']
        for k in need:
            if k not in me: fails.append(f"index 本期缺 {k}（跨期趨勢圖會斷）")
        if set(me.get('dims', {})) != set(want_ids):
            fails.append(f"index 本期 dims 應為 {want_ids}（跨期趨勢圖會斷）")
        if v2 and me.get('quantVer') != 'v2':
            fails.append("index 本期的 quantVer 應為 'v2'——外殼靠它決定哪幾期能連成一條線")
    print(f"[{'ok ' if len(fails) == n0 else 'FAIL'}] index.json 量化快照")

    # --- 3. 敘事側逐字回查 ---
    # 三份敘事摘要層要分別檢查有沒有給。只給其中一兩份時，缺的那庫的佐證
    # 會全部「查不到」而變成假 FAIL——那是參數沒給，不是引用錯了。
    corpus = ''
    missing_src = []
    for label, p in (('--adv', a.adv), ('--pod', a.pod), ('--cotd', a.cotd)):
        if p and os.path.exists(p): corpus += open(p, encoding='utf-8').read()
        else: missing_src.append(label)
    ev = [(it, e) for s in d['sections'] for it in s['items'] for e in it.get('evidence', [])]
    narr = [e for _, e in ev if e.get('s') != '監控']
    # 單邊訊號整節用 list[] 而非 evidence[]，但「佐證一律逐字」是無條件的規則，
    # 所以 list 也要回查。src 裡有「監控」的視為量化側，不做 substring。
    lst = [l for s in d['sections'] for it in s['items'] for l in it.get('list', [])]
    lst_narr = [l for l in lst if '監控' not in str(l.get('src', ''))]
    if missing_src:
        warns.append(f"未提供 {'／'.join(missing_src)}，跳過敘事側回查——"
                     f"部分給定會讓缺的那庫全部假 FAIL，所以缺一個就整批跳過")
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

    # --- 3.5 來源獨立性：圖表庫與投顧庫不是兩票 ---
    # 每日五圖的選題取自 advisory-knowledge-hub（見它自己的 about.upstream），
    # 所以「投顧在講 ＋ 圖表也在畫」不構成兩個獨立來源——那是同一則新聞被數兩次。
    # 這是 events 那條禁令的同型問題，只是換了層皮。
    VOICE = {'投顧': 'narrative_adv', '圖表': 'narrative_adv',   # ← 同一票，故意的
             '節目': 'narrative_pod', '監控': 'quant'}
    # s 打錯字（例如「圖表庫」）會讓 VOICE.get() 回 None 而靜靜地少一票，
    # 錯誤訊息還會誤導成「來源不夠獨立」。先把非法值擋下來。
    bad_s = sorted(str(e.get('s')) for _, e in ev if e.get('s') not in VOICE)
    bad_s = sorted(set(bad_s))
    if bad_s:
        fails.append(f"evidence[].s 有非法值 {bad_s}——合法值只有 {sorted(VOICE)}")
    bad_res = []
    for s in d['sections']:
        if s.get('id') != 'resonance': continue
        for it in s['items']:
            tags = ' '.join(t.get('t', '') for t in it.get('tags', []))
            if '共振' not in tags: continue
            voices = {VOICE.get(e.get('s')) for e in it.get('evidence', [])} - {None}
            if len(voices) < 3:
                srcs = sorted({e.get('s') for e in it.get('evidence', [])} - {None})
                bad_res.append(f"{it.get('title','(無標題)')[:36]}｜佐證來源 {srcs} "
                               f"→ 只有 {len(voices)} 個獨立聲音")
    if bad_res:
        fails.append(f"{len(bad_res)} 條標為「共振」的 item 其實不到三個獨立來源")
    print(f"[{'ok ' if not bad_res else 'FAIL'}] 共振的來源獨立性（投顧與圖表計為同一票）")
    for x in bad_res: print("        ✗", x)

    # --- 4. 量化側指標存在性 ---
    quant_ev = [e for _, e in ev if e.get('s') == '監控']
    if not (a.bub and os.path.exists(a.bub)):
        warns.append("未提供 --bub，跳過量化側檢查")
        skipped.append("量化側存在性／層維變動／events 檢查")
    else:
        b = json.load(open(a.bub, encoding='utf-8'))
        # 合法的量化欄位名＝指標 id（動態讀，v2 為 22 項）＋ 台股項目 id
        # ＋ 頂層量化欄位。維度 id 兩代並存：v1 的 d1–d6 與 v2 的 l1–l3 都算數，
        # 因為舊期引用 d4、新期引用 l2 都是對的。
        ids = ({i['id'] for i in b['indicators']}
               | {i['id'] for i in b['tw']['items']}
               | {'stage', 'composite', 'twheat', 'quadrant', 'heat', 'support'}
               | {f'd{n}' for n in range(1, 7)}
               | {f'l{n}' for n in range(1, 4)})
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

        # 層／維現值與變動 vs history（變動＝現值 − 基準筆）
        # 監控庫改版當天之前的 history 舊筆還是 v1 的 D1–D6 鍵（那邊刻意不回頭改寫），
        # 所以基準只能取「與現值同一組鍵」的最早一筆，否則就是拿三層去減六維。
        h = b.get('history', [])
        cur_keys = set(b.get('dims', {}))
        # 顯式依日期排序，不倚賴監控庫的陣列順序——它哪天改成降冪，
        # 這裡會靜靜地拿到最新一筆當基準，而且不會報錯。
        same = sorted([r for r in h if set(r.get('dims', {})) == cur_keys],
                      key=lambda r: r.get('date', ''))
        if not cur_keys:
            fails.append("監控庫的頂層 dims 是空的，無法核對")
        elif not same:
            warns.append("history 裡沒有與現值同架構的紀錄（監控庫剛改版？），跳過變動核對")
            skipped.append("層／維變動 vs history")
        elif set(x['id'] for x in q['dims']) != cur_keys:
            # 本期的架構與眼前這份監控資料不同。兩種可能，訊息要同時涵蓋：
            #   (a) 正在發的新一期用錯了架構 → 這是真錯，必須擋下
            #   (b) 拿舊期回頭驗今天的資料 → 工具用錯了，舊期在當時是對的
            fails.append(
                f"本期的量化架構是 {sorted(set(x['id'] for x in q['dims']))}，"
                f"但 --bub 這份監控資料是 {sorted(cur_keys)}。\n"
                f"          若你正在發新一期：改用監控庫現行架構重寫 quant.dims。\n"
                f"          若你是拿舊期回頭驗今天的資料：那一期在發布當時是對的，"
                f"verify.py 是發布前檢查，不適合這樣用。")
            print("[FAIL] 層／維現值與變動 vs history（架構不符，見下方說明）")
        else:
            n1 = len(fails)
            first = same[0]
            if len(same) < len(h):
                warns.append(f"history 共 {len(h)} 筆，其中僅 {len(same)} 筆與現值同架構；"
                             f"變動以 {first['date']} 為基準，不跨改版計算")
            for dim in q['dims']:
                cur = b['dims'][dim['id']]
                delta = round(cur - first['dims'][dim['id']], 1)
                if abs(dim['v'] - cur) > .05:
                    fails.append(f"{dim['id']} 現值 {dim['v']} ≠ 監控 {cur}")
                if abs(dim['delta'] - delta) > .05:
                    fails.append(f"{dim['id']} 變動 {dim['delta']} ≠ 實算 {delta}")
            print(f"[{'ok ' if len(fails) == n1 else 'FAIL'}] "
                  f"層／維現值與變動 vs history（基準 {first['date']}，同架構 {len(same)} 筆）")

        # 觸發器：id 必須存在於監控庫，state 與 index 的 trigLit 要對得上
        bt = b.get('triggers', [])
        if q.get('triggers') and bt:
            n2 = len(fails)
            bmap = {x['id']: x for x in bt}
            for x in q['triggers']:
                if x['id'] not in bmap:
                    fails.append(f"triggers 的 {x['id']} 不存在於監控庫")
                elif int(x.get('state', 0)) != int(bmap[x['id']].get('state', 0)):
                    fails.append(f"triggers 的 {x['id']} state={x.get('state')} "
                                 f"≠ 監控庫 {bmap[x['id']].get('state')}")
            lit = sum(1 for x in q['triggers'] if x.get('state'))
            if me and me.get('trigLit') is not None and int(me['trigLit']) != lit:
                fails.append(f"index 本期 trigLit={me['trigLit']} ≠ 實際已觸發數 {lit}")
            print(f"[{'ok ' if len(fails) == n2 else 'FAIL'}] "
                  f"觸發器對帳（{lit}/{len(q['triggers'])} 已觸發）")

        # watch[] 的 trigger 綁定：提到 trigger 名稱就必須用 <code>正確 id</code> 標。
        # v0.6 接 triggers 的全部意義是「下期驗收直接查 state 翻轉」——
        # id 標錯或漏標，那個自動化就不存在。第 002 期 7 條裡有 4 條是壞的。
        n_w = len(fails)
        tids = {x["id"] for x in bt}
        bad_w = []
        for w in d.get("watch", []):
            plain = clean(w)
            named = sorted(i for i in tids if i in plain)      # 該條提到的 trigger id
            if not named: continue                             # 沒提到 trigger 就不管
            tagged = set(re.findall(r"<code>([a-z0-9_]+)</code>", str(w)))
            hit = sorted(set(named) & tagged)
            if hit: continue                                   # 至少正確標了一個就放行
            wrong = sorted(x for x in tagged if x not in tids)
            why = (f"標成 {wrong}（那不是 trigger id）" if wrong else "完全沒用 <code> 標")
            bad_w.append(f"該條講 {named} 但{why}：{plain[:42]}")
        if bad_w:
            fails.append(f"watch 有 {len(bad_w)} 條的 trigger 綁定壞掉——下期無法自動驗收 state")
        if bt:
            print(f"[{'ok ' if len(fails) == n_w else 'FAIL'}] "
                  f"watch 的 trigger 綁定（{len(d.get('watch', []))} 條）")
            for x in bad_w: print("        ✗", x)

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
