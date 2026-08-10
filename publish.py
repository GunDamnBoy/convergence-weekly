#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主題匯流訊號報 · 發布閘門（v1.0 起唯一的發布路徑）

用法：
    python3 publish.py work/issue.json --work work [--site .]

為什麼需要它：dashpush 每 180 秒無條件推送整個 repo——**檔案一寫進 data/ 就等於發布**。
在它之前，verify 實際上跑在發布之後：FAIL 時錯的檔已經在線上了。
本腳本把順序反過來：**草稿 → 全部檢查通過 → 才原子寫入 data/**。

它做五件事，全過才落地，任何一步失敗時 data/ 一個位元組都不會動：
  1. 不可改寫守衛：目標單期檔已存在且內容不同 → 拒絕（歷史永不改寫，
     這條規則從 v0.9 之前只是 prompt 裡的一句話，現在有程式在守）
  2. 在暫存區組出「發布後的 index.json」（含量化快照、保留 errata 等既有欄位）
  3. 機械折入 calls：在記憶體中組出新帳本（驗證失敗即中止，不落地）
  4. 跑 verify.py（草稿＋暫存 index，四個語料參數全帶）——exit 非 0 就停
  5. 原子寫入：單期檔、index.json、calls.json、upstream.json（監控庫指紋基準）

exit：0 發布成功；1 verify 或 calls 折帳擋下（什麼都沒寫）；2 不可改寫守衛拒絕；
     3 草稿無法解析／缺 date
"""
import json, os, sys, shutil, subprocess, argparse, datetime as dt, zoneinfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cwlib import upstream_fingerprint, atomic_write_json, is_lit, is_v2


def build_entry(issue, prev_entry):
    """從單期 JSON 組 index 條目。既有欄位（errata、日後新增的任何欄）以 merge 保留。"""
    q = issue["quant"]
    date = issue["date"]
    entry = dict(prev_entry or {})          # 先帶舊欄位，避免重跑洗掉 errata／upstreamFp
    entry.update({
        "date": date, "issue": issue["issue"], "label": issue["label"],
        "short": f"{int(date[5:7])}/{int(date[8:10])}",
        "headline": issue["headline"],
        "composite": q["composite"],
        "dims": {x["id"]: x["v"] for x in q["dims"]},
        "twHeat": q["twHeat"], "stage": q["stage"]["current"],
        "file": f"data/{date}.json",
    })
    if is_v2(q):
        entry["quantVer"] = q["schemaVer"]
        entry["quadrant"] = {k: q["quadrant"][k] for k in ("heat", "support")}
        entry["trigLit"] = sum(1 for t in q.get("triggers", []) if is_lit(t))
    return entry


def fold_calls(ledger, issue):
    """把單期 JSON 的 calls.open/close 機械折入帳本。回傳（新帳本, 錯誤清單）。"""
    calls = {c["id"]: c for c in ledger.get("calls", [])}
    errs = []
    cc = issue.get("calls") or {}
    for cl in cc.get("close", []):
        cid, res = cl.get("id"), cl.get("result")
        if cid not in calls:
            errs.append(f"calls.close 引用不存在的帳目 id：{cid}")
        elif calls[cid].get("status") != "open":
            errs.append(f"calls.close 的 {cid} 已是 {calls[cid].get('status')}，不能重複結案")
        elif res not in ("hit", "miss", "expired", "void"):
            errs.append(f"calls.close 的 {cid} result={res!r} 不合法（hit/miss/expired/void）")
        else:
            calls[cid] = {**calls[cid], "status": res, "closed": issue["date"],
                          "closedIssue": issue["issue"], "closeNote": cl.get("note", "")}
    for op in cc.get("open", []):
        cid = op.get("id")
        if not cid or not str(cid).strip():
            errs.append("calls.open 有帳目缺 id")
        elif cid in calls:
            errs.append(f"calls.open 的 id 重複：{cid}（帳目 id 必須全域唯一，建議格式 c{issue['issue']:03d}-N）")
        elif not op.get("claim") or not op.get("judge"):
            errs.append(f"calls.open 的 {cid} 缺 claim 或 judge——沒有裁判方法的判斷不能登帳")
        else:
            calls[cid] = {"id": cid, "opened": issue["date"], "issue": issue["issue"],
                          "kind": op.get("kind", "watch"), "claim": op["claim"],
                          "judge": op["judge"], "deadline": op.get("deadline"),
                          "status": "open"}
    return {"calls": sorted(calls.values(), key=lambda c: (c.get("opened", ""), c["id"]))}, errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft", help="草稿單期 JSON（例如 work/issue.json）")
    ap.add_argument("--work", default="work")
    ap.add_argument("--site", default=HERE)
    a = ap.parse_args()

    try:
        issue = json.load(open(a.draft, encoding="utf-8"))
    except Exception as e:
        print(f"❌ 草稿無法解析：{e}"); sys.exit(3)
    date = issue.get("date")
    if not date:
        print("❌ 草稿缺 date"); sys.exit(3)

    data_dir = os.path.join(a.site, "data")
    target = os.path.join(data_dir, f"{date}.json")

    # 1) 不可改寫守衛
    if os.path.exists(target):
        old = open(target, encoding="utf-8").read()
        new = json.dumps(issue, ensure_ascii=False, indent=1)
        if old.strip() == new.strip():
            print(f"（{date} 內容與既有檔完全相同，視為冪等重跑）")
        else:
            print(f"❌ data/{date}.json 已存在且內容不同。歷史永不改寫——"
                  f"發布後才發現的問題走 index.json 的 errata，不是改寫單期檔。")
            sys.exit(2)

    # 2) 暫存區組 index
    stage = os.path.join(a.work, "_stage")
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    idx_path = os.path.join(data_dir, "index.json")
    idx = json.load(open(idx_path, encoding="utf-8")) if os.path.exists(idx_path) \
        else {"issues": []}
    prev_entry = next((i for i in idx["issues"] if i["date"] == date), None)
    entry = build_entry(issue, prev_entry)
    issues = [i for i in idx["issues"] if i["date"] != date] + [entry]
    issues.sort(key=lambda x: x["date"], reverse=True)
    is_newest = issues[0]["date"] == date
    now = dt.datetime.now(zoneinfo.ZoneInfo("Asia/Taipei"))
    new_idx = {
        # 重跑舊期不推進發布時間——那會讓 healthcheck 的 updated 檢查永久 WARN
        "updated": now.strftime("%Y-%m-%dT%H:%M:%S+08:00") if is_newest else idx.get("updated", ""),
        "updatedLabel": f"{now.month}/{now.day} {now:%H:%M}" if is_newest else idx.get("updatedLabel", ""),
        "count": len(issues), "issues": issues,
    }
    stage_issue = os.path.join(stage, f"{date}.json")
    stage_idx = os.path.join(stage, "index.json")
    atomic_write_json(stage_issue, issue)
    atomic_write_json(stage_idx, new_idx)

    # 3) calls 折帳（在暫存版上做，錯了不落地）
    calls_path = os.path.join(data_dir, "calls.json")
    ledger = json.load(open(calls_path, encoding="utf-8")) if os.path.exists(calls_path) \
        else {"calls": []}
    new_ledger, call_errs = fold_calls(ledger, issue)
    if call_errs:
        print("❌ 訊號帳本折入失敗：")
        for e in call_errs:
            print("   -", e)
        sys.exit(1)

    # 4) verify（草稿＋暫存 index）
    vargs = [sys.executable, os.path.join(a.site, "verify.py"), stage_issue,
             "--index", stage_idx,
             "--adv", os.path.join(a.work, "adv.txt"),
             "--pod", os.path.join(a.work, "pod.txt"),
             "--cotd", os.path.join(a.work, "cotd.txt"),
             "--bub", os.path.join(a.work, "bub", "data.json")]
    r = subprocess.run(vargs)
    if r.returncode != 0:
        print(f"\n❌ verify 未通過（exit {r.returncode}），**什麼都沒有發布**。修完重跑本指令。")
        sys.exit(1)

    # 5) 落地。四份檔案先全部序列化到 .tmp（任何失敗發生在這裡，data/ 未動），
    #    最後連續四次 os.replace——單檔原子，檔間視窗僅微秒級，把「部分落地」
    #    的風險壓到 replace 本身失敗（磁碟層級）才會發生。
    bub = json.load(open(os.path.join(a.work, "bub", "data.json"), encoding="utf-8"))
    up_path = os.path.join(data_dir, "upstream.json")
    batch = [(target, issue), (idx_path, new_idx), (calls_path, new_ledger),
             (up_path, upstream_fingerprint(bub))]
    import io
    for path, obj in batch:
        with io.open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
    for path, _ in batch:
        os.replace(path + ".tmp", path)
    n_open = sum(1 for c in new_ledger["calls"] if c["status"] == "open")
    n_hit = sum(1 for c in new_ledger["calls"] if c["status"] == "hit")
    n_miss = sum(1 for c in new_ledger["calls"] if c["status"] == "miss")
    print(f"\n✅ 已發布 第 {issue['issue']:03d} 期（{date}）"
          f"｜index {len(issues)} 期｜帳本 {n_hit} 勝 {n_miss} 敗 {n_open} 未決"
          f"｜upstream 指紋已更新")


if __name__ == "__main__":
    main()
