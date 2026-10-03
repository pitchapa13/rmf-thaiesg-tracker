# RMF / ThaiESG Tracker

ผลตอบแทนหลังหักค่าธรรมเนียม (YTD / 1Y / 3Y / 5Y / 10Y, NAV-based) และ management fee / TER
ของกองทุน **RMF · ThaiESG · ThaiESGX** ทุก บลจ. — อัปเดตอัตโนมัติ **ทุกวันศุกร์ 23:30 น.** ด้วย GitHub Actions

- หน้าเว็บ: `index.html` (GitHub Pages) อ่าน `data/funds.json` + `data/history.json`
- ตัวดึงข้อมูล: `pull_funds.py` → Finnomena public API (`fn3/api/fund/v2/public/filter`) ซึ่งใช้ข้อมูล NAV/ค่าธรรมเนียมจาก Morningstar + fund factsheet ก.ล.ต.
- `data/history.json` / `data/nav_history.csv` เก็บ NAV ของทุกกองทุกสัปดาห์ → ใช้คำนวณผลตอบแทนเอง (คอลัมน์ "1 สัปดาห์" และ "ตั้งแต่เริ่มเก็บ" บนเว็บ)
- `RMF_ThaiESG_returns_fees.xlsx` / `rmf_thaiesg_returns_fees.csv` = ตารางล่าสุดสำหรับดาวน์โหลด

## รันเอง
```bash
pip install -r requirements.txt
python pull_funds.py
```
(ตั้ง `FUNDS_RAW_CACHE=1` เพื่อใช้ `raw_finnomena_filter.json` ที่ดึงไว้แล้วแทนการดึงใหม่ ~2 นาที)

## สั่งดึงทันที
GitHub → Actions → "Pull fund data (every Friday)" → **Run workflow**

## หมายเหตุ
- ผลตอบแทน > 1 ปี เป็น % ต่อปี (annualized) ตามมาตรฐาน AIMC; หัก mgmt fee/TER แล้ว, ยังไม่หัก front/back-end และไม่รวมสิทธิภาษี
- ค่าธรรมเนียม "เก็บจริง" = อัตราที่เรียกเก็บจริงล่าสุด, "สูงสุด" = เพดานตามหนังสือชี้ชวน (รวม VAT)
- ThaiESG เริ่ม ธ.ค. 2566 → ยังไม่มีผล 3 ปีจนถึง ~ธ.ค. 2569; ThaiESGX เริ่ม พ.ค. 2568
- ข้อมูล third-party — ตรวจกับ factsheet ล่าสุดของ บลจ. ก่อนเผยแพร่; ไม่ใช่คำแนะนำการลงทุน
