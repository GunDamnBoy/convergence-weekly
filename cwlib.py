#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主題匯流訊號報 · 共用函式

這些邏輯曾經在 prepare.py／verify.py／make_index.py 各寫一份（「同架構最早一筆」
寫了四遍、「是不是 v2」有五種寫法），任何規則調整都會有一份忘了改，
而症狀是數字不一致、不是 crash。v1.0 起集中在這裡，**規則只改這一份**。

它在「一組要一起改」的清單裡（見 AGENT_BRIEF.md 第 3.0 節末）。
"""
import json


def need(obj, path, ctx=""):
    """安全取巢狀欄位。缺欄位時給「上游改版了」等級的可行動錯誤，不是裸 KeyError。

    path 用點分隔，例如 need(bub, "tw.items", "監控庫")。
    """
    cur = obj
    for i, k in enumerate(path.split(".")):
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            raise SystemExit(
                f"❌ {ctx or '資料'}缺少欄位 `{'.'.join(path.split('.')[:i+1])}`——"
                f"上游可能改版了。先確認該庫的 schema，再依 CHANGELOG 的失效模式 3.4 處理。")
    return cur


def baseline(bub):
    """「本期變動」的基準：history 中與現值同一組 dims 鍵的**最早一筆**。

    監控庫 2026-08-04 由六維改三層後，history 舊筆仍是 D 鍵——
    跨架構相減就是拿三層去減六維。顯式依日期排序，不倚賴陣列順序。
    回傳 (first_row_or_None, same_arch_rows)。
    """
    h = bub.get("history", []) or []
    cur_keys = set(bub.get("dims", {}) or {})
    same = sorted((r for r in h if set(r.get("dims", {}) or {}) == cur_keys),
                  key=lambda r: r.get("date", ""))
    return (same[0] if same else None), same


def dim_ids(bub_or_quant):
    """現行維度／層 id 的唯一真相來源。

    吃監控庫原始 data.json（dims 是 dict）或單期 quant（dims 是 list）都行。
    不要再硬編 ['L1','L2','L3']——v3 上線那天硬編碼會全面誤判（六維改三層已發生過一次）。
    """
    d = bub_or_quant.get("dims")
    if isinstance(d, dict):
        return sorted(d.keys())
    if isinstance(d, list):
        return [x.get("id") for x in d]
    return []


def schema_ver(quant_or_bub):
    """架構版本字串。優先讀明寫的 schemaVer / meta.version，最後才用維度數推測。"""
    sv = quant_or_bub.get("schemaVer")
    if sv:
        return str(sv)
    mv = (quant_or_bub.get("meta") or {}).get("version")
    if mv:
        return f"v{mv}"
    n = len(dim_ids(quant_or_bub))
    return {6: "v1", 3: "v2"}.get(n, f"v?（{n} 維，無明寫版本——上游可能改版了）")


def is_lit(trigger):
    """trigger 是否已觸發。統一真值定義：state 只認 0/1（或可轉 int 的等價值）。

    上游把 state 寫成字串 "0" 之類的型別漂移，在這裡直接炸出可行動訊息，
    不要讓 truthiness 與 int() 兩套邏輯各自解讀。
    """
    s = trigger.get("state")
    try:
        v = int(s)
    except (TypeError, ValueError):
        raise SystemExit(f"❌ trigger `{trigger.get('id')}` 的 state 是 {s!r}，"
                         f"不是 0/1——監控庫的型別可能變了。")
    if v not in (0, 1):
        raise SystemExit(f"❌ trigger `{trigger.get('id')}` 的 state={v}，超出 0/1。")
    return v == 1


def zone_label(bub):
    """依 zones 門檻表（max 升冪）把 composite 換成「標籤（lo–hi）」字串。"""
    c = bub.get("composite", 0)
    zs = sorted((z for z in bub.get("zones", []) if isinstance(z, dict) and "max" in z),
                key=lambda z: z["max"])
    if not zs:
        return None
    zone = next((z for z in zs if c <= z["max"]), zs[-1])
    prev_max = 0
    for z in zs:
        if z is zone:
            break
        prev_max = z["max"]
    return f"{zone.get('label','')}（{prev_max}–{zone['max']}）"


def upstream_fingerprint(bub):
    """監控庫的七項指紋。取「意義會變」的東西，不是只取欄位名。

    重要性排序（見 CHANGELOG 失效模式 3.4 的分析）：
    dims 鍵（上次出事的就是它）→ 權重（最無聲的改版：欄位全不變、composite 意義已變）
    → triggers 的 id+name 全文（name 藏著門檻數字）→ indicators id → tw id
    → stage checklist 全文（lit 的分母靠它）→ zones 門檻表。
    """
    dm = bub.get("dimMeta", {}) or {}
    return {
        "dims": dim_ids(bub),
        "weights": {k: (dm.get(k) or {}).get("w") for k in dim_ids(bub)},
        "triggers": [{"id": t.get("id"), "name": t.get("name")}
                     for t in bub.get("triggers", []) or []],
        "indicators": sorted(i.get("id") for i in bub.get("indicators", []) or []),
        "tw_items": sorted(i.get("id") for i in (bub.get("tw") or {}).get("items", []) or []),
        "checklist": [c.get("item") for c in (bub.get("stage") or {}).get("checklist", []) or []],
        "zones": [{"max": z.get("max"), "label": z.get("label")}
                  for z in bub.get("zones", []) or []],
        "meta_version": (bub.get("meta") or {}).get("version"),
    }


def diff_fingerprint(old, new):
    """兩份指紋的明文差異清單（人讀得懂的句子，直接可寫進 PREP.md / gaps）。"""
    out = []
    if not old:
        return out
    if old.get("dims") != new.get("dims"):
        out.append(f"維度／層由 {old.get('dims')} 變為 {new.get('dims')}——**架構改版，不可跨期相減**")
    for k in new.get("weights", {}):
        ow, nw = (old.get("weights") or {}).get(k), new["weights"][k]
        if ow is not None and ow != nw:
            out.append(f"權重變更：{k} 由 {ow} 變為 {nw}——composite 的意義已不同")
    ot = {t["id"]: t.get("name") for t in old.get("triggers", [])}
    nt = {t["id"]: t.get("name") for t in new.get("triggers", [])}
    for i in sorted(set(nt) - set(ot)):
        out.append(f"新增 trigger `{i}`：{nt[i]}")
    for i in sorted(set(ot) - set(nt)):
        out.append(f"移除 trigger `{i}`（舊 watch 引用它的條目下期無法驗收）")
    for i in sorted(set(ot) & set(nt)):
        if ot[i] != nt[i]:
            out.append(f"trigger `{i}` 的定義由「{ot[i]}」變為「{nt[i]}」——門檻可能變了")
    for key, label in (("indicators", "指標"), ("tw_items", "台股項目")):
        o, n = set(old.get(key, [])), set(new.get(key, []))
        if o - n:
            out.append(f"移除{label} id：{sorted(o - n)}")
        if n - o:
            out.append(f"新增{label} id：{sorted(n - o)}")
    if old.get("checklist") != new.get("checklist"):
        out.append(f"stage checklist 由 {len(old.get('checklist', []))} 項變為 "
                   f"{len(new.get('checklist', []))} 項或文字有改——`lit` 的分母與跨期比較會受影響")
    if old.get("zones") != new.get("zones"):
        out.append("zones 門檻表變更——`zone` 標籤與分數的對應已不同")
    return out


def atomic_write_json(path, obj):
    """先寫 tmp 再 os.replace——dashpush 每 180 秒 commit，非原子寫入撞上會推出截斷的檔。"""
    import os, io
    tmp = str(path) + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
