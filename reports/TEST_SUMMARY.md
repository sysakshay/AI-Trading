# Verification summary — 2026-09-16

**65 passed, 0 failed, 0 skipped**, 39.28 seconds on Windows/Python 3.14.6, version 0.2.

Command: `.\.venv\Scripts\python.exe -m pytest -q --junitxml=reports/test-results.xml`

## Repository-integration verification

The original 45 checks remain; 20 additional cases cover timestamped evidence and immutable snapshots, validation/atomic imports, prior-only regime thresholds and warm-up, unchanged default financial results, opt-in gating, persistent/idempotent experiments, historical period cash/positions, saved expenses, schema-1 migration/backup, delayed feed receipt, worker ownership loss, invalid paid budgets and restart-visible experiment UI.

`reports/repository-integration-experiment.json` records rules and mock at INR -5.12 and the optional regime filter at zero trades due to insufficient warm-up. This establishes no financial superiority. The real existing database migrated to schema 2 with four runs preserved. No new runtime dependencies; `pip check` and compilation pass. The version 0.2 local server at `http://localhost:8501` returned health `ok`.

Upstream repository programs/tests were not executed; only their source/documentation was reviewed. The app's OpenAI and Upstox calls remained mocked in tests; no external account connection or paid request occurred. Browser discovery again returned no browsers, so visual screenshots remain unexecuted. Both ordinary workflow and persistent-comparison workflows ran through Streamlit AppTest.

The first run encountered Windows ACL restrictions on an old OS temporary directory. Pytest now uses disposable project-local `.pytest-tmp` and `.pytest-local-cache` directories. A subsequent added-test scoping error was fixed. The final complete suite above passed; no earlier failed run is presented as success.

## What ran

- Independent SMA/ATR/window expectations, warm-up, deterministic candidate and financial results.
- Invalid OHLC, missing volume, naive timestamps, duplicates, ordering, missing scheduled bars and holiday exclusion.
- Quantity/cash/aggregate/liquidity/fee boundaries, daily halt/trade limit, pause, stale marks, reservations and original-level rechecks.
- Decision-before-fill, revision/expiry handling, concurrent double approval, restart, stop-first and adverse gaps, unresolved missing exits.
- Exact cash ledger/report reconciliation, rollback, isolated modes, backup/restore and secret-free export.
- Known-outcome memory, 20-record cap, losing cases, immutable saved contexts and future-outcome exclusion.
- Strict response schema, wrong identity, refusal, malformed output, timeout, missing key, exhausted budget and cached/no-repeat requests.
- Mock HTTP candle conversion/completeness, auth failures, bounded retries, forward prerequisites and offline catch-up cancellation.
- Streamlit AppTest: start demo → approve → advance → exit without UI exceptions.
- Deterministic report generation: rules and mock net INR -5.12; mock failure zero trades.
- `pip check`: no broken requirements. `compileall`: passed. Running local server health endpoint: `ok`.

## Mocked or not executed

All OpenAI/Upstox network interactions in tests were mocked. No real key/entitlement/credit test, paid call or real-time feed verification occurred. Price fixtures are synthetic. No several-week prospective validation or untouched real historical evaluation occurred.

Browser runtime bootstrap succeeded but browser selection failed; discovery returned `[]`. Therefore rendered screenshots, desktop/narrow viewport inspection and keyboard-accessibility checks were **not executed**. Streamlit's interaction test is not a substitute for visual browser verification.

## Development failures resolved

Initial tests correctly cancelled an entry when modeled exit slippage pushed net reward/risk below the threshold. The synthetic eligible-fill scenario was adjusted; financial gates were retained, and a separate crossed-level cancellation test remains. A Streamlit AppTest relative-path issue was fixed by using the absolute app path. Final suite has no failures.
