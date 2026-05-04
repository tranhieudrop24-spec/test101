from flask import Flask, render_template, jsonify, request
import pandas as pd
import json
import os
import time
import requests
from datetime import datetime, timedelta
from vnstock import stock_historical_data, fr_trade_heatmap, offline_stock_list

app = Flask(__name__)

# Cache sectors
try:
    df_sectors_cache = offline_stock_list()
    df_sectors_cache['sector'] = df_sectors_cache['sector'].fillna('Khác')
    df_sectors_cache['industry'] = df_sectors_cache['industry'].fillna('Khác')
except Exception as e:
    print(f"Failed to load offline stock list: {e}")
    df_sectors_cache = pd.DataFrame(columns=['ticker', 'sector', 'industry', 'organName', 'organShortName'])


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE = os.path.join(BASE_DIR, 'portfolio.json')
WATCHLIST_FILE = os.path.join(BASE_DIR, 'watchlist.json')
NOTES_FILE = os.path.join(BASE_DIR, 'notes.json')

# CLOUD STORAGE: JSONBin.io (Optional, for Render.com ephemeral disks)
JSONBIN_BIN_ID = os.environ.get('JSONBIN_BIN_ID', '')
JSONBIN_API_KEY = os.environ.get('JSONBIN_API_KEY', '')
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}" if JSONBIN_BIN_ID else ""

def init_storage():
    if not os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                "balance": 200000000, 
                "holdings": [], 
                "pending_orders": [], 
                "trade_log": [],
                "equity_history": [{"time": datetime.now().strftime('%Y-%m-%d'), "equity": 200000000}]
            }, f)
    else:
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            port = json.load(f)
        dirty = False
        if "pending_orders" not in port:
            port["pending_orders"] = []; dirty = True
        if "trade_log" not in port:
            port["trade_log"] = []; dirty = True
        if "equity_history" not in port:
            port["equity_history"] = [{"time": datetime.now().strftime('%Y-%m-%d'), "equity": port.get('balance', 200000000)}]; dirty = True
        if dirty:
            with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
                json.dump(port, f, indent=4)
                
    if not os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump(["FPT", "VCB", "HPG", "VHM", "VIC", "SSI", "TCB", "MWG"], f)
    if not os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)

init_storage()

import threading
import time

# Caching and State
CHART_CACHE = {}
MARKET_MAP_CACHE = {'data': None, 'time': 0}
LIVE_PRICE_CACHE = {} # ticker -> {'price': float, 'change': float, 'time': float}

def get_notes():
    uid = get_uid()
    file_path = f"notes_{uid}.json"
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_notes(data):
    uid = get_uid()
    file_path = f"notes_{uid}.json"
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    save_cloud_state_bg()

def fetch_cloud_state():
    if not JSONBIN_URL: return None
    try:
        res = requests.get(JSONBIN_URL, headers={'X-Master-Key': JSONBIN_API_KEY})
        if res.status_code == 200:
            return res.json().get('record', {})
    except Exception as e:
        print(f"Cloud fetch error: {e}")
    return None

def save_cloud_state_bg():
    if not JSONBIN_URL: return
    def run():
        try:
            data = {
                'portfolio': get_portfolio(),
                'watchlist': get_watchlist(),
                'notes': get_notes()
            }
            requests.put(JSONBIN_URL, headers={'X-Master-Key': JSONBIN_API_KEY, 'Content-Type': 'application/json'}, json=data)
            print("Cloud state background sync successful")
        except Exception as e:
            print(f"Cloud save error: {e}")
    threading.Thread(target=run, daemon=True).start()

def get_uid():
    try:
        from flask import request
        if request: return request.headers.get('X-User-ID', '001')
    except: pass
    return '001'

def get_portfolio():
    uid = get_uid()
    file_path = f"portfolio_{uid}.json"
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"balance": 200000000, "holdings": [], "pending_orders": [], "trade_log": [], "equity_history": []}

def save_portfolio(data):
    uid = get_uid()
    file_path = f"portfolio_{uid}.json"
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    save_cloud_state_bg()

def get_watchlist():
    uid = get_uid()
    file_path = f"watchlist_{uid}.json"
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_watchlist(data):
    uid = get_uid()
    file_path = f"watchlist_{uid}.json"
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    save_cloud_state_bg()

