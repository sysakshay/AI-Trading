# Architecture and strategy contract

Version 0.2.0; schema 2; execution policy `completed-close-v1`; retrieval version 1, prompt version 2.

## Version 0.2 additions and corrections

`research.py` independently implements recorded supporting/opposing/risk lenses, a prior-only regime diagnostic and replay evidence import. It does not call an LLM. Evidence must be published and available by the decision time, is capped at eight items from the preceding 30 days, and is frozen in candidate evidence. No later enrichment of an old candidate is allowed. Forward evidence imports are blocked because historical availability declarations cannot establish actual forward ingestion.

Regime warm-up is `ATR period + 21` bars (35 by default). Normalize Wilder ATR by close, then compare the current value with nearest-rank 20th/80th percentiles of the preceding 20 normalized observations, excluding current. Trend labels use the existing SMA/three-bar slope. These are descriptive labels, not calibrated probabilities. Optional `avoid_high_volatility` blocks UNKNOWN/HIGH_VOLATILITY proposals and creates a different settings version; `observe` is the default and does not alter trade eligibility.

`experiments.py` records data/configuration/evidence identity and fixed rules/mock/experimental-filter variants in three isolated historical accounts. The same completed-close fill engine and financial bounds apply. Completed experiment requests are idempotent. Interrupted RUNNING/FAILED groups retain their partial evidence; automatic resumption is not implemented (create a new source run to rerun). No paid historical calls are made and no true out-of-sample claim follows from these fixture comparisons.

Schema 2 adds research items, experiment manifests/members, operating expense records and worker ownership. `migrations/002_research.sql` is applied transactionally after a schema-1 backup. `PRAGMA user_version` accepts up to 2; restore accepts schema 1 or 2 and subsequent open upgrades old backups. Existing records/strategy versions are preserved. The older schema discussion below describes the original entities; these additions supersede its version-1-only upgrade note.

Period reports now use `[start,end)` throughout trading/expense calculations, reconstruct cash and open positions before end, and restrict drawdown/exposure to the selected observations. Both closed-trade costs (attributed at exit) and fees paid within the period are exposed. Candidate-state counts intentionally show current lifecycle state grouped by creation period, not reconstructed historical decisions. Operating expenses are saved manual INR allocations and never change virtual trading cash. USD AI reservations remain distinct from invoices.

Workers renew an ownership-tagged lease between requests and processing steps. A worker which loses ownership cannot clear the new owner's status. Feed freshness uses time after retrieval/before processing instead of the initial request timestamp. The single paid-review prompt weighs recorded opposing evidence and gaps; it does not claim multiple independent LLM votes. Old contexts remain immutable. Context-budget trimming removes oldest outcomes first and recomputes selected-sample statistics.

## Ownership

`domain.py` contains validated configuration, candles, pure indicators, costs and sizing. `engine.py` owns transactional account actions. `ai.py` only reviews candidates. `provider.py` only requests metadata and candle data using GET. `worker.py` owns forward scheduling. `app.py` displays records and invokes explicit user actions; reruns alone cannot scan, approve, fill or call AI. `cli.py` runs deterministic research and maintenance operations.

SQLite uses WAL, foreign keys, 15-second busy timeout, fresh connections and `BEGIN IMMEDIATE` for mutations. Dashboard and worker may each perform short transactions; the SQLite writer lock serializes them. A persisted five-minute worker lease prevents duplicate workers from fetching concurrently for one run. Network calls occur outside write transactions. Paid request reservations commit before the network call. A crash after that commit leaves REQUESTED/unknown; it is not retried automatically or refunded, because the provider may already have billed it.

## Persistence and upgrades

`src/schema.sql` is migration 1 and contains actual schema, keys and indexes. Runs combine configuration/strategy/account concepts; sessions store reference equity and latched limits. Candles store immutable payloads and retrieval times. Candidates, reviews, decisions, orders, positions, fills, ledger, events and equity record independent lifecycle facts. Reports/outcomes derive from those records, not invented summary values.

