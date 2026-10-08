# -*- coding: utf-8 -*-
"""Which RMF/ThaiESG/ThaiESGX funds hold a given stock (in their TOP-5 holdings, per Finnomena/Morningstar)?
Usage: python find_holding.py "ธนาคารกรุงเทพ|BBL|Bangkok Bank" [label]
"""
import json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor
try:
    from curl_cffi import requests as rq
    def get(u): return rq.get(u, impersonate="chrome", timeout=60)
except Exception:
    import requests as rq
    def get(u): return rq.get(u, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)

ROOT = os.path.dirname(os.path.abspath(__file__))
pattern = re.compile(sys.argv[1] if len(sys.argv) > 1 else r"ธนาคารกรุงเทพ|BBL|Bangkok Bank", re.I)
label = sys.argv[2] if len(sys.argv) > 2 else "BBL"
funds = json.load(open(os.path.join(ROOT, "data", "funds.json"), encoding="utf-8"))["funds"]

def fetch(f):
    u = f"https://www.finnomena.com/fn3/api/fund/v2/public/funds/{f['fund_id']}/portfolio"
    for i in range(3):
        try:
            r = get(u)
            if r.status_code == 200:
                d = r.json().get("data") or {}
                th = d.get("top_holdings") or {}
                return f, th.get("data_date", "")[:10], th.get("elements") or []
            time.sleep(1 + i)
        except Exception:
            time.sleep(1 + i)
    return f, None, None

hits, failed, with_data = [], [], 0
with ThreadPoolExecutor(8) as ex:
    for f, dd, els in ex.map(fetch, funds):
        if els is None:
            failed.append(f["code"]); continue
        if els: with_data += 1
        for e in els:
            if pattern.search(e.get("name") or ""):
                hits.append({"type": f["type"], "amc": f["amc"], "code": f["code"], "name": f["name"],
                             "cat": f["cat"], "holding": e["name"], "pct": e.get("percent"), "as_of": dd,
                             "r1y": f.get("r1y"), "r3y": f.get("r3y"), "mgmt_act": f.get("mgmt_act")})
hits.sort(key=lambda h: (h["type"], -(h["pct"] or 0)))
import csv
out = os.path.join(ROOT, f"holders_{label}.csv")
with open(out, "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=list(hits[0].keys()) if hits else ["code"]); w.writeheader(); w.writerows(hits)
print(f"funds={len(funds)} with_top5_data={with_data} failed={len(failed)} hits={len(hits)} -> {out}")
for h in hits:
    print(f"{h['type']:<9}{h['amc']:<11}{h['code']:<28}{h['pct']:>6.2f}%  {h['as_of']}  1Y {h['r1y']}  3Y {h['r3y']}  | {h['holding']}")
if failed: print("failed:", failed[:20])
