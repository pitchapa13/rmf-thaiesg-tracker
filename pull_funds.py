# -*- coding: utf-8 -*-
"""Pull RMF / ThaiESG / ThaiESGX fund returns + fees from the Finnomena public API.

Outputs (relative to this script's folder):
  data/funds.json         - latest snapshot for the web dashboard
  data/history.json       - NAV per fund per pull date (grows weekly) -> used to compute returns
  data/nav_history.csv    - same as above, flat CSV
  RMF_ThaiESG_returns_fees.xlsx / rmf_thaiesg_returns_fees.csv

Run:  python pull_funds.py            (set env FUNDS_RAW_CACHE=1 to reuse raw_finnomena_filter.json)
"""
import json, re, sys, time, os, csv
from datetime import datetime, timezone, timedelta
import requests
import pandas as pd
try:  # Cloudflare in front of finnomena.com blocks plain datacenter clients (GitHub runners) -> impersonate Chrome TLS
    from curl_cffi import requests as cffi_requests
except Exception:  # pragma: no cover
    cffi_requests = None

BASE = "https://www.finnomena.com/fn3/api/fund/v2/public"
H = {"User-Agent": "Mozilla/5.0 (fund-tracker)", "Accept": "application/json"}
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
os.makedirs(DATA, exist_ok=True)
RAW = os.path.join(ROOT, "raw_finnomena_filter.json")
TZ = timezone(timedelta(hours=7))
TODAY = datetime.now(TZ).strftime("%Y-%m-%d")

def log(*a):
    print(*a, file=sys.stderr, flush=True)

BROWSER_H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*", "Accept-Language": "th-TH,th;q=0.9,en;q=0.8",
    "Referer": "https://www.finnomena.com/fund/filter", "Origin": "https://www.finnomena.com",
}

def get(url, **kw):
    for i in range(5):
        try:
            if cffi_requests is not None and (i % 2 == 0 or os.environ.get("FORCE_CFFI")):
                r = cffi_requests.get(url, headers=BROWSER_H, timeout=90, impersonate="chrome", **kw)
            else:
                r = requests.get(url, headers=BROWSER_H, timeout=90, **kw)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]!r}")
            return r.json()
        except Exception as e:
            log("retry", i, url, e); time.sleep(3 * (i + 1))
    raise SystemExit("failed: " + url)

# ---------- 1) all funds with returns + fees (paginated) ----------
if os.environ.get("FUNDS_RAW_CACHE") and os.path.exists(RAW):
    allf = json.load(open(RAW, encoding="utf-8"))
else:
    allf, page = [], 1
    while True:
        d = get(f"{BASE}/filter", params={"page": page, "limit": 100})["data"]
        allf += d["funds"]
        log(f"page {page}/{d['pagination']['page_total']} -> {len(allf)}")
        if d["pagination"]["last_page"] or page >= d["pagination"]["page_total"]:
            break
        page += 1
    json.dump(allf, open(RAW, "w", encoding="utf-8"), ensure_ascii=False)

# ---------- 2) names + AIMC category ----------
lst = get(f"{BASE}/funds")["data"]
name = {f["fund_id"]: f.get("name_th") for f in lst}
catid = {f["fund_id"]: f.get("aimc_category_id") for f in lst}
cats = get(f"{BASE}/categories")["data"]
catname, caten, catrisk = {}, {}, {}
for c in cats:
    catname[c["aimc_category_id"]] = c["name_th"]
    for s in c.get("sub_categories", []):
        catname[s["aimc_category_id"]] = s["name_th"]
        caten[s["aimc_category_id"]] = s["name_en"]
        catrisk[s["aimc_category_id"]] = s.get("risk_level")

def num(v):
    try:
        return None if v is None else float(v)
    except Exception:
        return None

def fee(fs, desc):
    for x in fs or []:
        if x.get("description") == desc:
            return num(x.get("rate")), num(x.get("actual_value"))
    return None, None

def classify(code, nm):
    c = (code or "").upper().replace(" ", "")
    n = nm or ""
    if "RMF" in c or "เพื่อการเลี้ยงชีพ" in n:
        return "RMF"
    # ThaiESGX = "ไทยเพื่อความยั่งยืนแบบพิเศษ" (Thai ESG Extra, launched May 2025)
    if re.search(r"THAIESGX|TESGX|ESGX", c) or "ไทยเพื่อความยั่งยืนแบบพิเศษ" in n:
        return "ThaiESGX"
    # ThaiESG: SEC naming rule requires "ThaiESG" / "ไทยเพื่อความยั่งยืน" in the class name
    if re.search(r"THAIESG", c) or "ไทยเพื่อความยั่งยืน" in n or (re.search(r"TESG", c) and "ยั่งยืน" in n):
        return "ThaiESG"
    return None

