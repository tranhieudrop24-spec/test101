import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Add saveLines and loadLines
js_code = """
function saveLines() {
    const prices = drawnLines.map(l => l.options().price);
    const key = `citrinex_lines_${currentUser.id}_${currentTicker}`;
    localStorage.setItem(key, JSON.stringify(prices));
}

function loadLines() {
    clearLinesNoSave();
    const key = `citrinex_lines_${currentUser.id}_${currentTicker}`;
    const saved = JSON.parse(localStorage.getItem(key) || '[]');
    saved.forEach(p => {
        const l = candleSeries.createPriceLine({
            price: p, color: '#fcd535', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Solid, axisLabelVisible: true
        });
        drawnLines.push(l);
    });
}

function clearLinesNoSave() {
    drawnLines.forEach(l => { try { candleSeries.removePriceLine(l); } catch(e){} });
    drawnLines = [];
}
"""

if 'function saveLines()' not in html:
    html = html.replace('let eraseActive = false;', 'let eraseActive = false;\n' + js_code)

# Replace clearLines to use clearLinesNoSave and saveLines
old_clear = """function clearLines() {
    drawnLines.forEach(l => {
        try { candleSeries.removePriceLine(l); } catch(e){}
    });
    drawnLines = [];
}"""
new_clear = """function clearLines() {
    clearLinesNoSave();
    saveLines();
}"""
if old_clear in html:
    html = html.replace(old_clear, new_clear)

# Insert saveLines() after drawnLines.splice and drawnLines.push
html = html.replace("drawnLines.splice(closestIdx, 1);", "drawnLines.splice(closestIdx, 1);\n          saveLines();")
html = html.replace("drawnLines.push(newLine);\n      toggleDrawLine();", "drawnLines.push(newLine);\n      saveLines();\n      toggleDrawLine();")

# Call loadLines() when chart is updated
# Inside fetchChartData
if 'chart.timeScale().fitContent();' in html:
    html = html.replace('chart.timeScale().fitContent();', 'chart.timeScale().fitContent();\n      loadLines();')

# Modify newLine color to match dark mode (e.g. #fcd535)
html = html.replace("color: '#a855f7'", "color: '#fcd535', lineWidth: 1")

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Updated lines logic")
