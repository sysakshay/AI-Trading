# Repository review and integration — 16 September 2026

## Outcome

Reviewed all three default-branch source snapshots, compared their relevant implementations with this application, and delivered version 0.2. The useful common architecture is **data → measured evidence → decision → execution constraints → durable outcomes → evaluation**. They do not all use the same kind of AI, serve the same market, or provide evidence of a profitable strategy.

This is a targeted source review, not an exhaustive security audit or a reproduction of each project's results. Upstream dependencies, services and trading commands were not executed. No registration, subscription, external order or paid model call was made.

## Exact versions reviewed

| Repository | Reviewed commit | Main focus at this snapshot |
|---|---|---|
| [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents/tree/be952b8eccb49720509af544c6675233bc1f10d0) | `be952b8eccb49720509af544c6675233bc1f10d0` | Specialist LLM analysts, opposing research arguments, risk/portfolio review, structured output and dated memory |
| [aaryansinha16/AI-trader](https://github.com/aaryansinha16/AI-trader/tree/de830f95c462c8142acb8191c62d3404868484aa) | `de830f95c462c8142acb8191c62d3404868484aa` | NSE options research/execution, tick features, trained ML, regime selection and replay |
| [HKUDS/AI-Trader](https://github.com/HKUDS/AI-Trader/tree/d03ff6c056b32ced735adf7c19ed8175adb1c8df) | `d03ff6c056b32ced735adf7c19ed8175adb1c8df` | Agent-facing trading/community platform, signal sharing and experiment infrastructure |

Full shallow source snapshots are under `research/upstream/`, excluded from this app's source-control inputs. Provenance is recorded in `research/reviewed-repositories.json`. HKUDS's current default branch should not be confused with an earlier research-benchmark implementation or with an NSE-specific simulator.

## Comparison and choices

| Area | What the sources offer | Our previous limitation | Integration delivered |
|---|---|---|---|
| Research reasoning | TradingAgents separates technical/news/fundamental analysis and opposing arguments | One short generic review; no readable evidence gaps | Frozen supporting/opposing/risk research packet, measured references, missing-source coverage and AI prompt v2 |
| Time-aware evidence | TradingAgents filters dated content and resolved memory | Price/outcome cutoffs existed, but no external research contract | Validated news/fundamental JSON imports with publication **and availability** cutoffs, immutable candidate evidence |
| Market conditions | NSE AI-trader computes regime diagnostics and maps strategies | No visibility into changing volatility/trend | Prior-only Wilder ATR/price diagnostics; regime breakdown of results; optional separately versioned filter |
| Experiments | HKUDS stores variants, outcome snapshots and exports | Comparison labels lived only in the browser session | Persistent SQLite experiment manifest, isolated accounts, matched candidate/state export and idempotent completed experiments |
| Economics | All need explicit evaluation/operating assumptions | Expense allocations vanished on refresh | Saved INR operating expense journal, kept separate from virtual trading cash |
| Operations | HKUDS separates workers and renews singleton ownership | Fixed lease could expire during long work; freshness used fetch-start time | Ownership-checked lease renewal and freshness checked after retrieval |
| Reporting | Research platforms need consistent measurement windows | Daily/weekly P&L used period trades but latest cash and whole-run drawdown | Half-open period reports with historical cash, positions, equity, expenses and selected-window drawdown |

### What we were doing wrong or incompletely

1. **The earlier AI explanation was too narrow.** It lacked a structured opposing case and explicit news/fundamental coverage. The new packet improves traceability; it does not make several code-generated opinions independent model votes.
2. **Period reporting was misleading.** A historical report could show later account cash or position state. It now reconstructs values at the selected exclusive end. Closed-trade fees versus fees actually paid during the period are separate fields.
3. **Experiments and expenses were not durable enough.** Results now survive application restart and export with their data/configuration identity.
4. **Forward freshness was measured too early.** A slow request could make data stale between request start and use. The worker now checks after retrieval and before processing each boundary.
5. **Our evidence base remains too small.** Synthetic tests prove software behavior, not trading value. No credible reason exists yet to train XGBoost/RL, calibrate profit probabilities, or increase capital/risk.

### What we should keep

Keep integer-paise accounting, conservative gaps/ambiguous bars, transactional idempotency, zero-share rejection, later fills, manual authority, strict model outputs, isolated accounts and a valid no-trade result. Extra indicators or additional model conversations do not replace those guarantees.

In the reviewed NSE source, `risk/risk_manager.py` floors quantity to at least one, and parts of `backtest/backtest_engine.py` similarly floor lots. That is unsuitable for our rule that insufficient affordable risk must yield zero shares. This is a specific source observation, not a claim that every upstream execution path is unsafe.

The reviewed `models/train_model.py` uses chronological `TimeSeriesSplit`, but the split helper has no explicit label-horizon purge. Before adopting forward-return labels, we would require a gap/purge at fold boundaries and an untouched evaluation set. We did not import its trained-model behavior or claim its reported probabilities are calibrated for our equities.

### Features deliberately not brought across

- Real broker order paths, options/futures/crypto, copy trading, public signal publishing and remote agent registration are outside our local long-only paper scope.
- Kelly sizing, reinforcement-learning exits and automatic parameter changes require independent data and validation; they would change the financial experiment substantially.
- A full LangGraph multi-model debate can multiply cost and latency. Version 0.2 uses deterministic evidence lenses plus the existing **single** optional paid reviewer. It is not advertised as independent multi-agent consensus.
- TrueData, Alpha Vantage, social feeds and cloud databases are not prerequisites. No speculative connector purchases were added.
- Live historical news/fundamental ingestion is not implemented: imported records are replay-only and need honest availability timestamps. Missing sources are visible. Evidence cannot be backfilled into already-created candidates.

## New features in practice

1. Start a fresh offline demo. Each candidate shows **Research desk**, its supporting/opposing case and absent source coverage. Existing candidates remain unchanged.
2. In **Evaluation**, inspect **Results by market condition** and use **Run saved policy comparison**. Three separate virtual accounts run: original rules, mock research and the experimental regime filter. Results are saved and exportable.
3. The regime filter is opt-in under new-run settings. It blocks high relative volatility and UNKNOWN warm-up states. It is a hypothesis, not a recommended trading strategy. Default `observe` leaves rules unchanged.
4. In **Settings & data**, create a new unadvanced sample run, then import `fixtures/research-example.json` before the first candidate. Advance to the proposal. The source is explicitly synthetic. Direct public source URLs must not contain credentials, query parameters or fragments.
5. Enter actual allocated operating expenses in **Evaluation**. They persist and appear in economic results but do not subtract from virtual trading cash.

The comparison fixture remains **INR -5.12** for rules and mock. The regime filter makes zero trades because the signal precedes its longer warm-up. A no-trade result of zero is not evidence that the filter performs better.

## Reuse and licenses

TradingAgents includes Apache-2.0; aaryansinha16/AI-trader includes MIT. HKUDS's README advertises MIT, but the reviewed root tree has no LICENSE file. We therefore used architectural ideas and wrote our own implementation; no upstream source, prompts, models, data or assets were copied into the runtime. No new third-party runtime dependency was added. Local upstream clones retain their own original files for inspection.

## Source paths inspected

- TradingAgents: `graph/analyst_execution.py`, `agents/schemas.py`, `agents/utils/memory.py`, `dataflows/date_window.py`, `graph/reflection.py`, README and LICENSE.
- NSE AI-trader: `strategy/regime_detector.py`, `models/model_monitor.py`, `models/train_model.py`, `risk/risk_manager.py`, `backtest/backtest_engine.py`, README and LICENSE.
- HKUDS: `service/server/worker.py`, `service/server/experiment_metrics.py`, `service/server/experiments.py`, `service/server/fees.py`, `research/scripts/compute_metrics.py`, README and repository tree.

Upstream designs informed the changes; upstream profitability, API access and model quality were not verified. See [CONNECTION_CHECKLIST.md](CONNECTION_CHECKLIST.md) for the only account actions you need to consider.