rows = []
for f in allf:
    code = f.get("short_code"); nm = name.get(f["fund_id"])
    t = classify(code, nm)
    if not t:
        continue
    mg = fee(f.get("fees"), "ค่าธรรมเนียมการจัดการ")
    te = fee(f.get("fees"), "ค่าธรรมเนียมและค่าใช้จ่ายรวมทั้งหมด")
    fr = fee(f.get("fees"), "ค่าธรรมเนียมการขายหน่วยลงทุน (Front-end Fee)")
    bk = fee(f.get("fees"), "ค่าธรรมเนียมการรับซื้อคืนหน่วยลงทุน (Back-end Fee)")
    cid = catid.get(f["fund_id"])
    rows.append({
        "type": t, "amc": f.get("amc_name"), "code": code, "name": nm,
        "cat": catname.get(cid), "cat_en": caten.get(cid), "risk": catrisk.get(cid),
        "nav": num(f.get("nav")), "nav_date": (f.get("nav_date") or "")[:10],
        "ytd": num(f.get("return_ytd")), "r1y": num(f.get("return_1y")),
        "r3y": num(f.get("return_3y")), "r5y": num(f.get("return_5y")), "r10y": num(f.get("return_10y")),
        "mgmt_max": mg[0], "mgmt_act": mg[1], "ter_max": te[0], "ter_act": te[1],
        "front_max": fr[0], "front_act": fr[1], "back_max": bk[0], "back_act": bk[1],
        "factsheet": f.get("fund_fact_sheet"), "fund_id": f["fund_id"],
    })

rows.sort(key=lambda r: (r["type"], -(r["r3y"] if r["r3y"] is not None else -1e9), -(r["r1y"] if r["r1y"] is not None else -1e9)))
counts = {}
for r in rows:
    counts[r["type"]] = counts.get(r["type"], 0) + 1
log("counts:", counts)

# ---------- 3) NAV history (weekly snapshots) -> lets the site compute returns from NAV ----------
hist_path = os.path.join(DATA, "history.json")
hist = json.load(open(hist_path, encoding="utf-8")) if os.path.exists(hist_path) else {"dates": [], "nav": {}}
if TODAY not in hist["dates"]:
    hist["dates"].append(TODAY)
for r in rows:
    if r["nav"] is None or not r["nav_date"]:
        continue
    series = hist["nav"].setdefault(r["code"], [])
    # one point per nav_date (the API returns the latest NAV; dedupe by nav_date)
    if not any(p[0] == r["nav_date"] for p in series):
        series.append([r["nav_date"], r["nav"]])
        series.sort()
