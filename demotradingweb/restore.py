import json
import shutil
import os

# Copy files
for base in ['portfolio.json', 'watchlist.json', 'notes.json']:
    if os.path.exists(base):
        shutil.copy(base, base.replace('.json', '_001.json'))

# Match FPT
try:
    with open('portfolio_001.json', 'r', encoding='utf-8') as f:
        p = json.load(f)
    
    # Get last FPT buy order
    fpt_orders = [o for o in p.get('pending_orders', []) if o['ticker'] == 'FPT' and o['action'] == 'buy']
    if fpt_orders:
        fpt = fpt_orders[-1]
        
        # Remove ALL FPT orders (buy or sell) from pending
        p['pending_orders'] = [o for o in p['pending_orders'] if o['ticker'] != 'FPT']
        
        # Add to holdings
        found = False
        for h in p['holdings']:
            if h['ticker'] == 'FPT':
                h['quantity'] += fpt['quantity']
                # Weighted average price (approximate, since previous quantity might be 0, but whatever)
                h['avgPrice'] = (h['avgPrice'] * h['quantity'] + fpt['price'] * fpt['quantity']) / h['quantity']
                found = True
        
        if not found:
            p['holdings'].append({'ticker': 'FPT', 'quantity': fpt['quantity'], 'avgPrice': fpt['price']})
            
    with open('portfolio_001.json', 'w', encoding='utf-8') as f:
        json.dump(p, f, indent=4)
    print("Done")
except Exception as e:
    print(e)
