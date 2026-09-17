# User setup guide

**Version 0.2 update:** see [the repository comparison](docs/REPOSITORY_COMPARISON.md) and [short connection checklist](docs/CONNECTION_CHECKLIST.md). A schema-1 database is backed up beside the original as `*.before-v2-*.db` before its first upgrade. Existing accounts/candidates remain intact. Schema-2 backups require version 0.2 or later.

The new research lenses and saved experiments need no keys. News/fundamental imports are optional replay JSON, imported before the first candidate; their links are not fetched. Paid AI remains one optional reviewer with explicit budget caps. In Evaluation, operating expense allocations are now stored in the journal, separate from virtual cash.

## Stage A — run offline

### 1. Understand the folder

The app is in `X:\GitHub\AI_Trading`. Files named `.py` contain the program; you do not need to edit them. `data\paper.db` stores your virtual accounts. `backups` holds database copies. `reports` holds generated reports. A virtual environment (`.venv`) keeps this project's libraries separate from other Python programs.

### 2. Check Python

In File Explorer, open the project folder, type `powershell` in the address bar, and press Enter. Enter `python --version`. Success on the tested machine is `Python 3.14.6`. If Windows opens the Store or says Python is missing, install the 64-bit Python 3.14 release from [Python for Windows](https://www.python.org/downloads/windows/), enable the installer option to expose Python on PATH when offered, reopen PowerShell, and repeat the check. The `py` command is not installed on this machine; use `python`.

### 3. Launch

Enter `powershell -NoProfile -ExecutionPolicy Bypass -File .\start_app.ps1`. This bypass applies to this launch only; it does not change machine policy. The launcher creates `.venv` and installs the pinned libraries if they are missing. Initial installation needs internet. Success: it prints `http://localhost:8501`. Open that address and follow [QUICK_START.md](QUICK_START.md). If corporate policy blocks scripts, use the direct commands in troubleshooting.

Once installed, the sample mode needs no broker account, keys, payment or network. A candle summarizes a 15-minute interval's opening, highest, lowest and closing price plus traded volume. Only finished intervals are used. Advancing replay moves a simulated clock; it does not wait 15 real minutes.

### 4. Preserve results

Use **Settings & data → Create consistent database backup**. Success: a path under `backups` is displayed. Use **Journal → Export complete run** to download JSON records. Money in raw records is paise (100 paise = INR 1).

To restore, stop the app and worker with Ctrl+C. In PowerShell run, substituting the backup filename:

```powershell
.\.venv\Scripts\python.exe -m src.cli restore backups\paper-YOUR-TIMESTAMP.db data\restored.db
$env:PAPER_DB = 'data\restored.db'
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_app.ps1
```

Success: the restored run appears. Restore refuses to overwrite an existing destination and checks database integrity first. Never copy only `paper.db` while the app is active: SQLite may also have live journal files. Use the backup button.

## Stage B — optionally connect OpenAI

**Current state: not connected or billed.** Offline mock reviews are visibly labeled. AI only explains or filters a rule-generated candidate; it cannot place trades, alter amounts or bypass your decision. SQLite is its memory: the app selects and sends up to 20 completed outcomes. The model does not automatically read your computer or learn from the journal.

1. Open [OpenAI Platform](https://platform.openai.com/) in your own browser. Sign in or create your own account. Select or create a project for this app. Success: the project's API-key and billing settings are accessible. If you lack permission, the account owner must grant it. Follow the [official quickstart](https://developers.openai.com/api/docs/quickstart).
2. Review API billing and available credits in Platform settings. Do not assume a ChatGPT subscription supplies API credit, or that a free trial is available. Review the account's actual balance before enabling usage. Project usage/limits and key security are described in [production guidance](https://developers.openai.com/api/docs/guides/production-best-practices). You decide whether to fund the account; this app does not purchase credits or enable recharge.
3. Create a project API key. In the project folder, copy `.env.example` to `.env` using File Explorer. Open `.env` in Notepad and enter the key after `OPENAI_API_KEY=`. Never paste it in chat. Do not share the file or include it in screenshots. `.env` is plain readable text, excluded by `.gitignore`; protect your Windows account and folder permissions.
4. Leave the initial budget at zero until you explicitly choose one. The configured model is `gpt-5-mini`, whose [official model page](https://developers.openai.com/api/docs/models/gpt-5-mini) lists Structured Outputs and USD 0.25 input / USD 2 output per million tokens (checked 2026-09-16). Access in your project remains unverified. A different model requires reviewing its price bound in code before enabling it.
5. When you choose to authorize a small test, an example **user-selected** cap is `AI_BUDGET_APPROVED=true`, `AI_DAILY_USD=0.03`, `AI_DAILY_REQUESTS=1`. These are an example, not authorization already given. Set a separate forward account's `settings.ai_mode` to `openai`. Restart the worker after editing `.env`. The `AI_MODE` example variable documents the intended policy; the saved run's `ai_mode` controls actual behavior and never changes an existing run silently.
6. A qualifying current forward candidate becomes the connection smoke test. The app reserves USD 0.03 before sending, permits at most the configured daily count, and does not retry uncertain calls. Success: **Settings & data** reports a previously verified response and the candidate displays a validated review. Failure: the candidate shows a sanitized authentication, quota, model, timeout or validation error and cannot be approved. Mock tests cover these paths; no real success is claimed yet. Paid historical replay is disabled.
7. Review actual charges on the Platform Usage page. App reservations are deliberately conservative estimates, not the invoice. Keep alerts and any provider spending controls appropriate to your account; alerts alone are not a hard cap.

The request uses the official SDK's [Responses Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), no external tools, and `store=False`. This does **not** guarantee zero provider retention; consult [data controls](https://developers.openai.com/api/docs/guides/your-data). Keys are not included in prompts or exports.

## Stage C — optionally connect market data

Read [the comparison](docs/PROVIDERS.md) first. The recommendation is **Upstox's read-only Analytics Token**, subject to account eligibility and rights confirmation. The internal simulator itself needs no brokerage deposit.

1. Open the [Upstox Developer Apps page](https://account.upstox.com/developer/apps) and sign in yourself. Confirm whether your account can access Analytics. If Upstox requires account opening, identity/KYC verification, terms acceptance or two-factor authentication, complete those yourself on Upstox; this project has not verified non-broker-account eligibility. Do not open several accounts just for this demo.
2. In **Analytics**, choose **Generate Token**, confirm, and copy the token privately into `.env` after `UPSTOX_ACCESS_TOKEN=`. Success: the provider page shows its expiry. The [official token guide](https://upstox.com/developer/api-documentation/analytics-token/) describes a free read-only token with one-year validity and no static-IP requirement for historical/market data. This route does not require daily OAuth login. If the token is revoked or expires, replace it locally. Trading permissions are unnecessary.
3. Ask Upstox to confirm your right to retain candle snapshots locally and display them privately in this app. Also confirm unadjusted executable price conventions and corporate-action handling. Documentation reviewed did not settle these rights/adjustments. Until clarified, keep forward trading blocked. Never redistribute downloaded data.
4. Run this read-only historical check in the project PowerShell window, with a recent known trading interval:

   ```powershell
   .\.venv\Scripts\python.exe -m src.cli data-check --symbol RELIANCE --start 2026-09-14 --end 2026-09-15
   ```

   This is an example instrument for access testing, not a buy recommendation. Success: an actual candle timestamp, count and instrument identity print and are saved in `data\provider-check.json`. A historical result proves neither real-time delivery nor adjustment correctness. On 401/403, check the token and entitlement; no authentication bypass is attempted.
5. During an open NSE session, within one minute after a 15-minute boundary, run ` .\.venv\Scripts\python.exe -m src.cli feed-check --symbol RELIANCE`. Success: `supported: true` with a recent timestamp. Repeat at several boundaries; inspect `data\feed-check.json`. The reported age includes polling delay and is only a conservative observed bound. If age exceeds 60 seconds, use replay; do not claim real-time monitoring.

## Stage D — forward paper session

This is an advanced optional stage; the offline walkthrough is complete without it. Real credentials and several live-session observations have not been tested here.

1. Choose virtual capital (default INR 10,000), keep risk limits, and choose up to 20 verified NSE cash instruments. No verified liquidity ranking is supplied. Prefer a watchlist established from a separate dated turnover/volume analysis; record the source. The example single symbol only demonstrates setup.
2. Make a draft calendar: ` .\.venv\Scripts\python.exe -m src.cli calendar --start 2026-09-14 --end 2026-10-31`. It writes `data\verified-schedule.json`. Compare dates and times with [NSE timings](https://www.nseindia.com/static/market-data/market-timings) and [holiday/special-session circulars](https://www.nseindia.com/resources/exchange-communication-holidays/). The library is not proof that late special sessions are included. Add explicit verified sessions if needed; unsupported partial 15-minute bars are excluded.
3. Copy `forward.example.json` to `data\forward.json`. Update symbols, warm-up dates (at least 23 complete bars), schedule path, and `settings`. Set verification fields true **only after** completing Stage C/calendar checks, and fill the observed timestamp and measured delay from the feed check. Exclude intervals affected by splits or other corporate actions. These are documented attestations, not measured automatically by this app.
4. Run ` .\.venv\Scripts\python.exe -m src.cli forward-init data\forward.json`. Success: it prints a new forward run ID after loading historical warm-up without past candidates. Then run:

   ```powershell
   .\.venv\Scripts\python.exe -m src.cli worker data\forward.json --run YOUR_RUN_ID
   ```

   Select that saved run in the dashboard. Leave the worker terminal open and the computer awake with internet available. Refresh the dashboard to see new data; it does not schedule work. Status includes last fetch, processed candle, next check and errors.
5. Review proposals and approve or reject before expiry. Approvals expire at the next interval boundary; AI latency does not extend them. A fill is a coarse simulation at a later completed close, with price and risk checks repeated. A skipped trade is normal.
6. **Pause entries** blocks entry and cancels pending fills at recheck; exits still operate. To end a session early, pause and request exits for open positions, then keep monitoring until later observations resolve them. At the scheduled close the worker attempts intraday exits. Without closing data positions remain unresolved. Do not invent a closing price.
7. Ctrl+C stops a process. Stop both UI and worker when finished. SQLite preserves positions and pending decisions. On restart the worker backfills gaps (up to a 28-day retrieval window), updates exits, cancels missed entry opportunities, and does not retroactively trade while you were offline. Longer outages require rebuilding a fresh run with verified history. A feed error pauses entries; fix it, check status, then deliberately resume.

No guarantee of monitoring while Windows sleeps. Observe for at least four to eight weeks as an initial checkpoint, report sample count and conditions, and extend observation as needed. Keep the INR 500–800 weekly aspiration separate from risk settings. Record software costs before comparing net economics.

## Stage E — future integrations

External broker demos, real-money execution, public hosting and cloud operation are outside this release. This app contains no real-order endpoint or enabling switch. Whether an external demo supports the required Indian equities must be verified separately.