json.dump(hist, open(hist_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
with open(os.path.join(DATA, "nav_history.csv"), "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh); w.writerow(["code", "nav_date", "nav"])
    for code, series in sorted(hist["nav"].items()):
        for d, v in series:
            w.writerow([code, d, v])

# ---------- 4) web JSON ----------
meta = {
    "pulled_at": datetime.now(TZ).strftime("%Y-%m-%d %H:%M") + " (ICT)",
    "pull_date": TODAY,
    "nav_date_max": max((r["nav_date"] for r in rows if r["nav_date"]), default=""),
    "counts": counts, "total_funds_scanned": len(allf),
    "source": "Finnomena public API (ข้อมูล NAV/ค่าธรรมเนียมจาก Morningstar + fund factsheet ก.ล.ต.)",
    "history_dates": hist["dates"],
}
json.dump({"meta": meta, "funds": rows}, open(os.path.join(DATA, "funds.json"), "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))

# ---------- 5) Excel / CSV ----------
TH = {
    "type": "ประเภท", "amc": "บลจ.", "code": "รหัสกองทุน", "name": "ชื่อกองทุน", "cat": "กลุ่ม AIMC",
    "cat_en": "AIMC category (EN)", "risk": "ระดับความเสี่ยง", "nav": "NAV", "nav_date": "วันที่ NAV",
    "ytd": "YTD %", "r1y": "1Y %", "r3y": "3Y % ต่อปี", "r5y": "5Y % ต่อปี", "r10y": "10Y % ต่อปี",
    "mgmt_max": "Mgmt fee สูงสุด (% ต่อปี)", "mgmt_act": "Mgmt fee เก็บจริง (% ต่อปี)",
    "ter_max": "TER สูงสุด (% ต่อปี)", "ter_act": "TER เก็บจริง (% ต่อปี)",
    "front_max": "Front-end สูงสุด %", "front_act": "Front-end เก็บจริง %",
    "back_max": "Back-end สูงสุด %", "back_act": "Back-end เก็บจริง %", "factsheet": "Fund factsheet",
}
df = pd.DataFrame(rows).drop(columns=["fund_id"]).rename(columns=TH)
df.to_csv(os.path.join(ROOT, "rmf_thaiesg_returns_fees.csv"), index=False, encoding="utf-8-sig")

def summ(g):
    return pd.Series({
        "จำนวนกอง": len(g), "กองที่มีผล 3Y": g["3Y % ต่อปี"].notna().sum(),
        "เฉลี่ย 1Y %": g["1Y %"].mean(), "เฉลี่ย 3Y % ต่อปี": g["3Y % ต่อปี"].mean(),
        "มัธยฐาน 3Y % ต่อปี": g["3Y % ต่อปี"].median(),
        "เฉลี่ย Mgmt fee เก็บจริง": g["Mgmt fee เก็บจริง (% ต่อปี)"].mean(),
        "เฉลี่ย TER เก็บจริง": g["TER เก็บจริง (% ต่อปี)"].mean(),
    })
summary = df.groupby(["ประเภท", "บลจ."]).apply(summ, include_groups=False).reset_index()

notes = pd.DataFrame({"หมายเหตุ": [
    f"ดึงข้อมูลเมื่อ {meta['pulled_at']} จาก Finnomena public API (fn3/api/fund/v2/public/filter) ซึ่งใช้ข้อมูล NAV/ค่าธรรมเนียมจาก Morningstar + fund factsheet ของ ก.ล.ต.",
    "ผลตอบแทนคำนวณจาก NAV (หักค่าธรรมเนียมการจัดการ/TER แล้ว ยังไม่หัก front-end/back-end และยังไม่รวมสิทธิประโยชน์ทางภาษี) — ผลตอบแทน > 1 ปี เป็น % ต่อปี (annualized) ตามมาตรฐาน AIMC",
    "ค่าธรรมเนียม: 'สูงสุด' = เพดานตามหนังสือชี้ชวน (รวม VAT), 'เก็บจริง' = อัตราที่เรียกเก็บจริงล่าสุดตาม factsheet; TER = ค่าธรรมเนียมและค่าใช้จ่ายรวมทั้งหมด",
    "ThaiESG เริ่มขาย ธ.ค. 2566 จึงยังไม่มีผลตอบแทน 3 ปี (ครบ 3 ปีประมาณ ธ.ค. 2569); ThaiESGX เริ่ม พ.ค. 2568 มีแค่ ~1 ปี",
    "กอง RMF/ThaiESG ที่อายุไม่ถึง 3 ปี ช่อง 3Y จะว่าง",
    "ข้อมูลนี้เป็น third-party (ไม่ใช่ sec.or.th โดยตรง) — ก่อนนำไปใช้เผยแพร่ควรตรวจกับ fund factsheet ล่าสุดของแต่ละ บลจ. (ลิงก์ในคอลัมน์ Fund factsheet)",
    "ไม่ใช่คำแนะนำการลงทุน ผลการดำเนินงานในอดีตไม่ได้เป็นสิ่งยืนยันถึงผลการดำเนินงานในอนาคต",
]})

xlsx = os.path.join(ROOT, "RMF_ThaiESG_returns_fees.xlsx")
with pd.ExcelWriter(xlsx, engine="openpyxl") as w:
    notes.to_excel(w, sheet_name="README", index=False)
    summary.to_excel(w, sheet_name="สรุปราย บลจ", index=False)
    for t in ["ThaiESG", "ThaiESGX", "RMF"]:
        df[df["ประเภท"] == t].drop(columns=["ประเภท"]).to_excel(w, sheet_name=t, index=False)
    df.to_excel(w, sheet_name="ทั้งหมด", index=False)

from openpyxl import load_workbook
wb = load_workbook(xlsx)
for ws in wb.worksheets:
    ws.freeze_panes = "A2"
    for col in ws.columns:
        hdr = str(col[0].value or "")
        width = 60 if hdr == "หมายเหตุ" else (46 if hdr == "ชื่อกองทุน" else (30 if "AIMC" in hdr or "factsheet" in hdr else max(10, min(24, len(hdr) + 4))))
        ws.column_dimensions[col[0].column_letter].width = width
        for c in col[1:]:
            if isinstance(c.value, float):
                c.number_format = "0.00"
wb.save(xlsx)
log("wrote", xlsx, len(df), "funds; history dates:", hist["dates"])
