import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

user_logic = '''
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

<script>
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

if 'function saveUser()' not in html:
    html = html.replace('</body>', user_logic + '\n</body>')

# Replace exact fetch calls
html = re.sub(r"fetch\('/api/watchlist'\)", "fetch('/api/watchlist', { headers: reqHeaders() })", html)
html = re.sub(r"fetch\('/api/portfolio'\)", "fetch('/api/portfolio', { headers: reqHeaders() })", html)
html = re.sub(r"fetch\(`/api/notes/\$\{ticker\}`\)", "fetch(`/api/notes/${ticker}`, { headers: reqHeaders() })", html)
html = html.replace("{'Content-Type':'application/json'}", "reqHeaders()")
html = html.replace("{'Content-Type': 'application/json'}", "reqHeaders()")

html = html.replace("fetch('/api/match_orders', { method: 'POST' })", "fetch('/api/match_orders', { method: 'POST', headers: reqHeaders() })")
html = html.replace("fetch('/api/force-sync', { method: 'POST' })", "fetch('/api/force-sync', { method: 'POST', headers: reqHeaders() })")

if 'updateProfileUI();' not in html:
    html = html.replace('fetchWatchlist();\n  fetchPortfolio();', 'updateProfileUI();\n  fetchWatchlist();\n  fetchPortfolio();')

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Updated HTML logic correctly")
