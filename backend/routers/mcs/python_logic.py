import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class PythonMCSEngine:
    def __init__(self, initial_capital: float, n_simulations: int):
        self.initial_capital = initial_capital
        self.n_simulations = n_simulations

    def load_trades(self, file_path: str) -> np.ndarray:
        """
        Load trade PnL or Returns from CSV.
        Expects columns: 'pnl', 'profit', 'return', or 'net_profit'.
        If only prices, this helper isn't smart enough yet (MCS usually takes trade list).
        """
        try:
            df = pd.read_csv(file_path)
            df.columns = df.columns.str.lower().str.strip()
            
            # Detect PnL column (Prioritize Net PnL)
            possible_cols = ['pnl_with_commission', 'net_profit', 'total_pnl', 'pnl', 'profit', 'return', 'pl']
            col = next((c for c in possible_cols if c in df.columns), None)
            
            if col:
                # Clean data: remove currency symbols and commas
                vals = df[col].astype(str).str.replace(r'[$,€£]', '', regex=True).str.replace(',', '', regex=False)
                return pd.to_numeric(vals, errors='coerce').fillna(0.0).values
            
            # Fallback: simple close-to-close returns from price data?
            # MCS is usually for Trade Systems, not raw price series.
            # But if user uploaded price data... 
            if 'close' in df.columns:
                 # Calculate simple returns? 
                 # Assuming single share? 
                 # Let's treat close diff as PnL per unit?
                 # Or just % return?
                 # Safer to error or assume % returns if small values, PnL if large.
                 # Let's assume % returns for price limits? No, standard is Trade PnL.
                 pass
            
            raise ValueError(f"Could not find trade PnL column in {df.columns}. Expected one of {possible_cols}")
            
        except Exception as e:
            logger.error(f"Failed to load trades: {e}")
            raise e

    def run(self, file_path: str):
        try:
            trades = self.load_trades(file_path)
            n_trades = len(trades)
            
            if n_trades == 0:
                return {
                    "error": "No trades found in file"
                }

            # Vectorized Simulation
            # Generate random indices: (n_simulations, n_trades)
            # This samples *with replacement* from the original trades
            random_indices = np.random.randint(0, n_trades, size=(self.n_simulations, n_trades))
            
            # Get PnL values
            sim_pnls = trades[random_indices] # shape (n_simulations, n_trades)
            
            # Calculate Equity Curves
            # cumulative sum of PnL + Initial Capital
            # Axis 1 is time (trades)
            cumulative_pnl = np.cumsum(sim_pnls, axis=1)
            equity_curves = self.initial_capital + cumulative_pnl
            
            # Prepend Initial Capital to get full curve starting at t=0
            start_cap_column = np.full((self.n_simulations, 1), self.initial_capital)
            equity_curves = np.hstack((start_cap_column, equity_curves))
            
            # --- Metrics ---
            
            # 1. Terminal Equity Stats
            final_equities = equity_curves[:, -1]
            mean_profit = np.mean(final_equities) - self.initial_capital
            # Return as Rate (e.g. 0.05 for 5%), Frontend/Email multiplies by 100
            mean_return = mean_profit / self.initial_capital if self.initial_capital != 0 else 0.0
            std_return = np.std(final_equities)
            
            # 2. Drawdowns
            # Calculate max drawdown for EACH simulation
            # Accumulate max so far
            running_max = np.maximum.accumulate(equity_curves, axis=1)
            drawdowns = (equity_curves - running_max) / running_max # Percentage DD
            # Or absolute? Usually % for logic.
            # Drawdowns are negative or zero.
            max_drawdowns = np.min(drawdowns, axis=1) # The deepest trough (most negative)
            
            mean_max_drawdown = np.mean(max_drawdowns) * 100 # Convert to % positive for display?
            # Usually users expect "Max Drawdown: 25%" (meaning -25%).
            # Let's return positive number representing the drop size.
            mean_max_drawdown = -mean_max_drawdown 
            
            # 95th Percentile DD (The "bad case")
            # 5th percentile of the negative numbers = 95th %ile 'size'
            max_drawdown_95 = -np.percentile(max_drawdowns, 5) * 100
            
            # 3. Risk of Ruin
            # Count simulations where equity drops below ? (Zero? 50%?)
            # Standard RoR: Equity <= 0
            ruined_sims = np.any(equity_curves <= 0, axis=1)
            risk_of_ruin = np.mean(ruined_sims) * 100
            
            # 4. Percentiles for Charts
            # We want specific equity curves (traces) that represent the p5, p50, p95 OUTCOME
            # Sort simulations by final equity
            sorted_indices = np.argsort(final_equities)
            
            idx_05 = sorted_indices[int(self.n_simulations * 0.05)]
            idx_50 = sorted_indices[int(self.n_simulations * 0.50)]
            idx_95 = sorted_indices[int(self.n_simulations * 0.95)]
            
            # Helper to format curve for frontend
            def to_list(arr): return arr.tolist()
            
            return {
                "n_simulations": self.n_simulations,
                "n_trades": n_trades,
                "initial_capital": self.initial_capital,
                "mean_return": float(mean_return),
                "std_return": float(std_return),
                "mean_max_drawdown": float(mean_max_drawdown),
                "max_drawdown_95": float(max_drawdown_95),
                "risk_of_ruin": float(risk_of_ruin),
                
                "final_equity_05": float(final_equities[idx_05]),
                "final_equity_50": float(final_equities[idx_50]),
                "final_equity_95": float(final_equities[idx_95]),
                
                "equity_curve_05": to_list(equity_curves[idx_05]),
                "equity_curve_50": to_list(equity_curves[idx_50]),
                "equity_curve_95": to_list(equity_curves[idx_95]),
                
                "processing_time_seconds": 0.0 # Filled by caller
            }

        except Exception as e:
            logger.error(f"MCS Python execution failed: {e}")
            return {"error": str(e)}
