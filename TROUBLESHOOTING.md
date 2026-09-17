# Troubleshooting

| What you see | What to do | Success looks like |
|---|---|---|
| Python not recognized | Install Python 3.14 x64 from python.org; reopen PowerShell | `python --version` prints a version |
| Script execution blocked | Use the launch command in QUICK_START; if managed policy forbids it, run the direct commands below | Local URL appears |
| First install cannot reach PyPI | Restore internet/proxy access and retry; offline mode is offline after libraries are installed | pip finishes without error |
| Port 8501 in use | Open the existing URL or launch on port 8502 | The Paper Research title appears |
| Browser page unavailable | Keep the terminal running; use `http://127.0.0.1:8501`; check its error output | Dashboard loads |
| No proposals | Start offline demo or advance until warm-up completes; no trade is valid | Watchlist explains failed rules |
| Approved but no position | Advance one candle; inspect cancelled-order reason if risk or levels changed | A later eligible fill or explicit cancellation |
| Expired proposal | It cannot be revived; wait for a new eligible proposal | New candidate has its own ID |
| Failed MOCK review | Intentional scenario; create a separate `mock` or `rules` run | New run has its chosen policy |
| Missing key / no budget | Offline still works; complete optional setup privately | Valid real response only after authorized call |
| 401/403 provider error | Renew token or verify entitlement with Upstox | Read-only check returns actual candles |
| Stale feed / missing candle | Pause entries; inspect timestamp and gaps; never fill missing prices | Verified fresh observations; otherwise replay |
| Database locked | Avoid duplicate workers; stop extra processes, wait 15 seconds, retry | Atomic action completes once |
| Unresolved end-of-day position | Keep worker running for actual subsequent data; inspect recovery exit | Recorded later observation resolves it |
| Newer schema error | Use a matching newer app version or restore a compatible backup to a new file | History remains preserved |

## Direct launch without a script

In PowerShell in the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
```

Use `--server.port 8502` if necessary and open that port. Do not expose the server publicly; it is a local single-user app.

Before reporting an error, record the mode, run ID, displayed reason and time. Do not send `.env`, authorization headers or complete API exceptions. Back up the database before changing it. Deleting a database is never a repair step here.
