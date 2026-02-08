import pandas as pd
import numpy as np

file_path = r"c:\Greek-Suite\AlphaVerify\SuperApp\Example Data Amalgamation - combined_market_data_layered.csv.csv"

try:
    # Attempt to read with MultiIndex header (Row 0 and 1)
    df = pd.read_csv(file_path, header=[0, 1], index_col=0, parse_dates=True)
    
    print("Shape: {}".format(df.shape))
    print("Columns Levels: {}".format(df.columns.nlevels))
    # print("Level 0:", df.columns.levels[0].tolist()) # levels might be tricky if not fully parsed
    
    print("\nColumns:")
    print(df.columns)

    print("\nHead:")
    print(df.head())
    
except Exception as e:
    print("Error: {}".format(e))