Candidate uniqueness is `(run, instrument, completed timestamp)`; every run has exactly one immutable strategy version, making it equivalent to including that version in the key. Each candidate can have one decision per revision, one order and one position. Fill uniqueness is `(position, side)`. No externally supplied SQL table names are accepted by the UI. Input snapshots are never overwritten by a provider correction; forward correction events pause entry.

`PRAGMA user_version` rejects newer schemas. For a future migration: stop worker, use SQLite backup API, apply ordered SQL within a transaction, validate foreign keys/account reconciliation, then increment version. Restore validates integrity and refuses existing destinations. No destructive reset exists.

## Price/time/data contracts

- Storage: timezone-aware ISO strings normalized to Asia/Kolkata, prices/accounting in integer paise. Decimal handles rupee conversion, tick rounding, fee ceiling and risk budgets. Floating-point indicator arithmetic is acceptable for derived averages; all executable levels round to the instrument tick.
- A timestamp means **bar end**. Provider start timestamps gain 15 minutes. CSV timestamps must already mean end and include an offset. No ambiguous naive timestamps, inferred volume or forward-filled prices.
- CSV contains stable instrument ID, display symbol, source, interval, adjustment and tick metadata. All rows fail as a batch when any row is invalid; the importer returns row-numbered errors. Duplicate observations, invalid OHLC, missing/negative volume, nonpositive prices and unsupported intervals fail validation.
- NSE calendar comes from pandas-market-calendars plus an explicit user-verified session schedule. Ordinary times are 09:15–15:30 IST; holidays and special sessions must be checked against exchange circulars. The three synthetic dates have an explicit fixture schedule. Only complete 15-minute slots wholly inside a session are accepted. A final short interval is excluded from indicators/signals and cannot fabricate a close.
- All scheduled bars between the first observation and decision must exist for each instrument. A missing bar blocks its candidates until a new complete dataset/run is supplied or forward backfill repairs the gap. Other instruments can continue. Warm-up does not fill absent history.
- Adjusted prices and corporate-action processing are not implemented. Import only verified unadjusted data without affected intervals; exclude splits/dividend adjustment inconsistencies and rebuild independent runs. Historical membership is not supplied; current-watchlist survivorship bias remains.

## Exact experimental rules

Default: 20-close SMA above its value three bars earlier, current close above SMA, current close strictly above preceding 20 highs, current volume at least 1.5 times preceding 20 mean volumes (current bar excluded). ATR uses Wilder smoothing: seed is the arithmetic mean of the first 14 true ranges beginning with the second bar; each subsequent ATR is `(13 * prior ATR + current TR) / 14`. TR is max(high−low, abs(high−previous close), abs(low−previous close)). At least 23 bars are required for all rules. Seed convention is deliberate and independently fixture-tested. Maintained indicator libraries were not added because a small directly specified SMA/ATR implementation avoids differing seed conventions.

Stop = reference close minus 1.5 ATR rounded down to tick. Target = reference plus 2 times the rounded stop distance, rounded up. These absolute levels persist. The reference is not an entry fill. Full settings are frozen per run, bounded through Pydantic, and hashed into a new version. No tuning process runs automatically. Fixed intraday volume baselines ignore time-of-day patterns; this is a known experimental limitation.

## State transitions

```text
Rules: completed signal → AWAITING_APPROVAL
AI: completed signal → PENDING_REVIEW → AWAITING_APPROVAL | REJECTED | FAILED
AWAITING_APPROVAL → APPROVED | REJECTED | EXPIRED
APPROVED → order PENDING_FILL → FILLED | CANCELLED
FILLED → open position → closed position (separate lifecycle)
```

`CREATED` is represented by immutable creation evidence/event rather than a separate lasting candidate state. Revision must match exactly. Approve/reject are one transaction, second clicks are no-ops. Expiry is next interval or session close minus 30 minutes, whichever is earlier. Approved orders may complete at the next boundary after the approval window ends; they must still be no more than 15 minutes old, on the same session, before the entry cutoff and eligible at execution. No proposal is silently revised.

## Fill policy and risk

