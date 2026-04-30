# 1. Ép cài đặt đúng phiên bản vnstock cũ ổn định (0.2.8.5)
!pip uninstall -y vnstock
!pip install vnstock==0.2.8.5 pandas -q

import pandas as pd
import json
from datetime import datetime, timedelta
from IPython.display import HTML, display

# 2. Phải import sau khi pip install xong
from vnstock import stock_historical_data

print("Đang lấy dữ liệu bằng thư viện VNSTOCK (Bản 0.2.8.5)...")

# Tính toán ngày (1 năm trở lại đây)
end_date = datetime.now().strftime('%Y-%m-%d')
start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
ticker = "FPT"

try:
    # Gọi vnstock
    df = stock_historical_data(symbol=ticker, start_date=start_date, end_date=end_date, resolution="1D", type="stock", beautify=True)
    
    # Chỉ lấy các cột cần thiết cho Chart
    df = df[['time', 'open', 'high', 'low', 'close']]
    
    # Đảm bảo cột time đúng định dạng chuỗi YYYY-MM-DD
    df['time'] = pd.to_datetime(df['time']).dt.strftime('%Y-%m-%d')
    
    # Fix giá: Nếu TCBS trả giá dạng rút gọn (115.5) thì nhân với 1000 thành 115500
    if df['close'].iloc[0] < 1000:
        df['open'] = df['open'] * 1000
        df['high'] = df['high'] * 1000
        df['low'] = df['low'] * 1000
        df['close'] = df['close'] * 1000

    # Ép kiểu Pandas DataFrame thành list dictionary chuẩn JSON
    chart_data = df.to_dict(orient='records')
    json_string = json.dumps(chart_data)
    
    print(f"✅ Đã tải và chuẩn hóa xong {len(chart_data)} cây nến mã {ticker}.")

except Exception as e:
    print(f"❌ Lỗi khi lấy data từ vnstock: {e}")
    json_string = "[]"


# ==========================================
# PHẦN HTML/JS HIỂN THỊ (Giữ nguyên)
# ==========================================
html_template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        body { font-family: Arial, sans-serif; background-color: #121212; color: white; margin: 0; padding: 10px; }
        #chart-container { width: 100%; height: 500px; background: #1e1e1e; border: 1px solid #444; }
        .log-panel { background: #000; color: #00e676; font-family: monospace; padding: 10px; margin-top: 10px; border: 1px solid #333;}
    </style>
</head>
<body>
    <h3 style="margin-top: 0; color: #2196f3;">Chart Tích hợp Colab - Ticker: FPT</h3>
    <div id="chart-container"></div>
    <div class="log-panel" id="logger">Đang nạp UI...</div>

    <script>
        const logger = document.getElementById('logger');
        function log(msg) { logger.innerHTML += `<br>> ${msg}`; }

        try {
            log("Khởi tạo Lightweight Charts v4.1.1...");
            const chart = LightweightCharts.createChart(document.getElementById('chart-container'), {
                layout: { textColor: '#d1d4dc', background: { type: 'solid', color: '#1e1e1e' } },
                grid: { vertLines: { color: '#2b2b43' }, horzLines: { color: '#2b2b43' } },
                crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
            });

            const candleSeries = chart.addCandlestickSeries({
                upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
                wickUpColor: '#26a69a', wickDownColor: '#ef5350'
            });

            log("Đang nhận dữ liệu từ Pandas bơm xuống...");
            
            const chartData = __DATA_PLACEHOLDER__; 

            if (chartData && chartData.length > 0) {
                candleSeries.setData(chartData);
                chart.timeScale().fitContent();
                log(`Đã render thành công ${chartData.length} nến!`);
            } else {
                log("<span style='color:#ff5252'>Dữ liệu rỗng, kiểm tra lại luồng gọi Python.</span>");
            }
        } catch (error) {
            log(`<span style="color:#ff5252">Lỗi JS: ${error.message}</span>`);
        }
    </script>
</body>
</html>
"""

# Bơm data vào HTML
final_html = html_template.replace("__DATA_PLACEHOLDER__", json_string)
display(HTML(final_html))