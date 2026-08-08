#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主題匯流訊號報 · index.json 快照組裝（每週排程的第 5 步後半，機械環節）

用法：
    python3 make_index.py data/2026-08-09.json

從單期 JSON 自動組出 index.json 的期別條目：
  - quantVer / quadrant / trigLit 依 quant.schemaVer 自動帶入（v2 必填三欄）
  - updated / updatedLabel 填當下台北時間（實際發布時間，不是排程時刻）
  - 既有條目的 errata 保留（那是發布後才發現的問題，洗掉等於把勘誤吞了）
  - 其餘期別原樣保留，依日期由新到舊排序，count 重算

這支腳本**只動 index.json**，永不碰任何單期檔。
跑完請接著跑 verify.py（它會核對這裡寫出的快照）。
"""
import json, os, sys, io, datetime as dt, zoneinfo

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
    entry = {
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
    }
    if q.get("schemaVer") == "v2":
        entry["quantVer"] = "v2"
        entry["quadrant"] = {k: q["quadrant"][k] for k in ("heat", "support")}
        entry["trigLit"] = sum(1 for t in q.get("triggers", []) if t.get("state"))
    if prev.get("errata"):
        entry["errata"] = prev["errata"]

    issues = [i for i in idx["issues"] if i["date"] != date] + [entry]
    issues.sort(key=lambda x: x["date"], reverse=True)
    now = dt.datetime.now(zoneinfo.ZoneInfo("Asia/Taipei"))
    out = {
        "updated": now.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "updatedLabel": f"{now.month}/{now.day} {now:%H:%M}",
        "count": len(issues),
        "issues": issues,
    }
    with io.open(idx_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"wrote {idx_path} | 第 {entry['issue']:03d} 期（{date}）"
          f"{'｜quantVer=v2 trigLit='+str(entry.get('trigLit')) if 'quantVer' in entry else ''}"
          f"{'｜errata 保留 '+str(len(entry.get('errata',[])))+' 條' if entry.get('errata') else ''}")

if __name__ == "__main__":
    main()
