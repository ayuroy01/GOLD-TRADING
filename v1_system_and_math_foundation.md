# Gold (XAU/USD) — V1 Executable System + Mathematical Foundation

---

## PART A: THE V1 SYSTEM — ONE STRATEGY, ZERO AMBIGUITY

### Strategy Selection Rationale

After five architectural iterations, the choice of strategy for a V1 system reduces to one question: which setup has the highest expected value per unit of complexity?

The answer for gold is the **H4 pullback in trend**. Three reasons:

First, gold trends more than it ranges. Measured by ADX readings above 25 on the daily timeframe, gold spends approximately 55-65% of trading days in a trending state. A trend-following system has a structural tailwind.

Second, pullback entries offer superior R:R compared to breakouts because the stop loss is closer to the entry (below the pullback low) than a breakout stop (below the broken level, which is further away). The same target produces a higher R:R.

Third, pullbacks are executable by a human without sub-second timing. Breakouts require catching the candle close at the exact moment of the break. Pullbacks give you a zone and a confirmation candle — you have hours, not seconds.

---

### THE RULES — V1 SYSTEM

**Timeframe:** H4 chart for analysis, H1 for entry timing.

**Instruments:** XAU/USD only.

**Sessions:** London (08:00-16:00 UTC) and New York (13:00-21:00 UTC) only. No entries outside these hours.

---

#### STEP 1: DETERMINE TREND (H4)

The market is in an **uptrend** if ALL THREE conditions are true:
- Price is above the 50-period EMA on H4
- The most recent H4 swing low is higher than the previous H4 swing low
- The most recent H4 swing high is higher than the previous H4 swing high

The market is in a **downtrend** if ALL THREE conditions are true (inverted):
- Price is below the 50-period EMA on H4
- The most recent H4 swing high is lower than the previous H4 swing high
- The most recent H4 swing low is lower than the previous H4 swing low

**If neither condition set is met: NO TRADE. Stop here.**

---

#### STEP 2: WAIT FOR PULLBACK (H4)

In an uptrend, wait for price to pull back to ONE of these zones:
- The 50-period EMA on H4 (dynamic support)
- The most recent broken resistance level (support/resistance flip)
- The 50% retracement of the most recent impulse leg

The pullback zone is valid if price has entered the zone but has NOT closed below the previous H4 swing low.

In a downtrend: mirror logic. Pullback to EMA, broken support, or 50% retracement of the down leg. Valid if price has NOT closed above previous H4 swing high.

**If price blows through the pullback zone and closes beyond the previous swing: TREND IS BROKEN. NO TRADE. Return to Step 1.**

---

#### STEP 3: ENTRY TRIGGER (H1)

Once price is in the pullback zone, drop to H1 and wait for a **reversal candle** in the trend direction:

For long entries (uptrend pullback):
- A bullish engulfing candle, OR
- A hammer (long lower wick, small body, closes in upper third)

For short entries (downtrend pullback):
- A bearish engulfing candle, OR
- A shooting star (long upper wick, small body, closes in lower third)

**Entry price:** The close of the reversal candle.

**If no reversal candle appears within 3 H4 candles (12 hours): pullback is invalid. Return to Step 2 and wait for the next pullback.**

---

#### STEP 4: STOP LOSS

For long trades: Stop loss = the low of the pullback swing minus a buffer.
- Buffer = 0.3% of current price (approximately $7 at gold $2,300)
- Example: Pullback low = $2,310. Buffer = $7. Stop loss = $2,303.

For short trades: Stop loss = the high of the pullback swing plus a buffer.

**Non-negotiable rule: Once set, the stop loss is NEVER moved further from entry. It can only be moved to breakeven or in the direction of profit.**

---

#### STEP 5: TAKE PROFIT

- **Target 1 (T1):** The most recent swing high (for longs) or swing low (for shorts). This is the conservative target.
- **Target 2 (T2):** The measured move — the magnitude of the previous impulse leg projected from the pullback low. This is the full target.

Execution:
- Close 50% of the position at T1. Move stop loss to breakeven.
- Trail the remaining 50% with stop at the most recent H4 swing low (for longs) or swing high (for shorts).
- If T2 is hit, close remaining position.

---

#### STEP 6: POSITION SIZING

Risk per trade = **1% of account equity.**

Position size (in ounces) = (Account equity × 0.01) / (Entry price − Stop loss price)

