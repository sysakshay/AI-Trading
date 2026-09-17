# Offline demonstration report

Generated 2026-09-16 from invented candles; policy completed-close-v1. Starting virtual cash INR 10,000. These are scenario checks, not evidence about NSE returns.

| Policy | Trades | Gross P&L | Transaction costs | Net P&L |
|---|---:|---:|---:|---:|
| Rules-only | 2 | INR 4.80 | INR 9.92 | **INR -5.12** |
| Mock AI | 2 | INR 4.80 | INR 9.92 | **INR -5.12** |
| Failing mock AI | 0 | INR 0.00 | INR 0.00 | INR 0.00 |

Rules/mock: 24 shares per position at INR 103.05. One exits at INR 99.95 after a stop gap; one at INR 106.35 at the modeled target. Net loss INR 79.28, net win INR 74.16. Win rate 50%, expectancy INR -2.56, profit factor about 0.935. Maximum sampled equity drawdown INR 7.36: positions offset in the same bar snapshot, which does not reveal intrabar drawdown. No remaining positions.

API/data spend: zero. No subscriptions purchased. Future operating expenses must be reported separately. No useful inference about the INR 500–800 weekly aspiration is possible from this fixture. JSON reports preserve curves and data/configuration identity. UUIDs vary; deterministic financial results do not. Human replay is a separate discretionary account.
