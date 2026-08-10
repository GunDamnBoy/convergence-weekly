#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主題匯流訊號報 · index.json 快照組裝（寫完單期檔後跑，機械環節）

用法：
    python3 make_index.py data/2026-08-09.json

從單期 JSON 自動組出 index.json 的期別條目：
  - quantVer / quadrant / trigLit 依 quant.schemaVer 自動帶入（v2 必填三欄）
  - updated / updatedLabel 填當下台北時間（實際發布時間，不是排程時刻）
  - 既有條目的 errata 保留（那是發布後才發現的問題，洗掉等於把勘誤吞了）
  - 其餘期別原樣保留，依日期由新到舊排序，count 重算

這支腳本**只動 index.json**，永不碰任何單期檔。
⚠️ v1.0 起正式發布流程走 publish.py（先 verify 全過才落地）；
本腳本保留給維護時手動重建 index 用，重跑舊期不會推進 updated、不會洗掉既有欄位。
"""
import json, os, sys, io, datetime as dt, zoneinfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cwlib import is_lit, atomic_write_json

def main():
    if len(sys.argv) != 2:
        sys.exit("用法：python3 make_index.py data/YYYY-MM-DD.json")
    issue_path = sys.argv[1]
    issue = json.load(open(issue_path, encoding="utf-8"))
    data_dir = os.path.dirname(os.path.abspath(issue_path))
    idx_path = os.path.join(data_dir, "index.json")
    idx = json.load(open(idx_path, encoding="utf-8")) if os.path.exists(idx_path) else {"issues": []}

    q = issue["quant"]
    date = issue["date"]
    prev = next((i for i in idx["issues"] if i["date"] == date), {})
    entry = dict(prev)      # 先帶舊欄位——重跑不得洗掉 errata 或日後新增的欄位
    entry.update({
        "date": date,
        "issue": issue["issue"],
        "label": issue["label"],
        "short": f"{int(date[5:7])}/{int(date[8:10])}",
        "headline": issue["headline"],
        "composite": q["composite"],
        "dims": {d["id"]: d["v"] for d in q["dims"]},
        "twHeat": q["twHeat"],
        "stage": q["stage"]["current"],
        "file": f"data/{date}.json",
    })
    if str(q.get("schemaVer", "")).startswith("v") and q.get("schemaVer") != "v1":
        entry["quantVer"] = q["schemaVer"]
        entry["quadrant"] = {k: q["quadrant"][k] for k in ("heat", "support")}
        entry["trigLit"] = sum(1 for t in q.get("triggers", []) if is_lit(t))

    issues = [i for i in idx["issues"] if i["date"] != date] + [entry]
    issues.sort(key=lambda x: x["date"], reverse=True)
    is_newest = issues[0]["date"] == date
    now = dt.datetime.now(zoneinfo.ZoneInfo("Asia/Taipei"))
    out = {
        # 重跑舊期不推進發布時間——那會讓 healthcheck 的 updated 檢查永久 WARN
        "updated": now.strftime("%Y-%m-%dT%H:%M:%S+08:00") if is_newest else idx.get("updated", ""),
        "updatedLabel": f"{now.month}/{now.day} {now:%H:%M}" if is_newest else idx.get("updatedLabel", ""),
        "count": len(issues),
        "issues": issues,
    }
    atomic_write_json(idx_path, out)
    print(f"wrote {idx_path} | 第 {entry['issue']:03d} 期（{date}）"
          f"{'｜quantVer=v2 trigLit='+str(entry.get('trigLit')) if 'quantVer' in entry else ''}"
          f"{'｜errata 保留 '+str(len(entry.get('errata',[])))+' 條' if entry.get('errata') else ''}")

if __name__ == "__main__":
    main()
