# Launch PhishShift Streamlit App
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " Starting PhishShift Message Risk Scanner...            " -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan

$pythonExe = "C:\Users\ELCOT\AppData\Local\Programs\Python\Python313\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $pythonExe) { $pythonExe = "py" }
}

& $pythonExe -m streamlit run app.py
