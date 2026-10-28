@echo off
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo ========================================================
echo  Launching PhishShift Message Risk Scanner...
echo ========================================================
echo.
"C:\Users\ELCOT\AppData\Local\Programs\Python\Python313\python.exe" -m streamlit run app.py
pause
