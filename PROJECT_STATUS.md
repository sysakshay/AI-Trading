# Project status — 2026-09-16

## Version 0.2 repository comparison update

Reviewed the three requested repositories at recorded commit hashes; see `docs/REPOSITORY_COMPARISON.md` and `research/reviewed-repositories.json`. Independently implemented research lenses, historical evidence availability contracts, regime diagnostics/optional filter, persistent experiments and expenses. Corrected historical report boundaries and worker receipt-time freshness/ownership. Existing `data/paper.db` migrated to schema 2 with an automatic schema-1 backup; four existing runs preserved. No upstream trading commands, account registrations or paid requests executed. No extra runtime dependencies added.

**65 tests passed** in 39.28 seconds; no failures/skips. Server health is `ok` at http://localhost:8501. Details and remaining connections are in `reports/TEST_SUMMARY.md` and `docs/CONNECTION_CHECKLIST.md`. The earlier unsaved-expense limitation and schema-1-only description are superseded. Live forward matched cohorts, real external access, visual browser inspection and prospective validation are still pending.

**Working offline application delivered. Connected services remain unverified.**

Empty Windows workspace inspected; no existing user work or AGENTS instructions found. Python 3.14.6. No paid requests, subscriptions, sign-ins or real-money operations performed.

Local dashboard running at **http://localhost:8501** in the current session. Restart from this folder with `powershell -NoProfile -ExecutionPolicy Bypass -File .\start_app.ps1`.

## Design decisions

- Local Streamlit UI, SQLite WAL, one atomic writer transaction per action.
- Integer paise for accounting, Decimal for ticks and fees.
- Synthetic offline fixtures; manual replay and deterministic automatic backtests isolated by run.
- Coarse bar-close execution: after approval, fill at the close of the next completed bar strictly later than approval. Pending orders expire only if not approved before proposal expiry; execution revalidates original levels and all limits. No use of a known past open. Stops start on subsequent bars.
- Pending approvals reserve no cash; approved orders reserve conservative cash/risk until execution or cancellation. Final sizing rechecks at execution.
- Explicit calendar schedules, no weekday-only calendar. Special sessions require a supplied verified schedule.
- Backtesting.py evaluated: default next-open fills and strategy-owned broker don't directly express durable manual approval, expiry, SQLite reservations and restart. Use one small tested event engine for all modes; details in docs/ARCHITECTURE.md.

## Implemented and verified

- Source, installed libraries, exact transitive pins, Windows launcher and beginner guides.
- Streamlit 1.64.0, Plotly 7.1.0, Pydantic 2.13.5, OpenAI SDK 3.14.0, pytest 9.1.1, pandas-market-calendars 5.4.0 installed on Python 3.14.6 x64. `pip check` passes.
- Strategy, sizing, risk/session limits, fees/ticks/slippage, later-close execution, conservative gaps, atomic ledger, reservations and restart.
- Offline scenarios, CSV replay, automatic backtests, rules/mock comparison, human decision journal, charts and reports.
- SQLite schema 2, transactional migration/backup, WAL, foreign keys/uniqueness, snapshot preservation, validated restore/export.
- Bounded context and known-outcome memory, strict reviews, official Responses SDK adapter, zero default paid allowance and persistent request reservation.
- Read-only Upstox adapter and independent forward worker with explicit calendar/rights/delay prerequisites, pause and conservative offline recovery.
- **65 automated tests passed** in 39.28 seconds; no failures/skips. Includes ordinary and saved-comparison Streamlit AppTest workflows. Server health returned `ok`; source compiles; dependency consistency passed.

## Evidence

- `reports/test-results.xml` and `reports/TEST_SUMMARY.md`.
- `reports/demo-rules.json`: two synthetic trades, gross INR 4.80, fees INR 9.92, net **INR -5.12**.
- `reports/demo-mock.json`: same values; validates plumbing, not model skill.
- `reports/demo-mock_fail.json`: zero trades, review failures block entry.
- `fixtures/sample.csv`, `fixtures/invalid.csv`, and provenance notes.

## Pending access and residual limitations

| Item | Missing evidence/action | Smallest next action |
|---|---|---|
| OpenAI | Private project key, API account credit/eligibility, explicit budget; real smoke test not run | Complete optional Stage B when desired; otherwise keep zero budget |
| Upstox | Eligible account/token and actual received history/intraday timestamps | Generate read-only token privately and run Stage C data check |
| Forward eligibility | Local retention/display rights, adjustment/corporate-action conventions, current calendar and ≤60-second observed delay | Confirm terms and measure several boundaries before setting attestations |
| Visual browser QA | Browser runtime returned no available browsers (`[]`) | Open local URL; desktop/narrow-window screenshots and keyboard review remain unexecuted |
| Prospective evidence | Weeks of forward observations have not elapsed | Start observation after prerequisites; count actual trades/conditions |

No partial fills/order-book simulation, quote feed, corporate-action adjustment, verified liquidity ranking or historical membership data. No real historical market dataset is bundled. Live forward cohort matching/automatic baseline-versus-live-AI selection analysis is not implemented: separate runs and recorded latency are available, while saved offline comparisons are implemented. Do not attribute fill-timing differences to AI selection. Operating expenses are saved manual allocations, not imported invoices. Special sessions need explicit calendar verification. These limitations are described in the architecture and setup guides.

## Phase record

1. Environment/specification: complete; financial/time contracts documented.
2. Offline workflow: passed automated end-to-end and restart checks.
3. Integrity/replay: deterministic accounting/timing/risk/leakage checks passed.
4. Memory/AI: mock and API-shaped tests passed; actual access pending.
5. Provider: official research/read-only adapter implemented; actual entitlement pending.
6. Forward: machinery/recovery fixture tests passed; live observation and matched comparison cohorts pending.
7. Handoff: guides, launcher, pins, reports and maintenance paths delivered; browser visuals blocked.

## Reproduce checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=reports/test-results.xml
.\.venv\Scripts\python.exe -m src.cli --db data\verification.db demo-report
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q src app.py
```

Next user action: open the local URL, click **Start offline demo**, approve `DEMO-WIN`, and advance two candles. No account setup required.
