# Daily operation and weekly review

## Before a session

- Confirm SAMPLE, REPLAY, BACKTEST or FORWARD and the correct saved account.
- Check virtual cash, strategy version, fees, planned risk and entry-pause status.
- Forward only: verify token validity, exchange session/special-session schedule, last successful fetch, latest completed timestamp and data delay. Keep Windows awake and the worker running.
- Confirm AI policy. Mock is not a connected model. Never increase risk or paid budget to meet an income target.

## During a session

- Read measured evidence, original stop/target, estimated costs, expiry and AI status.
- Approve exactly the intended proposal or reject it. Approval reserves cash; it does not guarantee a fill.
- Watch open positions and stale-mark/error messages. Pause entry if investigation is needed; keep exits monitored.
- Do not invent trades when none qualify. Do not treat a model explanation as a probability of profit.

## End of session

- Pause new entry and inspect whether closing observations resolved every open position.
- If an exit is pending, keep monitoring or record that shutdown leaves it unresolved.
- Export the run and make a consistent backup. Shut down UI and worker with Ctrl+C only after noting remaining exposure.

## Weekly review

- Report completed trades, dates/conditions, realized and unrealized results, costs and missing data separately.
- Inspect every losing trade, gaps beyond planned stops, maximum equity decline (drawdown), longest loss streak and skipped/error counts.
- Compare isolated rules, mock/AI and human runs with the same data, portfolio constraints and fill timing. Explain AI latency separately.
- Subtract actual allocated data/API/other expenses before comparing economics to INR 500–800/week. That figure is an aspiration, not a required return.
- Keep the strategy unchanged for a predeclared observation interval. A change creates a new version and a new evaluation period.
- Four to eight weeks is a checkpoint. Few trades, narrow market conditions or uncertain data mean more observation is needed. Software passing tests is not permission for real-money trading.
