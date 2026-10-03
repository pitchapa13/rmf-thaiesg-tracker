@echo off
rem Weekly local pull (backup for the GitHub Action). Registered in Windows Task Scheduler as "RMF-ThaiESG weekly pull".
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo [%date% %time%] start >> run_weekly.log
git pull --rebase --quiet >> run_weekly.log 2>&1
python pull_funds.py >> run_weekly.log 2>&1
if errorlevel 1 (
  echo [%date% %time%] pull FAILED >> run_weekly.log
  exit /b 1
)
git add data RMF_ThaiESG_returns_fees.xlsx rmf_thaiesg_returns_fees.csv >> run_weekly.log 2>&1
git diff --cached --quiet && (echo [%date% %time%] no changes >> run_weekly.log & exit /b 0)
git commit -q -m "data: weekly pull (local) %date%" >> run_weekly.log 2>&1
git push --quiet >> run_weekly.log 2>&1
echo [%date% %time%] done >> run_weekly.log
