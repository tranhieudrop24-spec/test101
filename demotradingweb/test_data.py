from vnstock import *
import pandas as pd

try:
    print("Fetching listing companies...")
    df_listing = listing_companies(live=True)
    
    # Filter HOSE
    if 'comGroupCode' in df_listing.columns:
        hose_df = df_listing[df_listing['comGroupCode'] == 'HOSE']
        hose_stocks = hose_df['ticker'].tolist()
    else:
        hose_stocks = []

    print(f"Total HOSE stocks: {len(hose_stocks)}")
    
    # Check industry/sector info - industry_analysis might help
    # print("Fetching industry info...")
    # df_industry = industry_analysis("FPT") # Just to see what it returns
    # print("Industry columns:", df_industry.columns.tolist())

    # Try price_board with a single valid symbol
    print("Testing price_board with FPT...")
    df_fpt = price_board("FPT")
    print("FPT price board columns:", df_fpt.columns.tolist())
    print(df_fpt[['Mã CP', 'Giá', '% Thay đổi']])

except Exception as e:
    import traceback
    traceback.print_exc()
