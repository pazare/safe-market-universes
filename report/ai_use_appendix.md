# AI Use Appendix

## Working Status

This appendix now reflects the completed verification and final canonical OpenAI-powered run. It documents representative development prompts, selected output excerpts, editorial judgment, and the verification steps that were accepted, revised, rejected, or independently checked.

## 1. Representative Development Prompts

Keep this appendix selective. Include representative prompts that materially changed the implementation.

### Prompt A: Base architecture

Goal:

- Build a LangGraph workflow with a pure market-data node, independent strategy branches, and evaluator routing.

Representative summary:

> Design a LangGraph workflow where market data fans out to independent strategy agents, those branches rejoin before evaluation, and the system handles agreement and disagreement differently.

What I accepted:

- the graph-first framing of the assignment

What I revised:

- I used schema-constrained outputs instead of free-form text parsing

### Prompt B: Indicator selection

Goal:

- Turn the assignment’s behavioral strategies into concrete indicators.

Representative summary:

> Compare a Momentum Trader against a Value Contrarian using moving averages, recent returns, volume confirmation, RSI, drawdown, 52-week range distance, and trailing P/E.

What I accepted:

- moving-average structure as the center of the momentum lens

What I revised:

- `trailing_pe` became an explicit valuation anchor in the contrarian design

### Prompt C: Bonus extensions

Goal:

- Add all three optional extensions without turning the code into a rewrite.

Representative summary:

> Add a third strategy agent, disagreement-only debate mode, and a historical backtest scorecard while keeping the online workflow clean and the historical logic separate.

What I accepted:

- keeping backtest logic outside the LangGraph online path

What I revised:

- I made debate a disagreement-only second round and intentionally omitted live valuation data from historical snapshots to avoid lookahead bias

## 2. Representative Output Excerpts

### Excerpt A: Live market-only stock-selection evidence

Observed on 2026-04-10:

- `COST`: `pct_change_30d = 1.19`, `short_vs_long_ma_pct = 0.27`
- `HIMS`: `pct_change_30d = 24.55`, `short_vs_long_ma_pct = 5.68`
- `SMCI`: `pct_change_30d = -21.75`, `short_vs_long_ma_pct = -14.31`
- `JNJ`: `pct_change_30d = -2.06`, `short_vs_long_ma_pct = -0.32`
- `TSLA`: `pct_change_30d = -14.59`, `short_vs_long_ma_pct = -5.95`

Why it mattered:

- the final stock basket was chosen from live data rather than intuition alone

### Excerpt B: Strategy excerpt

> “the setup looks more like a steady hold than an actionable breakout.”

Why it mattered:

- This was the clearest example of productive debate. The Momentum Trader did not simply defend its first answer; it reconsidered the evidence and downgraded COST from `BUY` to `HOLD`.

### Excerpt C: Evaluator excerpt

> “not oversold at RSI 45.1, not trend-confirmed, and still structurally damaged despite the rebound.”

Why it mattered:

- This captured the central analytical payoff of the assignment in an agreement case: the evaluator explained why the rebound in HIMS was still too weak to convince any of the strategies.

## 3. Editorial Judgment

### Accepted

- the LangGraph branch-and-routing architecture
- the use of OpenAI Structured Outputs plus Pydantic
- the separation between live workflow logic and historical backtest logic

### Revised

- I revised the project to make the core contrast explicitly `P/E` versus moving-average structure
- I added a third strategy that brings a risk-first lens rather than a minor prompt variation
- I revised historical snapshots to omit live valuation fields and avoid lookahead bias
- I tested `NVDA` as a fifth live stock, rejected it because it produced another low-insight consensus case, and replaced it with `TSLA` for the final canonical basket

### Rejected

- any design where one strategy sees another before the first-round evaluation
- free-form JSON parsing without typed validation
- historical backtest logic that reuses current valuation data as if it were historical

### Editorial corrections applied to output files

Two LLM generation artifacts were identified during post-run review and corrected editorially before submission.

**Artifact 1 — `outputs/HIMS.json`, `strategy_b.justification`:**

The Value Contrarian justification contained a mid-sentence self-correction: `"The stock is also above its 20-day moving average of 21.29? Actually it is below that at 19.43"`. The final conclusion was factually correct (current price 19.43 is below the 20-day MA of 21.29), but the phrasing shows the model reconsidering mid-sentence rather than expressing a clear conclusion. The sentence was rewritten as: `"The stock is below its 20-day moving average of 21.29 at current price 19.43, and also below the 50-day average of 20.14"`. No data or conclusion was changed.

**Artifact 2 — `outputs/backtest.json`, COST checkpoint Volatility Averse justification:**

Same class of artifact: `"but it still sits below the 50-day moving average at 894.59? Actually current price is above the 50-day but below the 200-day at 950.25"`. The fact (price 924.88 is above the 50-day MA at 894.59 and below the 200-day at 950.25) is correct. The sentence was rewritten as: `"but current price of 924.88 is above the 50-day moving average at 894.59 while still below the 200-day at 950.25"`.

**Prompt update to prevent recurrence:**

Each of the three strategy prompts (`strategy_a.txt`, `strategy_b.txt`, `strategy_c.txt`) was updated to include: `"Write each sentence in your justification as a clear, direct statement; do not revise or self-correct mid-sentence."` This does not change strategy philosophy or decision logic; it addresses the output writing style only.

### Verified Independently

- the market-data pipeline works with live Yahoo Finance data
- the upgraded workflow compiles and renders as a Mermaid graph
- the installed OpenAI SDK exposes `client.responses.parse(...)`
- the three-strategy disagreement and debate control flow works in a no-key smoke test
- the backtest scorecard logic works in a no-key synthetic smoke test

## 4. Verification Log

Already completed:

- `python3 -m venv .venv`
- `./.venv/bin/pip install -r requirements.txt`
- `./.venv/bin/python -m compileall src`
- `./.venv/bin/python -m src.main --market-only COST`
- direct live checks of candidate tickers through `fetch_market_data(...)`
- local inspection of `client.responses.parse(...)`
- deterministic smoke test for the extended graph and backtest logic

Final execution commands run:

- `./.venv/bin/python -m src.main --verify-setup`
- `./.venv/bin/python -m src.main`
- exploratory but non-canonical candidate scan was run separately in `/tmp` to test whether alternative live tickers would generate richer disagreement
- the final canonical batch was rerun after replacing `NVDA` with `TSLA`

## 5. Final Submission Checklist

- [x] one JSON file exists for each analyzed stock
- [x] `outputs/summary.json` exists
- [x] `outputs/backtest.json` exists
- [x] the report includes at least two direct excerpts from generated outputs
- [x] one failure or surprise case is documented honestly
- [x] prompts include `strategy_a.txt`, `strategy_b.txt`, `strategy_c.txt`, `evaluator.txt`, and `debate.txt`
- [x] README explains setup and the bonus-extension workflow
- [x] this appendix explains what was accepted, revised, rejected, and verified independently