# INITIAL SYNC ON STARTUP
if JSONBIN_URL:
    print("Initial sync from cloud...")
    cloud_data = fetch_cloud_state()
    if cloud_data:
        if 'portfolio' in cloud_data:
            with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f: json.dump(cloud_data['portfolio'], f, indent=4)
        if 'watchlist' in cloud_data:
            with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f: json.dump(cloud_data['watchlist'], f, indent=4)
        if 'notes' in cloud_data:
            with open(NOTES_FILE, 'w', encoding='utf-8') as f: json.dump(cloud_data['notes'], f, indent=4, ensure_ascii=False)

def bg_keep_alive():
    """Ping the app itself to prevent Render from sleeping (Free Tier)."""
    self_url = os.environ.get('RENDER_EXTERNAL_URL')
    if not self_url:
        print("Keep-alive disabled: RENDER_EXTERNAL_URL not set")
        return
    
    print(f"Keep-alive started for: {self_url}")
    while True:
        try:
            time.sleep(600) # Ping every 10 minutes
            res = requests.get(f"{self_url}/ping", timeout=10)
            print(f"Keep-alive ping sent: {res.status_code}")
        except Exception as e:
            print(f"Keep-alive error: {e}")

threading.Thread(target=bg_keep_alive, daemon=True).start()

def bg_chart_updater():
    print("Background chart updater started...")
    while True:
        try:
            # 1. Fetch Live Prices FIRST (Fast, whole market)
            try:
                df_heatmap = fr_trade_heatmap(symbol='HOSE', report_type='Value')
                if df_heatmap is not None and not df_heatmap.empty:
                    cols = {'stockSymbol':'ticker', 'companyNameVi':'name', 'matchedPrice':'price', 'priceChangePercent':'change', 'nmTotalTradedValue':'value'}
                    df_clean = df_heatmap[list(cols.keys())].rename(columns=cols)
                    df_clean['price'] = pd.to_numeric(df_clean['price'], errors='coerce')
                    df_clean['change'] = pd.to_numeric(df_clean['change'], errors='coerce')
                    df_clean['value'] = pd.to_numeric(df_clean['value'], errors='coerce')
                    df_clean = df_clean.fillna(0).sort_values(by='value', ascending=False).head(150)
                    
                    # Update LIVE_PRICE_CACHE immediately
                    for _, row in df_clean.iterrows():
                        LIVE_PRICE_CACHE[row['ticker']] = {
                            'price': row['price'] * 1000 if row['price'] < 1000 else row['price'],
                            'change': row['change'],
                            'time': time.time()
                        }

                    df_merged = pd.merge(df_clean, df_sectors_cache[['ticker', 'industry']], on='ticker', how='left')
                    df_merged['industry'] = df_merged['industry'].fillna('Khác')
                    df_merged = df_merged.rename(columns={'industry': 'sector'})
                    sectors_list = sorted(list(df_merged['sector'].unique()))
                    labels, parents, values, colors, customdata = ["HOSE"], [""], [df_merged['value'].sum()], [0], [{"ticker": "", "price": 0, "change": 0}]
                    sector_grouped = df_merged.groupby('sector')['value'].sum().reset_index()
                    for _, row in sector_grouped.iterrows():
                        if row['value'] > 0:
                            labels.append(row['sector']); parents.append("HOSE"); values.append(row['value']); colors.append(0); customdata.append({"ticker": "", "price": 0, "change": 0})
                    for _, row in df_merged.iterrows():
                        if row['value'] > 0:
                            labels.append(row['ticker']); parents.append(row['sector']); values.append(row['value']); colors.append(row['change']); customdata.append({"ticker": row['ticker'], "price": row['price'], "change": row['change']})
                    
                    MARKET_MAP_CACHE['data'] = {
                        "labels": labels, "parents": parents, "values": values,
                        "colors": colors, "customdata": customdata, "sectors_list": sectors_list,
                        "last_update": datetime.now().strftime('%H:%M:%S')
                    }
                    MARKET_MAP_CACHE['time'] = time.time()
            except Exception as e:
                print(f"Bg updater heatmap error: {e}")

            # 2. Fetch Historical Data (Slow, per ticker)
            wl = get_watchlist()
            port = get_portfolio()
            port_tickers = [h['ticker'] for h in port.get('holdings', [])]
            all_tickers = list(set(wl + port_tickers))
            for ticker in all_tickers:
                for res in ['1D', '1H']:
                    try:
                        end_date = datetime.now().strftime('%Y-%m-%d')
                        start_date = '2023-01-01'
                        df = stock_historical_data(symbol=ticker.upper(), start_date=start_date, end_date=end_date, resolution=res, type="stock", beautify=True)
                        if df is not None and not df.empty:
                            df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
                            df['time'] = pd.to_datetime(df['time'])
                            if res in ['1D', '1W', '1M']:
                                df['time'] = df['time'].dt.strftime('%Y-%m-%d')
                            else:
                                df['time'] = df['time'].apply(lambda x: int(x.timestamp()) - 7*3600)
                            if not df.empty and df['close'].iloc[0] < 1000:
                                for col in ['open', 'high', 'low', 'close']: df[col] = df[col] * 1000
                            
                            cache_key = f"{ticker.upper()}_{res}"
                            CHART_CACHE[cache_key] = {
                                'data': df.to_dict(orient='records'),
                                'time': time.time(),
                                'last_update': datetime.now().strftime('%H:%M:%S')
                            }
                    except Exception as e:
                        print(f"Bg updater error for {ticker} {res}: {e}")
                    time.sleep(1) # avoid rate limit
                
        except Exception as e:
            print(f"Bg updater loop error: {e}")
        # Sleep for 1 minute (60s) to keep prices fresh
        time.sleep(60)