Example: Account = $50,000. Entry = $2,320. Stop = $2,303. Risk distance = $17.
Position size = ($50,000 × 0.01) / $17 = 29.4 oz ≈ 0.29 standard lots.

---

#### STEP 7: NO-TRADE CONDITIONS

Do NOT enter if ANY of these is true:
1. Trend is unclear (Step 1 fails)
2. Major news release (FOMC, NFP, CPI) within 2 hours
3. Spread exceeds $0.50
4. You have 2 open positions already
5. You are in drawdown > 5% from peak equity
6. It is Friday after 18:00 UTC (weekend gap risk)
7. The R:R from entry to T1 is less than 1.5:1

---

#### DAILY CHECKLIST (BEFORE ANY ANALYSIS)

- [ ] What is the H4 trend? (Up / Down / Unclear)
- [ ] Is price in a pullback zone?
- [ ] Are there news events in next 2 hours?
- [ ] What is current spread?
- [ ] How many positions are open?
- [ ] What is my current drawdown from peak?

If any answer triggers a no-trade condition, close the chart. Come back next session.

---

## PART B: MATHEMATICAL FOUNDATION

### 1. Expected Value — The Only Metric That Matters

Expected value (EV) is the average amount you expect to gain or lose per trade over a large number of trades. It is the single number that determines whether a system survives.

**Formula:**

    EV = (Win Rate × Average Win) − (Loss Rate × Average Loss)

Where:
- Win Rate (W) = number of winning trades / total trades
- Loss Rate (L) = 1 − W
- Average Win = mean profit of winning trades (in R-multiples)
- Average Loss = mean loss of losing trades (in R-multiples, typically close to 1R if stops are respected)

**In R-multiple terms:**

    Expectancy = (W × Avg_Win_R) − (L × Avg_Loss_R)

**Example with realistic V1 numbers:**

Assume: Win rate = 48%, Avg win = 2.1R, Avg loss = 1.0R (stop hit)

    Expectancy = (0.48 × 2.1) − (0.52 × 1.0) = 1.008 − 0.52 = +0.488R per trade

This means: for every 1R risked, you expect to earn 0.488R on average. Over 100 trades risking $500 each, expected profit = 100 × $244 = $24,400.

**Why this matters:** A system with 48% win rate is a LOSING system at 1:1 R:R (EV = −0.04R). The same 48% win rate becomes strongly positive at 2.1:1 average win. The win rate alone tells you nothing. Expectancy tells you everything.

**Limitations of EV:**

EV assumes stationarity — that the win rate and average win/loss remain constant. In real markets, they don't. A system calibrated on trending markets will have degraded EV during ranging markets. This is why regime detection matters even in a V1 system (Step 1 addresses this).

EV is also a long-run average. Over any 20-trade sequence, actual results can deviate enormously from EV due to variance. A positive-EV system can easily produce 8 consecutive losses. The question is whether you survive to reach the long run.

---

### 2. Position Sizing — Fixed Fractional vs. Kelly

#### Fixed Fractional (V1 Default)

Risk a fixed percentage of current equity on each trade.

    Position Size = (Equity × f) / Stop Distance

Where f = risk fraction (0.01 for 1%, 0.02 for 2%).

Properties:
- Position size automatically decreases after losses (equity shrinks)
- Position size automatically increases after wins (equity grows)
- Mathematically impossible to reach zero (asymptotic approach)
- Growth is geometric, not linear

At 1% risk per trade, you need 69 consecutive losses to lose 50% of your account. At 2%, you need 34. This is why 1% is the V1 default.

#### Kelly Criterion

The Kelly fraction maximizes the long-term geometric growth rate of capital.

    f* = (b × p − q) / b

Where:
- p = probability of winning (win rate)
- q = 1 − p (probability of losing)
- b = ratio of average win to average loss

**Using V1 example numbers:**
- p = 0.48, q = 0.52, b = 2.1/1.0 = 2.1

    f* = (2.1 × 0.48 − 0.52) / 2.1 = (1.008 − 0.52) / 2.1 = 0.488 / 2.1 = 0.232

Full Kelly says risk 23.2% per trade. This is catastrophically aggressive for real trading.

**Why full Kelly is dangerous:**
- Kelly assumes you know the exact win rate and payoff ratio. You don't. Your estimates have error.
- Kelly maximizes terminal wealth but tolerates extreme drawdowns (30-50% drawdowns are normal under full Kelly).
- Kelly assumes infinite time horizon and no emotional response to drawdowns. Both assumptions are false.

