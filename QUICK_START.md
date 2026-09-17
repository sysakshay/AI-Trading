# First virtual trade — no accounts needed

1. Open File Explorer and go to `X:\GitHub\AI_Trading`.
2. Click the address bar, type `powershell`, and press Enter. A terminal opens in the project folder.
3. Paste this command and press Enter:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\start_app.ps1
   ```

4. Leave that window open. Open **http://localhost:8501** in your browser. Success: the **Paper Research** title appears. If it does not, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
5. Click **Start offline demo** in the left panel. You now have INR 10,000 of virtual cash. The clock is **15 September 2026, 10:00 IST**. All instruments beginning `DEMO-` are invented.
6. Under **Watchlist & setups**, inspect `DEMO-WIN` and its mock explanation. Click its **Approve virtual trade** button. Cash is reserved; no share is filled yet.
7. Click **Advance one candle** once. The clock reaches 10:15; inspect **Positions** for the virtual entry.
8. Click **Advance one candle** again. At 10:30 the fixture reaches its target. Inspect **Journal** for the entry/exit and cash ledger, and **Evaluation** for the report.
9. To see the loss scenario, start another offline demo and approve `DEMO-LOSS`, then advance twice. Its gap produces a loss worse than the planned stop. `DEMO-SKIP` never passes the volume rule.
10. Close the browser tab and reopen the URL. The saved run remains. To test process restart, press **Ctrl+C** in PowerShell, rerun step 3, and select the saved run.

In **Settings & data**, make a database backup. It appears in `backups`. The main journal lives in `data\paper.db`. A new run preserves old accounts; it does not reset or delete them.

**Next action:** complete steps 5–8. API keys and paid accounts can wait.

## New in version 0.2

Fresh proposals include a **Research desk** with supporting/opposing arguments, risk notes and missing evidence. These are code-computed diagnostics, not independent AI agents. Old proposals keep their original evidence.

In **Evaluation**, click **Run saved policy comparison** to create three isolated accounts on the full sample dataset. Results persist after restart. The experimental volatility filter may skip every trade while warming up; this does not prove it is superior. Operating expenses entered on this page are now saved.

See [repository comparison](docs/REPOSITORY_COMPARISON.md) and [connection checklist](docs/CONNECTION_CHECKLIST.md). Nothing new needs connecting to try these features.
