import pandas as pd
import json
from vnstock import fr_trade_heatmap
import numpy as np

def test_market_data():
    print("Fetching heatmap data from vnstock...")
    df = fr_trade_heatmap(symbol='HOSE', report_type='Value')
    
    if df is None or df.empty:
        print("Data is empty!")
        return
        
    print(f"Received {len(df)} rows.")
    
    cols = {
        'stockSymbol': 'ticker',
        'companyNameVi': 'name',
        'matchedPrice': 'price',
        'priceChangePercent': 'change',
        'nmTotalTradedValue': 'value',
        'highest': 'high',
        'lowest': 'low'
    }
    df_clean = df[list(cols.keys())].rename(columns=cols)
    
    # Introduce coercion to NaN as in the main app
    df_clean['price'] = pd.to_numeric(df_clean['price'], errors='coerce')
    df_clean['change'] = pd.to_numeric(df_clean['change'], errors='coerce')
    df_clean['value'] = pd.to_numeric(df_clean['value'], errors='coerce')
    
    # The fix:
    df_clean = df_clean.fillna(0) # or we could dropna()
    
    # Convert to dict
    data_dict = df_clean.to_dict(orient='records')
    
    # Try dumping to json with allow_nan=False to strictly test for invalid JSON standard
    try:
        json_str = json.dumps(data_dict, allow_nan=False)
        print("JSON Serialization SUCCESS!")
        print("First item:", json_str[:200])
    except ValueError as e:
        print(f"JSON Serialization FAILED: {e}")
        
if __name__ == "__main__":
    test_market_data()