**Practical rule: Use half-Kelly as the absolute ceiling, quarter-Kelly as the working default.**

Quarter Kelly for V1: 0.232 / 4 = 5.8%. Still aggressive. The fixed fractional 1% is more conservative and more survivable while the system is being validated. **Use 1% fixed fractional for V1. Period.**

#### When to consider adjusting from 1%

Only after 100+ trades with validated positive expectancy. If expectancy is stable and drawdown tolerance allows it, move to 1.5%. Never exceed 2% without 200+ trade validation.

---

### 3. Variance, Distributions, and Fat Tails

#### Why Averages Are Misleading

The V1 example has expectancy of +0.488R per trade. This is the mean of the return distribution. But the distribution of individual trade outcomes is NOT the mean. Consider two systems:

**System A:** Wins 48% at exactly 2.1R, loses 52% at exactly 1.0R.
Expectancy = +0.488R. Variance is moderate.

**System B:** Wins 48% — but 40% of wins are +1.2R and 8% are +8.0R. Loses 52% at 1.0R.
Expectancy = (0.40 × 1.2) + (0.08 × 8.0) − (0.52 × 1.0) = 0.48 + 0.64 − 0.52 = +0.60R. Higher expectancy. But variance is much higher — most winning trades produce only +1.2R, and you endure long stretches where the big wins don't appear.

The V1 pullback system is closer to System A (clustered wins near T1 target) with occasional System B outcomes (trend extensions that run to T2 and beyond). Understanding this distribution matters for setting expectations.

#### Variance of Returns

For a trading system, variance measures how widely individual trade outcomes spread around the mean.

    Variance = (1/N) × Σ(Ri − R̄)²

Where Ri = return of trade i, R̄ = mean return.

Standard deviation = √Variance.

**Why it matters:** A system with +0.5R expectancy and low variance (SD = 0.8R) will produce much smoother equity curves than a system with +0.5R expectancy and high variance (SD = 2.5R). The latter will have deeper drawdowns, longer losing streaks, and higher probability of the operator abandoning the system before the edge materializes.

**V1 implication:** Track standard deviation of R-multiples in your trade journal. If SD > 2.0R, the system's outcomes are highly variable and you need more trades before trusting the expectancy estimate.

#### Fat Tails and Non-Normal Distributions

Financial returns are NOT normally distributed. The normal distribution predicts that a 4-standard-deviation event occurs roughly once every 31,560 trading days (126 years). In gold markets, 4-sigma moves happen several times per year.

This means:
- Stop losses can be gapped through (the fat tail catches you between price levels)
- Average loss understates the true risk — occasional catastrophic losses exceed the expected stop distance
- Risk of ruin formulas that assume normal distributions are overoptimistic

**Practical defense:** 
- The 1% risk rule limits damage from any single fat-tail event to approximately 2-3% (stop gap-through worst case)
- No weekend holding (where gaps are largest)
- No holding through FOMC/NFP/CPI (where intraday gaps are most likely)
- Accept that risk of ruin is never zero. The goal is to make it negligibly small.

---

### 4. Risk of Ruin

Risk of ruin is the probability that an account will eventually reach a level (typically 50% drawdown or total depletion) where trading becomes impractical.

**Simplified formula (for fixed-bet systems):**

    RoR = ((1 − edge) / (1 + edge)) ^ units

Where:
- edge = (W × b) − L = (0.48 × 2.1) − 0.52 = 0.488
- units = (account value) / (risk per trade) = 1 / 0.01 = 100 units at 1% risk

    RoR = ((1 − 0.488) / (1 + 0.488)) ^ 100 = (0.512 / 1.488) ^ 100 = (0.344) ^ 100 ≈ 0

At 1% risk with 0.488 edge, risk of ruin is effectively zero.

**Now watch what happens at 5% risk (same edge):**

    units = 1 / 0.05 = 20
    RoR = (0.344) ^ 20 ≈ 0.0000018 ≈ 0.0002%

Still small. But what if the edge is overestimated?

**At 5% risk with edge = 0.10 (barely positive):**

    RoR = ((1 − 0.10) / (1 + 0.10)) ^ 20 = (0.818) ^ 20 ≈ 1.8%

Nearly 2% risk of ruin. With 100 traders running this system, 2 will be wiped out.

**At 5% risk with edge = 0.00 (no edge at all):**

    RoR = (1.0) ^ 20 = 100%

