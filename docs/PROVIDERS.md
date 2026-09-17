# Market-data research

Official documentation checked **2026-09-16**. Documentation review is separate from account/API verification. No account entitlement, live delay, or data license was actually tested in this session.

| Requirement | Upstox (implemented read-only adapter) | Kite Connect (researched alternative) |
|---|---|---|
| NSE cash identity | NSE_EQ instrument keys; official JSON master. Keys are preferred over reusable exchange tokens | NSE instrument tokens from instrument master |
| 15-minute history/volume | V3 minutes/15 with OHLCV; documented minute history from January 2022; 1-month request window at 1–15 minute intervals | `15minute` OHLCV; historical availability varies by instrument, exact usable depth must be queried |
| Cost | Analytics Token documented free; account/other services may have their own charges | Connect streaming + historical plan listed INR 500/month; free personal tier is not this data package |
| Authentication | Read-only Analytics Token, one-year validity; standard OAuth alternative exists | API key/secret, browser login and session token; token expires next day at 06:00 unless invalidated earlier |
| Account eligibility | Developer Apps access required; user-specific and non-broker-account eligibility unresolved | Developer and eligible Zerodha account access must be confirmed by user |
| Delivery delay | REST completion/publication delay not guaranteed here; measure received timestamp at boundaries | Streaming advertised realtime; historical candle publication delay still needs measurement |
| Rate limits | Other standard APIs: 50/sec, 500/min, 2,000/30 min; adapter intentionally uses ≤1/sec and bounded retries | Historical candles: 3/sec; quote: 1/sec |
| Corporate actions | Adjustment convention not established by reviewed pages; affected intervals excluded | Adjustment convention/point-in-time corrections require provider confirmation |
| Retain/display rights | Explicit local snapshot/private-display rights not established; confirmation required before retention of connected datasets | Must confirm applicable exchange/provider terms; no redistribution assumed |

**Recommendation:** start offline, then use Upstox Analytics if the user is eligible and approves its terms. Its read-only route and stated zero token cost fit this simulator; no order permission is needed. Do not buy Kite or another plan until its actual access benefit justifies the cost. No Twelve Data/OANDA NSE assumption is made.

## Official sources

- [Upstox Analytics Token](https://upstox.com/developer/api-documentation/analytics-token/): scope, generation, validity and stated free use.
- [Historical V3](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/) and [intraday V3](https://upstox.com/developer/api-documentation/v3/get-intra-day-candle-data/): candle contracts and endpoints.
- [Instrument master](https://upstox.com/developer/api-documentation/instruments/): NSE JSON identifiers and metadata.
- [Rate limits](https://upstox.com/developer/api-documentation/rate-limiting/) and [authentication](https://upstox.com/developer/api-documentation/authentication/).
- [Upstox terms](https://upstox.com/terms-of-use-and-privacy-policy/): review with provider; not treated as an affirmative data-redistribution license.
- [Kite plan pricing](https://zerodha.com/products/api/), [historical data](https://kite.trade/docs/connect/v3/historical/), [rate limits](https://kite.trade/docs/connect/v3/exceptions/), [session authentication](https://kite.trade/docs/connect/v3/user/).
- [NSE market timings](https://www.nseindia.com/static/market-data/market-timings), [holiday calendar](https://www.nseindia.com/resources/exchange-communication-holidays/), [2026 special budget-session circular](https://nsearchives.nseindia.com/content/circulars/CMTR72349.pdf). A weekday-only calendar would miss special sessions.

## Data operation and limitations

The provider interface supports lookup, history and incremental completed bars. Requests are GET-only, with 20-second timeout, ≤3 attempts for transient errors, exponential backoff and no auth retries. Stored snapshots are a reconstruction cache, so retention rights are a prerequisite. No shared/public cache exists. Error messages omit tokens.

The connected watchlist is selected from actual NSE_EQ/EQ metadata, up to 20 IDs. This release does not have dated liquidity rankings; the example `RELIANCE` is an access-test symbol, not a recommendation or claim of highest liquidity. Obtain and document a turnover/volume study before choosing a research universe. Historical membership remains unavailable.

Forward mode needs observed candle-end-to-receipt age ≤60 seconds, verified sessions, adjustment basis and rights. OHLCV publication is delayed confirmation of a coarse simulated close; it is not an executable live quote. Longer delays block the intended workflow and require replay. These data checks have not been completed with a real account.
