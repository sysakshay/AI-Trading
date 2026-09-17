# Paper Research — version 0.2

## Repository-inspired upgrade

Reviewed TradingAgents, aaryansinha16/AI-trader and HKUDS/AI-Trader. New: recorded supporting/opposing research, timestamped evidence imports, market-condition diagnostics, saved policy experiments and operating expenses. Period accounting and forward freshness/worker ownership were corrected. Default paper-trading rules remain unchanged.

Read [the comparison and implementation decisions](docs/REPOSITORY_COMPARISON.md) and [what you need to connect](docs/CONNECTION_CHECKLIST.md). No new runtime libraries or API subscriptions are required.

A local Windows application for learning how a transparent stock strategy behaves with virtual money. Offline demonstration, manual replay, deterministic backtests, SQLite journal, bounded AI reviews, and a read-only Upstox adapter. No real-order API exists.

## Start

Open PowerShell in this folder and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_app.ps1
```

Open **http://localhost:8501** and choose **Start offline demo**. Approve a proposal, then advance twice to see its fill and exit. [QUICK_START.md](QUICK_START.md) gives the exact walkthrough; [USER_SETUP.md](USER_SETUP.md) covers installation and optional accounts.

Python 3.14.6 and the exact versions in `requirements.txt` were installed and tested on Windows. The first installation needs internet; the installed sample workflow needs no network, API key or payment. Keep the PowerShell window open while using the app.

## What is delivered

- Completed 15-minute candle strategy, conservative costs/slippage, whole-share risk sizing and daily limits.
- Approval tied to candidate revision; later-close fills; stop-first ambiguity and adverse gap handling.
- Immutable data per run, atomic cash/fill ledger, persistence across restart, backup/restore and JSON export.
- Rules-only, mock AI and failing mock demonstrations; optional Responses API adapter with zero default paid allowance.
- Historical CSV import, automatic backtests, isolated rules/mock comparisons and separate human replay histories.
- Standalone forward worker with verified-feed prerequisites, pause/recovery and no retrospective entries.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m src.cli --db data\verification.db demo-report
```

The demonstration has one winning and one losing trade, with **INR -5.12 net** under the default automated policy. This is a software fixture, not historical performance. A failed mock review results in no trades.

## Read next

- [Project status and limitations](PROJECT_STATUS.md)
- [Architecture and financial assumptions](docs/ARCHITECTURE.md)
- [Data-provider comparison and official sources](docs/PROVIDERS.md)
- [Daily and weekly checklist](docs/OPERATING_CHECKLIST.md)
- [Troubleshooting](TROUBLESHOOTING.md)

External connections have **not** been verified with real credentials. No paid requests were made. Forward observation over several weeks remains future work for the user after access and data checks. Browser visual verification was unavailable; automated Streamlit interaction checks ran.