Guaranteed ruin. A system with zero edge and non-trivial risk per trade is guaranteed to eventually destroy the account.

**The lesson:** Risk per trade must be small enough to survive extended periods where the edge temporarily disappears (regime changes, non-stationarity). 1% provides this buffer. 5% does not.

---

### 5. Drawdown Mathematics

#### Expected Drawdown

Even a positive-EV system will experience drawdowns. The question is how deep and how long.

For a system with win rate W and loss rate L, the expected maximum consecutive losses over N trades is approximately:

    Max Streak ≈ ln(N) / ln(1/L)

For V1 (L = 0.52, N = 100 trades):

    Max Streak ≈ ln(100) / ln(1/0.52) = 4.605 / 0.654 = 7.04

Expect a losing streak of ~7 trades over every 100 trades. At 1% risk: maximum drawdown from streak alone ≈ 7%.

At 2% risk: ≈ 14%. At 5% risk: ≈ 35%. This is why position sizing is a survival question.

#### Recovery Difficulty

Drawdowns are asymmetric. A 10% loss requires an 11.1% gain to recover. A 20% loss requires 25%. A 50% loss requires 100%.

The recovery factor grows exponentially:

    Required Return = 1/(1 − drawdown%) − 1

| Drawdown | Return to Recover |
|----------|------------------|
| 5%       | 5.3%             |
| 10%      | 11.1%            |
| 20%      | 25.0%            |
| 30%      | 42.9%            |
| 50%      | 100.0%           |
| 75%      | 300.0%           |

**V1 implication:** The 10% drawdown halt in the V1 no-trade conditions exists because recovery from 10% (requiring 11.1% return) is achievable within 1-2 months of normal trading. Recovery from 25% (requiring 33% return) may take 6+ months and creates severe behavioral pressure to deviate from the system.

---

### 6. Uncertainty Modeling — Why Single Numbers Are Lies

Every number the V1 system uses (win rate, average R:R, expectancy) is an estimate based on a sample. The true value is unknown.

#### Confidence Intervals for Win Rate

After N trades with observed win rate W, the 95% confidence interval is approximately:

    W ± 1.96 × √(W × (1−W) / N)

**After 50 trades with 48% win rate:**

    0.48 ± 1.96 × √(0.48 × 0.52 / 50) = 0.48 ± 0.138

95% CI: [34.2%, 61.8%]. The true win rate could be anywhere in this range. An expectancy calculation using 34.2% win rate produces:

    EV = (0.342 × 2.1) − (0.658 × 1.0) = 0.718 − 0.658 = +0.06R

Barely positive. At the lower end of the confidence interval, the system has almost no edge.

**After 200 trades with 48% win rate:**

    0.48 ± 1.96 × √(0.48 × 0.52 / 200) = 0.48 ± 0.069

95% CI: [41.1%, 54.9%]. Much narrower. At 41.1%:

    EV = (0.411 × 2.1) − (0.589 × 1.0) = 0.863 − 0.589 = +0.274R

Still positive. The edge is more reliably confirmed.

**This is why 50 trades is the MINIMUM and 200 is the REAL validation threshold.** Before 200 trades, you cannot distinguish a marginally positive system from a marginally negative one with statistical confidence.

#### Probability Ranges vs. Point Estimates

The V1 system should never produce internal beliefs like "this trade has a 48% chance of winning." It should think in ranges: "this type of setup wins between 40% and 56% of the time based on 100 observations."

Decisions should be robust to the entire range. If the trade is positive-EV at the LOW end of the range, it's a valid trade. If it's only positive-EV at the HIGH end, the edge is uncertain and position size should be reduced.

---

## PART C: TRADE JOURNAL TEMPLATE

Every trade must be logged with these fields. No exceptions. Missing data makes the measurement useless.

### Pre-Trade (Filled Before Entry)

| Field | Value |
|-------|-------|
| Trade ID | Sequential number |
| Date/Time (UTC) | Timestamp of entry |
| Session | London / New York / Overlap |
| H4 Trend | Up / Down |
| Pullback Zone | EMA / S-R Flip / 50% Fib |
| Entry Trigger | Bullish Engulfing / Hammer / Bearish Engulfing / Shooting Star |
| Entry Price | $ |
| Stop Loss | $ |
| Target 1 | $ |
| Target 2 | $ |
| Risk Distance | Entry − Stop (absolute value) |
| R:R to T1 | (T1 − Entry) / Risk Distance |
| Position Size (oz) | Calculated per Step 6 |
| Dollar Risk | Equity × 0.01 |
| Spread at Entry | $ |
| Open Positions | Count before this trade |
| Current DD% | Drawdown from peak equity |

