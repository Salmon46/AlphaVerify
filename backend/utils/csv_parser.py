import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

def load_market_data(file_path: str) -> dict:
    """
    Parses market data CSV.
    Supports:
    1. Standard Single-Asset CSV (time, open, high, low, close, volume)
    2. Multi-Asset Layered CSV (Header 0: Assets, Header 1: Fields)
    
    Returns:
    dict: { "ASSET_NAME": pd.DataFrame (ohlcv), ... }
    """
    try:
        # 1. Detect Header Structure dynamically
        header_rows = []
        field_row_idx = None
        
        with open(file_path, 'r') as f:
            for i in range(10): # Check first 10 lines
                line = f.readline()
                if not line: break
                
                # Check if this line looks like the "Field" row (time, open, high...)
                # Heuristic: starts with time/date and has typical OHLC names
                lower_line = line.lower()
                if (lower_line.startswith('time') or lower_line.startswith('date')) and \
                   ('close' in lower_line and 'open' in lower_line):
                    field_row_idx = i
                    break
        
        if field_row_idx is not None and field_row_idx > 0:
            # It's a Multi-Layer CSV
            # header rows are 0 to field_row_idx
            header_indices = list(range(field_row_idx + 1))
            
            logger.info(f"Detected Multi-Level Header (Depth {len(header_indices)})")
            
            df = pd.read_csv(file_path, header=header_indices, index_col=0, parse_dates=True)
            
            # Forward Fill Header Levels
            # Reconstruct columns to handle "Unnamed" gaps from merged cells
            
            # Convert MultiIndex to a list of tuples to process mutable
            # We need to forward fill each level separately
            
            # Helper to fill a list
            def forward_fill_list(lst):
                filled = []
                last = ""
                for item in lst:
                    s = str(item)
                    if s == "nan" or "Unnamed" in s or s.strip() == "":
                        filled.append(last)
                    else:
                        filled.append(s)
                        last = s
                return filled

            # Process each level (except the last one which is fields)
            n_levels = df.columns.nlevels
            new_levels = []
            
            for l in range(n_levels - 1): # All except last (fields)
                level_values = df.columns.get_level_values(l).tolist()
                new_levels.append(forward_fill_list(level_values))
            
            # Last level is fields, usually don't need fill, but let's keep it clean
            new_levels.append(df.columns.get_level_values(n_levels - 1).tolist())
            
            # Zip back into tuples
            new_columns = list(zip(*new_levels))
            df.columns = pd.MultiIndex.from_tuples(new_columns)
            
            # Now flatten to Dictionary
            data_dict = {}
            
            # Identify Asset Key Level
            # Usually Level -2 is Asset (e.g. QQQ), Level -3 is Source (e.g. QuantConnect)
            # If we have Source, we should combine: Source_Asset to be unique
            
            # Group columns by unique (Source, Asset) tuple prefix
            # We assume the last level is always the Field (OHLC)
            
            # Get all unique prefixes (exclude field)
            # using dictionary to preserve order
            grouped_cols = {} 
            
            for col_tuple in df.columns:
                field = col_tuple[-1].lower().strip()
                # path is everything before field
                path = col_tuple[:-1]
                
                # Create a canonical key for this group
                if path not in grouped_cols:
                    grouped_cols[path] = {}
                
                grouped_cols[path][field] = col_tuple
            
            # Construct DataFrames
            for path, field_map in grouped_cols.items():
                # path is e.g. ('Market Data', 'QuantConnect', 'QQQ')
                # Determine Asset Name
                
                # Filter out "Market Data" or generic top levels if they exist
                # Use the deepest non-empty parts
                valid_parts = [p for p in path if p and "Market Data" not in p and "External Data" not in p]
                
                # Naming Strategy:
                # If just one part: "QQQ" -> QQQ
                # If multiple: "QuantConnect_QQQ" -> QuantConnect_QQQ
                # Exception: "Binance_BTC/USDT"
                
                if not valid_parts:
                    continue
                    
                asset_name = "_".join(valid_parts)
                
                # Extract subset
                # We can't just doing df[path] easily with MultiIndex if duplicates exists in levels
                # Safer to select by boolean indexing or column list
                
                cols_to_select = list(field_map.values())
                sub_df = df[cols_to_select].copy()
                
                # Rename columns to just fields
                # MultiIndex columns -> drop levels?
                sub_df.columns = [c[-1].lower().strip() for c in sub_df.columns]
                
                # Clean NaNs
                sub_df.dropna(how='all', inplace=True)
                
                if not sub_df.empty:
                    data_dict[asset_name] = sub_df
            
            logger.info(f"Loaded Multi-Asset Data keys: {list(data_dict.keys())}")
            return data_dict
            
        else:
            # Standard Parsing (No Multi-Level detected or just 1 line)
            df = pd.read_csv(file_path)
            df.columns = df.columns.str.lower().str.strip()
            
            # Identify Time Column
            time_cols = [c for c in df.columns if 'time' in c or 'date' in c]
            if time_cols:
                df.set_index(time_cols[0], inplace=True)
                df.index = pd.to_datetime(df.index)
            
            data_dict = {"MAIN": df}
            logger.info("Loaded Single-Asset Data")
            return data_dict

    except Exception as e:
        logger.error(f"Data Parsing Failed: {e}")
        raise e
