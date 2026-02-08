# Statistical & Analysis Tools

AlphaVerify includes a suite of advanced analysis tools designed to rigorously test trading strategies beyond simple backtesting.

## 1. Walk Forward Analysis (WFA)

**Purpose**: To verify the robustness of a strategy by simulating the "re-optimization" process over time. It helps detect if a strategy is overfitted to specific historical data.

### How It Works

The WFA engine checks strategy performance using a sliding window approach:

1. **In-Sample (IS)**: The strategy is optimized (parameters tuned) over a training period (e.g., 365 days).
2. **Out-Of-Sample (OOS)**: The best parameters from the IS period are applied to the immediate following test period (e.g., 90 days), which was *not* seen during optimization.
3. **Step**: The windows slide forward by the step size, and the process repeats.

### Key Metrics

- **Walk-Forward Efficiency (WFE)**: The ratio of annualized OOS return to IS return. A WFE > 0.5 usually indicates robust performance.
- **OOS Equity Curve**: The concatenated performance of the strategy during the "unknown" future periods.

### Inputs

- **Window Size**: Length of the In-Sample training period (days).
- **Step Size**: Length of the Out-Of-Sample testing period (days).
- **Parameters**: Range of parameters to optimize (Min, Max, Step).

---

## 2. Sensitivity Analysis

**Purpose**: To visualize how strategy performance changes as parameters vary. This identifies "parameter islands" (stable regions of profitability) versus "peaks" (potential overfitting).

### How It Works

The engine runs the strategy over the entire historical dataset for every combination of parameters defined in the grid.

### Key Metrics

- **Parameter Heatmaps**: Visual representation of Sharpes/Returns across two parameter dimensions.
- **Stability Score**: Measures the variance of returns in the neighborhood of the best parameter set.

### Inputs

- **Parameter Grid**: Define Min, Max, and Step for each strategy parameter.
- **Mode**: Grid Search (exhausts all combinations) or Random Search (samples `N` random combinations).

---

## 3. Monte Carlo Simulation (MCS)

**Purpose**: To assess the risk and probability of future returns based on the statistical properties of historical trades.

### How It Works

MCS does *not* rerun the strategy code. Instead, it takes the list of historical trade results (PnL) and re-shuffles them to create thousands of alternative equity curves.

1. **Resampling**: Randomly selects trades from history *with replacement*.
2. **Simulation**: Constructs `N` (e.g., 1000) hypothetical equity curves.

### Key Metrics

- **Risk of Ruin**: The probability that the account equity will hit zero (or a defined ruin threshold).
- **Value at Risk (VaR)**: The maximum expected loss at a given confidence level (e.g., 95%).
- **Median Equity**: The expected outcome (50th percentile).
- **Worst Case**: The 5th percentile outcome (95% confidence it won't be worse than this).

---

## 4. Permutation Tests

**Purpose**: To determine if the strategy's performance is statistically significant or a result of luck (data mining bias).

### How It Works

Instead of changing the strategy, this test changes the *data*.

1. **Null Hypothesis**: The strategy has no predictive power; any profit is due to market drift or luck.
2. **Permutation**: The OHLC market data is broken into bars, shuffled, or reconstructed to destroy serial correlation while preserving the distribution of returns (volatility, drift).
3. **Execution**: The strategy is run on 1000+ randomized versions of the market data.

### Interpretation

- **p-value**: The percentage of random runs that outperformed the actual strategy.
  - `p < 0.05`: Strong evidence the strategy has real predictive skill.
  - `p > 0.05`: The result could be due to luck.

---

## 5. Event-Driven Backtest

**Purpose**: To simulate production execution as closely as possible, including latency, order handling, and state management.

### Features

- **Tick-Level Precision**: Processes data tick-by-tick (or bar-by-bar) rather than vectorized arrays.
- **Mock Infrastructure**: Uses a mock Redis and Prometheus to simulate the live event bus and metrics collection.
- **State Tracking**: Accurately tracks cash, positions (average entry price), and financing costs.

### Use Case

Use this for the final verification of a strategy before deployment to ensure the logic holds up under "live-like" conditions.