### Post-Trade (Filled After Exit)

| Field | Value |
|-------|-------|
| Exit Price | $ |
| Exit Reason | T1 hit / T2 hit / Stop hit / Trailing stop / Time stop / Manual |
| R-Multiple Achieved | (Exit − Entry) / Risk Distance (negative if loss) |
| Holding Duration | Hours |
| Max Adverse Excursion | Furthest price went against trade (in $) |
| Max Favorable Excursion | Furthest price went in favor (in $) |
| Slippage | Difference between intended and actual entry/exit |
| Error Classification | None / Process / Analytical / Timing / Behavioral |
| Notes | What happened, what you learned |

### Derived Metrics (Calculated from Journal, Updated After Every Trade)

| Metric | Formula | Minimum for Validation |
|--------|---------|----------------------|
| Win Rate | Wins / Total | Track over rolling 50 |
| Average Win (R) | Mean R-multiple of winners | > 1.5R |
| Average Loss (R) | Mean R-multiple of losers | Should be ≈ −1.0R |
| Expectancy (R) | (WR × Avg Win) − (LR × Avg Loss) | > +0.20R |
| Profit Factor | Gross Wins / Gross Losses | > 1.3 |
| Max Consecutive Losses | Longest losing streak | Track for drawdown planning |
| Standard Deviation (R) | SD of all R-multiples | Lower is better |
| Sharpe-like Ratio | Expectancy / SD | > 0.3 |
| Max Drawdown % | Peak-to-trough equity decline | Should stay < 10% |

---

## PART D: VALIDATION FRAMEWORK

### Phase 1: Paper Trading (Trades 1-50)

**Objective:** Verify the rules are executable and unambiguous. NOT to prove the system works.

**What you're testing:**
- Can you identify trend, pullback, and trigger consistently?
- Are the no-trade conditions protecting you from bad entries?
- Is the stop loss placement logical (not too tight, not too wide)?
- Is the journaling process sustainable?

**Pass criteria for Phase 1:**
- 50 trades completed with full journal entries
- No fields missing from journal
- Average loss is between −0.8R and −1.2R (confirms stops are placed and respected correctly)
- No behavioral errors (no trades taken outside the rules)

**You are NOT evaluating profitability at this stage.** 50 trades is insufficient for statistical significance.

### Phase 2: Small Live Trading (Trades 51-150)

**Objective:** Validate execution quality and measure preliminary edge.

**Position sizing:** Use the smallest allowed position size (0.01 lots). The goal is measurement, not profit.

**What you're measuring:**
- Expectancy with 95% confidence interval
- Slippage: Is actual slippage within 0.2% of entry price on average?
- Spread: Is average spread consistent with estimates?
- Win rate stability: Is win rate within ±10% across different 20-trade windows?

**Pass criteria for Phase 2:**
- Expectancy point estimate is positive (> 0R)
- Lower bound of 95% CI for expectancy is above −0.3R (the system is not clearly negative)
- Max drawdown has not exceeded 8% (even at small size, process must be followed)
- Behavioral error rate < 10% of trades

### Phase 3: Full Validation (Trades 151-250)

**Objective:** Determine with statistical confidence whether the system has an edge.

**Position sizing:** Move to 0.5% risk per trade if Phase 2 passed. Move to 1% only after 200 trades with positive expectancy.

**The edge test:**

At 200 trades, calculate expectancy and its 95% confidence interval. The system has a validated edge if:

1. Point estimate of expectancy > +0.20R
2. Lower bound of 95% CI > 0R (the edge is statistically significant — positive even at the pessimistic end)
3. Profit factor > 1.3
4. System performed across at least 2 different market regimes (trending and ranging) within the sample

**If the system FAILS the edge test:**
- Stop live trading
- Analyze: Is the failure in win rate, average win, or average loss?
- If win rate < 40%: The entry trigger or trend filter may be too loose — review
- If average win < 1.5R: The target structure may be suboptimal — review T1/T2 levels
- If average loss > 1.2R: Stop losses are being hit after slippage/gap — tighten stop protocol
- Return to Phase 1 with adjusted rules

### Determining Sample Size

The minimum sample for detecting a given edge at 95% confidence:

    N ≈ (1.96 × SD / edge)²