Fills use the **next completed close strictly after approval**. This deliberately coarse simulation is confirmed when that full bar arrives. It never uses a previously observed open for new entry. Stops/targets begin on later bars after the entry close. Unknown within-bar sequencing uses stop-first. A gap below stop uses min(open, stop), then adverse slippage. A target limit fills at target (no favorable gap improvement), then conservative exit-cost/slippage modeling. Manual exits use the next completed close, unless an earlier modeled stop/target resolves the position. At session close an available completed bar can close a position. If absent, the position remains unresolved and the next session's first observed open resolves the overdue session exit; confirmation waits until that bar arrives.

Partial fills and order-book queue dynamics are not modeled. Quantity is capped at 1% of observed bar volume. This is a configurable liquidity assumption, not broker equivalence. Costs default to an explicitly estimated 10 basis points per side plus optional fixed paise; slippage is 2 basis points adversely, rounded to tick. One basis point is 0.01%. These are not a complete Indian brokerage/STT/GST/stamp-duty or personal income-tax calculation. Verified instrument-specific fee schedules can replace the pure `fee` function later.

Sizing chooses the largest affordable whole-share quantity satisfying 0.5% planned per-trade loss, 1% aggregate planned open risk, 1% volume participation, costs and net reward/risk ≥1.5. Estimated stop execution and target execution include slippage. Planned stop loss is not a maximum loss: gaps can exceed it. Cash is reserved only when approved; rejected/expired proposals reserve nothing; cancelled/filled orders release reservations. Entry price, cash, aggregate risk, existing positions, stale marks, daily trade count and daily halt are rechecked at fill. Max positions includes pending entries; max new fills is three per session; no leverage or shorts.

Equity = cash + last observed market value of open positions. Unrealized metrics include paid entry costs and exclude unknown future exit charges. Session reference equity uses carried latest marks before the first session observation; stale carried marks flag uncertainty and block entries until current observations arrive. Daily loss includes realized/unrealized change and is latched for the session even after recovery. Exits continue under halt, pause and AI failure.

## Backtesting library evaluation and research integrity

[Backtesting.py](https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html) was evaluated before building the simulator. Its documented market-order default is next open (or current close with `trade_on_close`), with configurable commissions and its own broker lifecycle. Durable human approval, later-close execution, reserved cash, latched session constraints and SQLite restart semantics would require substantial adapters. This release uses one compact event engine in replay, backtest and forward modes instead. This is an explicit deviation, not a claim of broker-grade simulation.

Automatic historical policy: process instruments in lexical ID order, approve every eligible rules-only candidate, or only successful PAPER_TRADE mock reviews, at the signal completion time; rejected capacity/risk attempts are journaled. Both baseline and mock get the same next-close timing. The human run is separate and discretionary. Live AI completion time and latency are recorded; any forward comparisons must separately report latency effects. Automated matching of live forward comparison cohorts is not yet provided; do not attribute timing differences solely to AI selection.

Historical date windows are configurable through CSV UI/CLI. Save all parameter configurations, choose a chronological development interval, freeze the version, and use a separate untouched test run. Repeated inspection/tuning invalidates “untouched” status. No optimization, multi-regime evidence or walk-forward claim is made from three synthetic days. Historical AI could know subsequent events through training; mock comparisons test plumbing only. Economic inputs are saved manual allocations, not provider invoices.

## Durable AI context

Only qualifying candidates reach the reviewer. Context includes current evidence, planned levels/quantity/costs, cash/equity/reservations/open positions, session risk, five recent bars, and the newest 20 known closed outcomes from the same run/strategy without filtering winners. Counts/losses/net sum describe that selected sample, not all-time performance. No cross-account context leakage. Context has a 24,000-character hard bound; over-limit requests fail closed rather than dropping risk facts. The exact packet, prompt/model/version, request/response times, status, usage and conservative allowance persist. Stable cache identity covers candidate, snapshot, version, prompt and model. Unknown or failed calls are never repeated automatically.

Review schema permits only candidate ID, WATCH/SKIP/PAPER_TRADE, bounded evidence/risk lists and summary. Wrong identity, refusal, malformed output, timeout or late review blocks assisted entry. No confidence percentage, autonomous financial calculation, credential access, or order tool is exposed. SDK retries are disabled to avoid duplicate paid requests. The default budget is zero. Price guard currently supports only documented `gpt-5-mini`; model configuration is explicit, but unreviewed model pricing blocks calls.
