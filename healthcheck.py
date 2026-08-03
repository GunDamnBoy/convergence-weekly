#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主題匯流訊號報 · 健康檢查

用法：
    python3 ~/convergence-weekly/healthcheck.py
    python3 healthcheck.py --repo /path/to/convergence-weekly

唯讀。**不執行任何 git 指令**（含 git status）——本機 com.kenny.dashpush 每 180 秒
自動推送，跑 git 會留下 .git/index.lock 擋住推送。要看推送鏈一律直接讀 .git 底下的檔案。

輸出每行是 PASS／WARN／FAIL。把 FAIL 與 WARN 全部帶進維護報告。
"""
import json, os, sys, subprocess, re, datetime as dt, glob

R = {"pass": 0, "warn": 0, "fail": 0}
def ok(m):   R["pass"] += 1; print(f"PASS  {m}")
def warn(m): R["warn"] += 1; print(f"WARN  {m}")
def fail(m): R["fail"] += 1; print(f"FAIL  {m}")

def find_repo():
    for a in sys.argv[1:]:
        if a.startswith("--repo="): return os.path.expanduser(a.split("=", 1)[1])
    if "--repo" in sys.argv:
        return os.path.expanduser(sys.argv[sys.argv.index("--repo") + 1])
    here = os.path.dirname(os.path.abspath(__file__))
    for c in [here, os.path.expanduser("~/convergence-weekly")]:
        if os.path.isdir(os.path.join(c, "data")): return c
    # Cowork 沙箱掛載點
    for c in glob.glob("/sessions/*/mnt/convergence-weekly"):
        if os.path.isdir(os.path.join(c, "data")): return c
    return None

REPO = find_repo()
if not REPO:
    print("FAIL  找不到 convergence-weekly（試過腳本所在目錄、~/convergence-weekly、沙箱掛載點）")
    sys.exit(2)
print(f"repo: {REPO}\n")
D = os.path.join(REPO, "data")

# ── 1. 檔案齊全 ────────────────────────────────────────────────
for f in ["index.html", "data/index.json", "AGENT_BRIEF.md", "MAINTENANCE.md",
          "build_issue.py", "verify.py"]:
    p = os.path.join(REPO, f)
    ok(f"{f} 存在") if os.path.exists(p) else fail(f"{f} 不存在")

# ── 2. 每期 JSON 可解析 ────────────────────────────────────────
files = sorted(glob.glob(os.path.join(D, "20??-??-??.json")))
issues = []
for p in files:
    try:
        d = json.load(open(p, encoding="utf-8"))
        issues.append(d)
    except Exception as e:
        fail(f"{os.path.basename(p)} 解析失敗：{e}")
ok(f"單期檔 {len(files)} 個全部可解析") if len(issues) == len(files) else None
if not files:
    fail("data/ 底下沒有任何單期檔")

# ── 3. index.json 與單期檔一致 ─────────────────────────────────
try:
    idx = json.load(open(os.path.join(D, "index.json"), encoding="utf-8"))
except Exception as e:
    fail(f"index.json 解析失敗：{e}"); idx = None

if idx:
    idl = idx.get("issues", [])
    if len(idl) == len(files):
        ok(f"index.json 期數（{len(idl)}）與單期檔數一致")
    else:
        fail(f"index.json 有 {len(idl)} 期，但 data/ 有 {len(files)} 個單期檔——期別清單漏了或多了")

    if idx.get("count") == len(idl):
        ok("index.json 的 count 與 issues 長度一致")
    else:
        fail(f"index.json count={idx.get('count')} 但 issues 有 {len(idl)} 筆")

    dates = [i.get("date") for i in idl]
    if dates == sorted(dates, reverse=True):
        ok("index.json 依日期由新到舊排序")
    else:
        fail("index.json 未依日期由新到舊排序（前端會拿錯預設期）")

    # 期號連續
    nums = sorted(i.get("issue") for i in idl if isinstance(i.get("issue"), int))
    if nums and nums == list(range(1, len(nums) + 1)):
        ok(f"期號連續（1–{nums[-1]}）")
    elif nums:
        fail(f"期號不連續：{nums}")

    # ★ 跨期趨勢圖的命脈：每期都必須有量化快照
    need = ("composite", "dims", "twHeat", "stage")
    broken = []
    for i in idl:
        miss = [k for k in need if k not in i]
        if set(i.get("dims", {})) != {"D1", "D2", "D3", "D4", "D5", "D6"}:
            miss.append("dims 六維不完整")
        if miss: broken.append(f"{i.get('date')}：缺 {miss}")
    if broken:
        fail("index.json 有期別缺量化快照——跨期趨勢圖會斷：\n        " + "\n        ".join(broken))
    else:
        ok(f"全部 {len(idl)} 期都帶有完整量化快照（趨勢圖可畫）")

    # 每期都指得到實體檔
    for i in idl:
        fp = os.path.join(REPO, i.get("file", ""))
        if not os.path.exists(fp):
            fail(f"index 指向的 {i.get('file')} 不存在")

    # updatedLabel 是否跟得上最新一期（podcast 庫就是栽在這裡）
    if idl:
        newest = idl[0].get("date")
        lab = str(idx.get("updated", ""))
        if newest and newest[:10] not in lab:
            warn(f"updatedLabel／updated（{idx.get('updatedLabel')}／{lab[:10]}）"
                 f"與最新一期日期 {newest} 不一致——前端顯示的時間會是錯的")
        else:
            ok(f"updated 與最新一期（{newest}）一致")

# ── 4. 單期內容規範 ────────────────────────────────────────────
REQ = ("date", "issue", "label", "range", "headline", "coverage",
       "verdict", "quant", "sections", "watch", "gaps", "about")
for d in issues:
    tag = d.get("date", "?")
    miss = [k for k in REQ if k not in d]
    if miss: fail(f"{tag} 缺欄位 {miss}")
    q = d.get("quant", {})
    if len(q.get("dims", [])) != 6:
        fail(f"{tag} quant.dims 不是 6 維")
    # 佐證來源標籤只能是這三個
    bad = set()
    for s in d.get("sections", []):
        for it in s.get("items", []):
            for e in it.get("evidence", []):
                if e.get("s") not in ("監控", "投顧", "節目"): bad.add(e.get("s"))
    if bad: warn(f"{tag} 出現非預期的佐證來源標籤：{bad}")
if issues:
    ok(f"單期內容規範檢查完成（{len(issues)} 期）")

# ── 5. 外殼 JS 語法 ────────────────────────────────────────────
try:
    html = open(os.path.join(REPO, "index.html"), encoding="utf-8").read()
    m = re.search(r"<script>(.*?)</script>", html, re.S)
    if not m:
        fail("index.html 找不到 <script> 區塊")
    else:
        tmp = "/tmp/_cw_check.mjs"
        open(tmp, "w").write(m.group(1))
        r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
        ok("index.html 的 JS 語法正常") if r.returncode == 0 else \
            fail(f"index.html JS 語法錯誤：{r.stderr.strip()[:200]}")
except FileNotFoundError:
    pass
except Exception as e:
    warn(f"JS 語法檢查跳過：{e}")

# ── 6. 推送鏈（純讀檔，不跑 git） ──────────────────────────────
gitdir = os.path.join(REPO, ".git")
lock = os.path.join(gitdir, "index.lock")
if os.path.exists(lock):
    fail("存在 .git/index.lock —— 自動推送被擋住，請 rm 掉")
else:
    ok("無殘留的 .git/index.lock")

def head_of(p):
    try: return open(p).read().strip()[:7]
    except Exception: return None

local = head_of(os.path.join(gitdir, "refs/heads/main"))
remote = head_of(os.path.join(gitdir, "refs/remotes/origin/main"))
if local and remote:
    ok(f"本機與遠端 main 同步（{local}）") if local == remote else \
        warn(f"本機 main={local} 但遠端 origin/main={remote}——尚未推送或推送失敗")
elif local:
    warn("找不到 .git/refs/remotes/origin/main（可能被 packed-refs 收納，屬正常）")

# dashpush 是否納入本 repo
ap = os.path.expanduser("~/.dashpush/auto-push.sh")
if os.path.exists(ap):
    txt = open(ap, encoding="utf-8").read()
    ok("~/.dashpush/auto-push.sh 已納入 convergence-weekly") if "convergence-weekly" in txt \
        else fail("~/.dashpush/auto-push.sh 沒有 convergence-weekly——不會自動推送")
    log = os.path.expanduser("~/.dashpush/push.log")
    if os.path.exists(log):
        lines = [l for l in open(log, encoding="utf-8", errors="ignore").read().split("\n")
                 if "convergence-weekly" in l]
        if lines:
            ok(f"push.log 最近一筆：{lines[-1].strip()}")
        else:
            warn("push.log 裡沒有 convergence-weekly 的任何紀錄")
else:
    warn("找不到 ~/.dashpush/auto-push.sh（若在沙箱執行屬正常）")

# ── 7. 文件內的數值一致性 ──────────────────────────────────────
try:
    mt = open(os.path.join(REPO, "MAINTENANCE.md"), encoding="utf-8").read()
    br = open(os.path.join(REPO, "AGENT_BRIEF.md"), encoding="utf-8").read()
    crons = set(re.findall(r"`?(\d+ \d+ \* \* \d)`?", mt + br))
    if len(crons) > 1:
        fail(f"brief 與 MAINTENANCE 出現不同的 cron：{crons}")
    elif crons:
        ok(f"cron 表述一致：{crons.pop()}")
    times = set(re.findall(r"週日\s*(\d{1,2}:\d{2})", mt + br))
    if len(times) > 1:
        fail(f"執行時刻表述不一致：{times}")
    elif times:
        ok(f"執行時刻表述一致：週日 {times.pop()}")
except FileNotFoundError:
    pass

# ── 總結 ───────────────────────────────────────────────────────
print(f"\n── PASS {R['pass']}　WARN {R['warn']}　FAIL {R['fail']} ──")
sys.exit(1 if R["fail"] else 0)
