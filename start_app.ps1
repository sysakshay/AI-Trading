$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (!(Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python could not create the environment. See USER_SETUP.md.' }
}
& '.\.venv\Scripts\python.exe' -c 'import streamlit, openai, plotly, pandas_market_calendars'
if ($LASTEXITCODE -ne 0) {
    & '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency install failed. Check internet access and TROUBLESHOOTING.md.' }
}
Write-Host 'Open http://localhost:8501 in your browser. Press Ctrl+C here to stop the dashboard.'
& '.\.venv\Scripts\python.exe' -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
