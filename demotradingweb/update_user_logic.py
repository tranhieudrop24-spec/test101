import os, re

# Update HTML
with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace buttons text
html = html.replace('Đo %">&#x1F4CF; Ruler</button>', 'Đo %">📏 Ruler</button>')
html = html.replace('Vẽ Line Ngang">&#9999; Vẽ Line</button>', 'Vẽ Line Ngang">✏️ Lines</button>')
html = html.replace('Xóa Lines">&#10060; Xóa Lines</button>', 'Xóa tất cả Lines">❌ Clear All</button>')

# Add user profile to topbar
topbar_str = '<div class="val" id="tb-total">0₫</div>\n      </div>'
user_profile_str = '''<div class="val" id="tb-total">0₫</div>
      </div>
      <div class="user-profile" onclick="showUserModal()">
        <div id="up-avatar">T</div>
        <div id="up-name">THieu</div>
      </div>'''
if '<div class="user-profile"' not in html:
    html = html.replace(topbar_str, user_profile_str)

# JS logic
user_logic = '''<script>
let currentUser = JSON.parse(localStorage.getItem('citrinex_user') || 'null');
if (!currentUser) {
    currentUser = { id: '001', name: 'THieu' };
    localStorage.setItem('citrinex_user', JSON.stringify(currentUser));
}
function updateProfileUI() {
    const av = document.getElementById('up-avatar');
    if(av) av.innerText = currentUser.name.charAt(0).toUpperCase();
    const nm = document.getElementById('up-name');
    if(nm) nm.innerText = currentUser.name;
}
function showUserModal() {
    document.getElementById('user-modal').classList.add('active');
    document.getElementById('user-id-input').value = currentUser.id;
    document.getElementById('user-name-input').value = currentUser.name;
}
function closeUserModal() { document.getElementById('user-modal').classList.remove('active'); }
function saveUser() {
    const uid = document.getElementById('user-id-input').value.trim() || '001';
    const uname = document.getElementById('user-name-input').value.trim() || 'THieu';
    currentUser = { id: uid, name: uname };
    localStorage.setItem('citrinex_user', JSON.stringify(currentUser));
    updateProfileUI();
    closeUserModal();
    window.location.reload();
}
const reqHeaders = () => ({ 'Content-Type': 'application/json', 'X-User-ID': currentUser.id });
'''
if 'let currentUser = JSON.parse' not in html:
    html = html.replace('<script>', user_logic, 1)

# Modal HTML
modal_html = '''
<div class="modal-overlay" id="user-modal">
  <div class="modal-content">
    <div class="modal-header">
      <div class="modal-title">Đăng nhập / Đổi User</div>
      <button class="modal-close" onclick="closeUserModal()">×</button>
    </div>
    <div class="modal-body">
      <div class="form-row">
        <label>User ID</label>
        <input type="text" id="user-id-input" placeholder="Ví dụ: 001">
      </div>
      <div class="form-row">
        <label>Tên hiển thị</label>
        <input type="text" id="user-name-input" placeholder="Ví dụ: THieu">
      </div>
      <button class="match-btn" style="width:100%;margin-top:10px" onclick="saveUser()">Đăng nhập</button>
      <p style="font-size:0.75rem;color:var(--dim);margin-top:10px;line-height:1.4">Không cần mật khẩu. Dữ liệu của bạn được phân tách theo User ID.</p>
    </div>
  </div>
</div>
'''
if 'id="user-modal"' not in html:
    html = html.replace('<script>', modal_html + '<script>', 1)

# Replace fetches
html = html.replace("fetch('/api/watchlist')", "fetch('/api/watchlist', { headers: reqHeaders() })")
html = html.replace("fetch('/api/portfolio')", "fetch('/api/portfolio', { headers: reqHeaders() })")
html = html.replace("fetch(`/api/notes/${ticker}`)", "fetch(`/api/notes/${ticker}`, { headers: reqHeaders() })")
html = html.replace("headers:{'Content-Type':'application/json'}", "headers:reqHeaders()")
html = html.replace("headers: {'Content-Type': 'application/json'}", "headers: reqHeaders()")
html = html.replace("headers: {'Content-Type':'application/json'}", "headers: reqHeaders()")
html = html.replace("fetch('/api/match_orders', { method: 'POST' })", "fetch('/api/match_orders', { method: 'POST', headers: reqHeaders() })")
html = html.replace("fetch('/api/force-sync', { method: 'POST' })", "fetch('/api/force-sync', { method: 'POST', headers: reqHeaders() })")

if 'updateProfileUI();' not in html:
    html = html.replace('fetchWatchlist();\n  fetchPortfolio();', 'updateProfileUI();\n  fetchWatchlist();\n  fetchPortfolio();')

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)


# Update app.py
with open('app.py', 'r', encoding='utf-8') as f:
    app_code = f.read()

# Replace get/save logic
replacements = {
    """def get_portfolio():
    try:
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"balance": 200000000, "holdings": [], "pending_orders": [], "trade_log": [], "equity_history": []}""": """def get_uid():
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
        return {"balance": 200000000, "holdings": [], "pending_orders": [], "trade_log": [], "equity_history": []}""",

    """def save_portfolio(data):
    with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    save_cloud_state_bg()""": """def save_portfolio(data):
    uid = get_uid()
    file_path = f"portfolio_{uid}.json"
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    save_cloud_state_bg()""",

    """def get_watchlist():
    try:
        with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []""": """def get_watchlist():
    uid = get_uid()
    file_path = f"watchlist_{uid}.json"
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []""",

    """def save_watchlist(data):
    with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    save_cloud_state_bg()""": """def save_watchlist(data):
    uid = get_uid()
    file_path = f"watchlist_{uid}.json"
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    save_cloud_state_bg()""",

    """def get_notes():
    try:
        with open(NOTES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}""": """def get_notes():
    uid = get_uid()
    file_path = f"notes_{uid}.json"
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}""",

    """def save_notes(data):
    with open(NOTES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    save_cloud_state_bg()""": """def save_notes(data):
    uid = get_uid()
    file_path = f"notes_{uid}.json"
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    save_cloud_state_bg()"""
}

for old, new in replacements.items():
    if old in app_code:
        app_code = app_code.replace(old, new)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(app_code)

print("Updated perfectly")