threading.Thread(target=bg_chart_updater, daemon=True).start()




@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ping')
def ping():
    return "pong", 200

@app.route('/api/force-sync', methods=['POST'])
def force_sync_api():
    if JSONBIN_URL:
        cloud_data = fetch_cloud_state()
        if cloud_data:
            uid = get_uid()
            if 'portfolio' in cloud_data:
                with open(f"portfolio_{uid}.json", 'w', encoding='utf-8') as f: json.dump(cloud_data['portfolio'], f, indent=4)
            if 'watchlist' in cloud_data:
                with open(f"watchlist_{uid}.json", 'w', encoding='utf-8') as f: json.dump(cloud_data['watchlist'], f, indent=4)
            if 'notes' in cloud_data:
                with open(f"notes_{uid}.json", 'w', encoding='utf-8') as f: json.dump(cloud_data['notes'], f, indent=4, ensure_ascii=False)
            return jsonify({"status": "success", "message": "Đồng bộ dữ liệu thành công!"})
        return jsonify({"status": "error", "message": "Lỗi đồng bộ từ Cloud."})
    return jsonify({"status": "error", "message": "Nút Sync chỉ có tác dụng khi chạy trên Web thật (Render.com) có cấu hình JSONBIN."})

@app.route('/api/price/<ticker>')
def price_api(ticker):
    """Get latest price for a ticker."""
    ticker = ticker.upper()
    
    # Check Live Cache first for most accurate price
    if ticker in LIVE_PRICE_CACHE:
        lp = LIVE_PRICE_CACHE[ticker]
        return jsonify({
            "price": lp['price'],
            "change": lp['change'],
            "ticker": ticker,
            "last_update": datetime.now().strftime('%H:%M:%S')
        })

    cache_key = f"{ticker}_1D"
    if cache_key in CHART_CACHE:
        data = CHART_CACHE[cache_key]['data']
        if data and len(data) > 0:
            last = data[-1]
            price = float(last['close'])
            prev = float(data[-2]['close']) if len(data) > 1 else price
            change_pct = round((price - prev) / prev * 100, 2) if prev != 0 else 0
            return jsonify({
                "price": price, 
                "change": change_pct, 
                "ticker": ticker,
                "last_update": CHART_CACHE[cache_key].get('last_update', datetime.now().strftime('%H:%M:%S'))
            })

    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
    try:
        df = stock_historical_data(
            symbol=ticker,
            start_date=start_date,
            end_date=end_date,
            resolution="1D",
            type="stock",
            beautify=True
        )
        if df is None or df.empty:
            return jsonify({"price": 0, "change": 0})
        last = df.iloc[-1]
        price = float(last['close'])
        prev = float(df.iloc[-2]['close']) if len(df) > 1 else price
        if price < 1000:
            price *= 1000
            prev *= 1000
        change_pct = round((price - prev) / prev * 100, 2) if prev != 0 else 0
        return jsonify({
            "price": price, 
            "change": change_pct, 
            "ticker": ticker,
            "last_update": datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        print(f"[price_api error] {e}")
        return jsonify({"price": 0, "change": 0})

@app.route('/api/stock/<ticker>')
def stock_api(ticker):
    res = request.args.get('res', '1D') # 1D, 1H, 15, 4H, 1W, 1M
    fetch_res = res
    if res == '4H': fetch_res = '1H'
    elif res in ['1W', '1M']: fetch_res = '1D'
    
    cache_key = f"{ticker.upper()}_{fetch_res}"
    
    # Use cache if available and less than 5 minutes old
    if cache_key in CHART_CACHE and (time.time() - CHART_CACHE[cache_key]['time']) < 300:
        data = CHART_CACHE[cache_key]['data']
        
        # Patch last price if available in Live Cache
        if ticker.upper() in LIVE_PRICE_CACHE and data:
            lp = LIVE_PRICE_CACHE[ticker.upper()]
            last = data[-1]
            last['close'] = lp['price']
            if lp['price'] > last['high']: last['high'] = lp['price']
            if lp['price'] < last['low']: last['low'] = lp['price']

        # Resample if needed (from 1H to 4H, or 1D to 1W/1M)
        if res in ['4H', '1W', '1M']:
            df = pd.DataFrame(data)
            df['time'] = pd.to_datetime(df['time'] if res not in ['4H'] else pd.to_datetime(df['time'], unit='s') + pd.Timedelta(hours=7))
            if res == '4H':
                df = df.set_index('time').resample('4h', offset='1h').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna().reset_index()
                df['time'] = df['time'].apply(lambda x: int(x.timestamp()) - 7*3600)
            elif res == '1W':
                df = df.set_index('time').resample('W-MON').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna().reset_index()
                df['time'] = df['time'].dt.strftime('%Y-%m-%d')
            elif res == '1M':
                df = df.set_index('time').resample('MS').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna().reset_index()
                df['time'] = df['time'].dt.strftime('%Y-%m-%d')
            return jsonify({"error": None, "data": df.to_dict(orient='records'), "last_update": CHART_CACHE[cache_key].get('last_update')})
        return jsonify({"error": None, "data": data, "last_update": CHART_CACHE[cache_key].get('last_update')})

    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = '2023-01-01'
    
    try:
        df = stock_historical_data(symbol=ticker.upper(), start_date=start_date, end_date=end_date, resolution=fetch_res, type="stock", beautify=True)
        if df is None or df.empty:
            return jsonify({"error": "No data available", "data": []})
            
        df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
        df['time'] = pd.to_datetime(df['time'])
        
        # Save raw fetched data to cache
        cache_df = df.copy()
        if fetch_res in ['1D', '1W', '1M']:
            cache_df['time'] = cache_df['time'].dt.strftime('%Y-%m-%d')
        else:
            cache_df['time'] = cache_df['time'].apply(lambda x: int(x.timestamp()) - 7*3600)
        if not cache_df.empty and cache_df['close'].iloc[0] < 1000:
            for col in ['open', 'high', 'low', 'close']: cache_df[col] = cache_df[col] * 1000
        CHART_CACHE[cache_key] = {
            'data': cache_df.to_dict(orient='records'), 
            'time': time.time(),
            'last_update': datetime.now().strftime('%H:%M:%S')
        }

        # Simple Resample logic
        if res == '4H':
            df = df.set_index('time').resample('4h', offset='1h').agg({
                'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
            }).dropna().reset_index()
        elif res == '1W':
            df = df.set_index('time').resample('W-MON').agg({
                'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
            }).dropna().reset_index()
        elif res == '1M':
            df = df.set_index('time').resample('MS').agg({ 
                'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
            }).dropna().reset_index()
        
        # Time Formatting
        if res in ['1D', '1W', '1M']:
            df['time'] = df['time'].dt.strftime('%Y-%m-%d')
        else:
            df['time'] = df['time'].apply(lambda x: int(x.timestamp()) - 7*3600)

        # Fix price scaling
        if not df.empty and df['close'].iloc[0] < 1000:
            for col in ['open', 'high', 'low', 'close']:
                df[col] = df[col] * 1000
                
        data_records = df.to_dict(orient='records')
        if ticker.upper() in LIVE_PRICE_CACHE and data_records:
            lp = LIVE_PRICE_CACHE[ticker.upper()]
            data_records[-1]['close'] = lp['price']
            if lp['price'] > data_records[-1]['high']: data_records[-1]['high'] = lp['price']
            if lp['price'] < data_records[-1]['low']: data_records[-1]['low'] = lp['price']

        return jsonify({
            "error": None, 
            "data": data_records,
            "last_update": datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        print(f"[stock_api error] {e}")
        return jsonify({"error": str(e), "data": []})

@app.route('/api/market/all')
def market_all():
    # Use cache if less than 5 minutes old
    if MARKET_MAP_CACHE['data'] and (time.time() - MARKET_MAP_CACHE['time']) < 300:
        return jsonify(MARKET_MAP_CACHE['data'])
        
    try:
        df = fr_trade_heatmap(symbol='HOSE', report_type='Value')
        if df is None or df.empty: return jsonify({"labels":[], "parents":[], "values":[], "colors":[], "customdata":[]})
        
        cols = {
            'stockSymbol': 'ticker',
            'companyNameVi': 'name',
            'matchedPrice': 'price',
            'priceChangePercent': 'change',
            'nmTotalTradedValue': 'value',
        }
        df_clean = df[list(cols.keys())].rename(columns=cols)
        df_clean['price'] = pd.to_numeric(df_clean['price'], errors='coerce')
        df_clean['change'] = pd.to_numeric(df_clean['change'], errors='coerce')
        df_clean['value'] = pd.to_numeric(df_clean['value'], errors='coerce')
        df_clean = df_clean.fillna(0)
        
        df_clean = df_clean.sort_values(by='value', ascending=False).head(150)
        df_merged = pd.merge(df_clean, df_sectors_cache[['ticker', 'industry']], on='ticker', how='left')
        df_merged['industry'] = df_merged['industry'].fillna('Khác')
        df_merged = df_merged.rename(columns={'industry': 'sector'})
        sectors_list = sorted(list(df_merged['sector'].unique()))
        
        labels, parents, values, colors, customdata = ["HOSE"], [""], [df_merged['value'].sum()], [0], [{"ticker": "", "price": 0, "change": 0}]
        sector_grouped = df_merged.groupby('sector')['value'].sum().reset_index()
        for _, row in sector_grouped.iterrows():
            if row['value'] > 0:
                labels.append(row['sector']); parents.append("HOSE"); values.append(row['value']); colors.append(0); customdata.append({"ticker": "", "price": 0, "change": 0})
        for _, row in df_merged.iterrows():
            if row['value'] > 0:
                labels.append(row['ticker']); parents.append(row['sector']); values.append(row['value']); colors.append(row['change']); customdata.append({"ticker": row['ticker'], "price": row['price'], "change": row['change']})
        
        result = {
            "labels": labels, "parents": parents, "values": values,
            "colors": colors, "customdata": customdata, "sectors_list": sectors_list
        }
        result["last_update"] = datetime.now().strftime('%H:%M:%S')
        MARKET_MAP_CACHE['data'] = result
        MARKET_MAP_CACHE['time'] = time.time()
        return jsonify(result)
    except Exception as e:
        print(f"Market error: {e}")
        return jsonify({"labels":[], "parents":[], "values":[], "colors":[], "customdata":[], "sectors_list":[]})

@app.route('/api/company/info/<ticker>')
def company_info(ticker):
    try:
        info = df_sectors_cache[df_sectors_cache['ticker'] == ticker.upper()]
        if info.empty:
            return jsonify({"status": "error", "message": "Không tìm thấy thông tin"})
        info = info.iloc[0]
        return jsonify({
            "status": "success",
            "data": {
                "ticker": info.get('ticker', ''),
                "name": info.get('organName', ''),
                "shortName": info.get('organShortName', ''),
                "industry": info.get('industry', 'Khác'),
                "sector": info.get('sector', 'Khác'),
                "group": info.get('comGroupCode', '')
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/watchlist', methods=['GET', 'POST', 'DELETE'])
def watchlist_api():
    watchlist = get_watchlist()
    if request.method == 'POST':
        data = request.json
        ticker = data.get('ticker', '').upper().strip()
        if ticker and ticker not in watchlist:
            watchlist.append(ticker)
            save_watchlist(watchlist)
        return jsonify(watchlist)
    elif request.method == 'DELETE':
        ticker = request.json.get('ticker', '').upper()
        if ticker in watchlist:
            watchlist.remove(ticker)
            save_watchlist(watchlist)
        return jsonify(watchlist)
    return jsonify(watchlist)

@app.route('/api/notes/<ticker>', methods=['GET', 'POST', 'DELETE'])
def notes_api(ticker):
    """Per-ticker trading notes: buy targets, reminders, strategies."""
    ticker = ticker.upper()
    notes = get_notes()
    if request.method == 'GET':
        return jsonify(notes.get(ticker, {"targets": [], "memo": ""}))
    elif request.method == 'POST':
        data = request.json
        notes[ticker] = data
        save_notes(notes)
        return jsonify({"status": "ok"})
    elif request.method == 'DELETE':
        notes.pop(ticker, None)
        save_notes(notes)
        return jsonify({"status": "ok"})


@app.route('/api/portfolio', methods=['GET', 'POST'])
def portfolio_api():
    portfolio = get_portfolio()
    if request.method == 'GET':
        # Attach industry info to holdings for frontend analysis
        for holding in portfolio.get('holdings', []):
            info = df_sectors_cache[df_sectors_cache['ticker'] == holding['ticker']]
            holding['industry'] = info.iloc[0]['industry'] if not info.empty else 'Khác'
        return jsonify(portfolio)
        
    if request.method == 'POST':
        action = request.json.get('action')
        ticker = request.json.get('ticker', '').upper()
        quantity = int(request.json.get('quantity', 0))
        price = float(request.json.get('price', 0))
        order_type = request.json.get('type', 'market')

        if quantity <= 0 or price <= 0:
            return jsonify({"status": "error", "message": "Số lượng và giá không hợp lệ"}), 400

        cost = quantity * price

        if order_type == 'limit':
            order_id = str(int(time.time() * 1000))
            if action == 'buy':
                if portfolio['balance'] < cost:
                    return jsonify({"status": "error", "message": f"Không đủ tiền. Cần {cost:,.0f}₫"}), 400
                portfolio['balance'] -= cost
                portfolio['pending_orders'].append({
                    "id": order_id, "ticker": ticker, "action": "buy", "quantity": quantity, "price": price, "timestamp": datetime.now().isoformat()
                })
                save_portfolio(portfolio)
                
                # Auto-add to watchlist even for limit orders
                wl = get_watchlist()
                if ticker not in wl:
                    wl.append(ticker)
                    save_watchlist(wl)

                return jsonify({"status": "success", "message": f"Đã đặt lệnh CHỜ MUA {quantity} {ticker} giá {price:,.0f}₫", "portfolio": portfolio})
            
            elif action == 'sell':
                holding = next((h for h in portfolio['holdings'] if h['ticker'] == ticker), None)
                pending_sells = sum(o['quantity'] for o in portfolio['pending_orders'] if o['ticker'] == ticker and o['action'] == 'sell')
                available_qty = holding['quantity'] - pending_sells if holding else 0
                
                if available_qty < quantity:
                    return jsonify({"status": "error", "message": f"Không đủ CP khả dụng. Khả dụng: {available_qty}"}), 400
                
                portfolio['pending_orders'].append({
                    "id": order_id, "ticker": ticker, "action": "sell", "quantity": quantity, "price": price, "timestamp": datetime.now().isoformat()
                })
                save_portfolio(portfolio)
                return jsonify({"status": "success", "message": f"Đã đặt lệnh CHỜ BÁN {quantity} {ticker} giá {price:,.0f}₫", "portfolio": portfolio})

        # Market Order processing
        elif order_type == 'market':
            if action == 'buy':
                if portfolio['balance'] < cost:
                    return jsonify({"status": "error", "message": f"Không đủ tiền. Cần {cost:,.0f}₫, còn {portfolio['balance']:,.0f}₫"}), 400
                portfolio['balance'] -= cost
                found = False
                for item in portfolio['holdings']:
                    if item['ticker'] == ticker:
                        total_qty = item['quantity'] + quantity
                        item['avgPrice'] = (item['avgPrice'] * item['quantity'] + cost) / total_qty
                        item['quantity'] = total_qty
                        found = True
                        break
                if not found:
                    portfolio['holdings'].append({"ticker": ticker, "quantity": quantity, "avgPrice": price})
                
                # Log trade
                portfolio['trade_log'].append({
                    "ticker": ticker, "action": "buy", "quantity": quantity, "price": price, "timestamp": datetime.now().isoformat()
                })
                save_portfolio(portfolio)
                
                # Auto-add to watchlist on buy
                wl = get_watchlist()
                if ticker not in wl:
                    wl.append(ticker)
                    save_watchlist(wl)

                return jsonify({"status": "success", "message": f"Khớp lệnh MUA {quantity} {ticker}!", "portfolio": portfolio})

            elif action == 'sell':
                holding = next((h for h in portfolio['holdings'] if h['ticker'] == ticker), None)
                pending_sells = sum(o['quantity'] for o in portfolio['pending_orders'] if o['ticker'] == ticker and o['action'] == 'sell')
                available_qty = holding['quantity'] - pending_sells if holding else 0

                if available_qty < quantity:
                    return jsonify({"status": "error", "message": f"Không đủ CP khả dụng. Khả dụng: {available_qty}"}), 400
                    
                holding['quantity'] -= quantity
                portfolio['balance'] += quantity * price
                
                # Log trade
                portfolio['trade_log'].append({
                    "ticker": ticker, "action": "sell", "quantity": quantity, "price": price, "timestamp": datetime.now().isoformat()
                })
                
                portfolio['holdings'] = [h for h in portfolio['holdings'] if h['quantity'] > 0]
                save_portfolio(portfolio)
                return jsonify({"status": "success", "message": f"Khớp lệnh BÁN {quantity} {ticker}!", "portfolio": portfolio})

        return jsonify({"status": "error", "message": "Action không hợp lệ"}), 400

    return jsonify(portfolio)


@app.route('/api/portfolio/cancel', methods=['POST'])
def cancel_order_api():
    portfolio = get_portfolio()
    order_id = request.json.get('id')
    
    order = next((o for o in portfolio['pending_orders'] if o['id'] == order_id), None)
    if not order:
        return jsonify({"status": "error", "message": "Không tìm thấy lệnh chờ"}), 404
        
    portfolio['pending_orders'] = [o for o in portfolio['pending_orders'] if o['id'] != order_id]
    
    if order['action'] == 'buy':
        # Refund balance
        portfolio['balance'] += order['quantity'] * order['price']
    # If sell, we just remove it from pending_orders (shares are no longer locked)
        
    save_portfolio(portfolio)
    return jsonify({"status": "success", "message": "Đã hủy lệnh thành công", "portfolio": portfolio})


@app.route('/api/portfolio/set_sl', methods=['POST'])
def set_stop_loss_api():
    """Set or clear stop-loss for a holding."""
    portfolio = get_portfolio()
    ticker = request.json.get('ticker', '').upper()
    sl_price = request.json.get('stop_loss')  # None = clear SL

    holding = next((h for h in portfolio['holdings'] if h['ticker'] == ticker), None)
    if not holding:
        return jsonify({"status": "error", "message": f"Không có vị thế {ticker}"}), 404

    if sl_price is None or sl_price == 0:
        holding.pop('stop_loss', None)
        msg = f"Đã xóa SL của {ticker}"
    else:
        holding['stop_loss'] = float(sl_price)
        msg = f"Đã đặt SL {ticker} tại {float(sl_price):,.0f}₫"

    save_portfolio(portfolio)
    return jsonify({"status": "success", "message": msg, "portfolio": portfolio})




@app.route('/api/match_orders', methods=['POST'])
def match_orders_api():
    portfolio = get_portfolio()
    if not portfolio['pending_orders']:
        return jsonify({"status": "success", "message": "Không có lệnh chờ nào cần khớp", "portfolio": portfolio})
        
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
    matched_count = 0
    messages = []
    
    # We copy the list to avoid modifying while iterating
    pending_orders = portfolio['pending_orders'][:]
    remaining_orders = []
    
    # Cache daily prices to avoid duplicate API calls
    day_prices = {}
    
    for order in pending_orders:
        ticker = order['ticker']
        if ticker not in day_prices:
            cache_key = f"{ticker}_1D"
            if cache_key in CHART_CACHE and CHART_CACHE[cache_key]['data'] and len(CHART_CACHE[cache_key]['data']) > 0:
                last_row = CHART_CACHE[cache_key]['data'][-1]
                low = float(last_row['low'])
                high = float(last_row['high'])
                day_prices[ticker] = {'low': low, 'high': high, 'time': last_row['time']}
            else:
                try:
                    df = stock_historical_data(symbol=ticker, start_date=start_date, end_date=end_date, resolution="1D", type="stock", beautify=True)
                    if df is not None and not df.empty:
                        last_row = df.iloc[-1]
                        low = float(last_row['low'])
                        high = float(last_row['high'])
                        if low < 1000:
                            low *= 1000
                            high *= 1000
                        
                        # Time formatting to match cache style
                        time_val = last_row['time']
                        if hasattr(time_val, 'strftime'):
                            time_val = time_val.strftime('%Y-%m-%d')
                        elif isinstance(time_val, pd.Timestamp):
                            time_val = time_val.strftime('%Y-%m-%d')
                            
                        day_prices[ticker] = {'low': low, 'high': high, 'time': time_val}
                    else:
                        day_prices[ticker] = None
                except Exception as e:
                    day_prices[ticker] = None
                
        price_data = day_prices.get(ticker)
        matched = False
        
        if price_data:
            candle_date_str = str(price_data['time'])[:10]
            order_date_str = order.get('timestamp', '')[:10]
            
            # ONLY match if the candle's date is ON or AFTER the order placement date
            # This prevents orders placed on holidays/weekends from time-traveling and matching against past prices.
            if candle_date_str < order_date_str:
                remaining_orders.append(order)
                continue

            if order['action'] == 'buy' and order['price'] >= price_data['low']:
                # Buy matches if limit price is greater than or equal to day's low
                found = False
                for item in portfolio['holdings']:
                    if item['ticker'] == ticker:
                        total_qty = item['quantity'] + order['quantity']
                        item['avgPrice'] = (item['avgPrice'] * item['quantity'] + order['quantity'] * order['price']) / total_qty
                        item['quantity'] = total_qty
                        found = True
                        break
                if not found:
                    portfolio['holdings'].append({"ticker": ticker, "quantity": order['quantity'], "avgPrice": order['price']})
                
                # Log trade
                portfolio.setdefault('trade_log', []).append({
                    "ticker": ticker, "action": "buy", "quantity": order['quantity'], "price": order['price'], "timestamp": datetime.now().isoformat()
                })
                
                matched = True
                matched_count += 1
                messages.append(f"Khớp mua {order['quantity']} {ticker} giá {order['price']:,.0f}₫")
                
            elif order['action'] == 'sell' and order['price'] <= price_data['high']:
                # Sell matches if limit price is less than or equal to day's high
                holding = next((h for h in portfolio['holdings'] if h['ticker'] == ticker), None)
                if holding and holding['quantity'] >= order['quantity']:
                    holding['quantity'] -= order['quantity']
                    portfolio['balance'] += order['quantity'] * order['price']
                    
                    # Log trade
                    portfolio.setdefault('trade_log', []).append({
                        "ticker": ticker, "action": "sell", "quantity": order['quantity'], "price": order['price'], "timestamp": datetime.now().isoformat()
                    })

                    matched = True
                    matched_count += 1
                    messages.append(f"Khớp bán {order['quantity']} {ticker} giá {order['price']:,.0f}₫")
                else:
                    # Should not happen because we check available qty when placing order
                    pass
                    
        if not matched:
            remaining_orders.append(order)
            
    portfolio['pending_orders'] = remaining_orders
    # Clean up empty holdings
    portfolio['holdings'] = [h for h in portfolio['holdings'] if h['quantity'] > 0]
    
    save_portfolio(portfolio)
    msg = f"Đã khớp {matched_count} lệnh."
    if messages:
        msg += " " + ", ".join(messages)
    return jsonify({"status": "success", "message": msg, "portfolio": portfolio})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