For V1 with estimated SD = 1.5R and edge = 0.488R:

    N ≈ (1.96 × 1.5 / 0.488)² = (6.025)² ≈ 36 trades

If the edge is real and large, 36 trades might detect it. But we use 200 as the target because:
- The edge estimate might be overoptimistic (true edge could be 0.20R, requiring N ≈ 216)
- Variance may be higher than assumed
- Regime changes during the sample period add noise
- 200 trades provides enough data to evaluate per-regime performance

---

## PART E: KEY RISKS AND LIMITATIONS

### What Will Go Wrong

**1. The edge may not exist.** The V1 system is built on structural principles (trend following, pullback entries) that have historical validity in gold markets. But past structure does not guarantee future structure. Gold's correlation regimes, volatility patterns, and microstructure all change over time. The 2020-2024 gold market (massive central bank buying creating persistent trends) may not resemble the 2025-2030 market.

**Mitigation:** Validate with 200+ trades. If the edge test fails, stop. Do not rationalize continued trading with a losing system.

**2. Regime changes will degrade performance temporarily.** The system is optimized for trending markets. During ranging or choppy markets, the trend filter (Step 1) should keep you out. But regime transitions are gradual — the system will take 2-5 trades during the transition before the trend filter fully engages. These trades will likely lose.

**Mitigation:** Accept 7-trade losing streaks as normal (see drawdown math). Do not abandon the system during streaks — this is the most common behavioral failure.

**3. Fat-tail events will exceed stop losses.** A weekend geopolitical event can gap gold $30-50 on Monday open. Your stop at $2,303 is meaningless if the market opens at $2,270. At 1% risk (0.29 lots), a $50 gap = $1,450 loss = 2.9% of account instead of the planned 1%.

**Mitigation:** No weekend holding. No holding through FOMC/NFP/CPI. Accept that residual gap risk during sessions is small but non-zero.

**4. Execution friction will reduce EV.** The mathematical models above assume frictionless entry and exit. In practice, spread ($0.15-0.30 round trip) and slippage ($0.10-0.30 per side) consume 3-7% of the stop distance on every trade. Over 200 trades at $500 risk per trade, friction cost = approximately $3,000-7,000.

**Mitigation:** Track actual friction in the trade journal. If it exceeds 10% of stop distance consistently, widen the stop (which means smaller position size to maintain 1% risk).

**5. You will violate the rules.** The research on discretionary trading is clear: under drawdown stress, traders consistently move stop losses, override no-trade conditions, increase position size to "recover," and revenge-trade after losses. Each of these violations degrades expected value and can convert a positive-EV system into a negative-EV one.

**Mitigation:** The error classification field in the trade journal exists specifically for this. If behavioral errors exceed 15% of trades, the system is not the problem — execution discipline is. Consider automated execution or a circuit breaker process (mandatory 24-hour cool-down after 3 consecutive losses).

### What Cannot Be Fixed Within V1

- **No macro overlay.** The V1 system is purely technical. It will take long gold trades during periods when DXY is surging (bearish gold macro). This reduces win rate. A V2 system should add a simple macro filter (no longs if DXY is above its 50-period EMA and rising).

- **No cross-timeframe optimization.** The H4/H1 combination is fixed. Some market conditions might favor D1/H4 (slower, less noise) or H1/M15 (faster, more trades). V1 doesn't adapt.

- **No volatility adjustment.** Position sizing uses a fixed 1% regardless of whether ATR is at its 10th percentile or 90th percentile. In high-vol environments, the fixed-dollar stop distance might be too tight relative to noise. A V2 system should scale position size inversely with ATR.

- **No portfolio context.** V1 trades gold in isolation. If you also hold silver, USD positions, or correlated assets, the V1 system has no mechanism to account for aggregate risk.

### What Is Deliberately Excluded (Anti-Overengineering)

The following were in v5 and are intentionally stripped from V1 because they cannot be validated without 500+ trades and add complexity without improving V1 decisions:

- Bayesian regime probability distributions — replaced with a simple 3-condition trend test
- Signal conflict resolver — V1 has one signal source (price structure), so there's nothing to conflict
- Uncertainty state propagation — replaced with conservative position sizing (1%) which is the practical outcome of high uncertainty anyway
- Execution realism engine — replaced with "track actual friction in journal and adjust if needed"
- Adaptation engine — premature before 200 validated trades. Optimization before validation is overfitting.

These belong in V2 after V1 is validated. Not before.
