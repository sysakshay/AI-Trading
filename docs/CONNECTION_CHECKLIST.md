# What you need to connect after this upgrade

## Nothing is required for the new offline features

The research desk, market-condition diagnostics, saved comparisons, evidence imports, expense journal and reports all work without accounts or API keys. Run `start_app.ps1`, open **http://localhost:8501**, and choose **Start offline demo**.

## For actual NSE market data

You need your own eligible Upstox access and a **read-only Analytics Token**. Enter it privately as `UPSTOX_ACCESS_TOKEN` in `.env`. Then complete the history/intraday checks in [USER_SETUP.md](../USER_SETUP.md), including observed delay, current sessions, adjustment conventions and permission to retain/display data locally. This upgrade did not verify your account or obtain market data.

You do not need TrueData or Zerodha keys just because the compared repositories use them. The current adapter remains Upstox. The example watchlist is not a verified liquidity ranking.

## For real AI explanations

You need an OpenAI Platform project API key, eligible API billing/credit, and a budget **you explicitly approve**. Enter `OPENAI_API_KEY` privately in `.env`; never send it in chat. The run must use the `openai` review policy. Leave `AI_BUDGET_APPROVED=false`, `AI_DAILY_USD=0` and `AI_DAILY_REQUESTS=0` until you choose to enable usage. Existing saved runs keep their selected policy.

There is still one optional paid review per qualifying candidate, subject to caching and caps. The research lenses do not add extra paid agent conversations. No live smoke test or payment was performed. A key being configured is not proof of a successful connection.

## For news or company fundamentals

No new API is mandatory or connected. You can use the replay JSON importer with source summaries you have permission to use and honest publication/availability timestamps. Import before the first candidate into a new offline run. Never insert today's company information into a past decision.

Automatic NSE news/fundamental coverage would require a separately verified provider with the correct instruments, timestamps and rights. Until that exists, the dashboard says this evidence is unavailable. Do not buy an Alpha Vantage/news plan solely for this upgrade.

## Your next action

Use the new offline demo first. When you want to move to connected paper observation, configure **Upstox**, then optionally **OpenAI with your chosen budget**, following the existing step-by-step guide. No accounts on the three GitHub projects' hosted platforms are necessary.
