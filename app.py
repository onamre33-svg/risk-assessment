from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, make_response
from datetime import datetime
import hashlib, os, json
try:
    from weasyprint import HTML
    WEASYPRINT_OK = True
except:
    WEASYPRINT_OK = False
import psycopg2
import psycopg2.extras

app = Flask(__name__)
app.secret_key = 'risk-assessment-secret-2024'

DATABASE_URL = os.environ.get('DATABASE_URL', '')

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def fetchone(cur):
    row = cur.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))

def fetchall(cur):
    rows = cur.fetchall()
    if not rows:
        return []
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        team_id INTEGER,
        created_at TEXT DEFAULT to_char(NOW(),'YYYY-MM-DD HH24:MI:SS')
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS teams (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        manager_id INTEGER
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS assessments (
        id SERIAL PRIMARY KEY,
        engineer_id INTEGER NOT NULL,
        team_id INTEGER NOT NULL,
        company TEXT, work_place TEXT, work_name TEXT, work_date TEXT,
        work_responsible TEXT, worker_count TEXT,
        pre_check TEXT, site_check TEXT,
        status TEXT DEFAULT 'pending',
        reject_reason TEXT,
        submitted_at TEXT DEFAULT to_char(NOW(),'YYYY-MM-DD HH24:MI:SS'),
        reviewed_at TEXT, reviewer_id INTEGER,
        offline_id TEXT, sign_requester TEXT, sign_worker TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS notifications (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        assessment_id INTEGER,
        is_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT to_char(NOW(),'YYYY-MM-DD HH24:MI:SS')
    )""")
    pw = hashlib.sha256('admin1234'.encode()).hexdigest()
    c.execute("INSERT INTO users (username,password,name,role) VALUES (%s,%s,%s,%s) ON CONFLICT (username) DO NOTHING",
              ('admin', pw, '관리자', 'master'))
    conn.commit()
    conn.close()

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def current_user():
    if 'user_id' not in session:
        return None
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=%s", (session['user_id'],))
    u = fetchone(c)
    conn.close()
    return u

def add_notification(user_id, message, assessment_id=None):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO notifications (user_id,message,assessment_id) VALUES (%s,%s,%s)",
                  (user_id, message, assessment_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Notification error: {e}")

# ── 인증 ───────────────────────────────────────────────
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hash_pw(request.form['password'])
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
        u = fetchone(c)
        c.execute("SELECT * FROM teams ORDER BY name")
        teams = fetchall(c)
        conn.close()
        if u:
            session['user_id'] = u['id']
            session['role'] = u['role']
            return redirect(url_for('dashboard'))
        flash('아이디 또는 비밀번호가 틀렸습니다.', 'error')
        return render_template('login.html', teams=teams)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM teams ORDER BY name")
    teams = fetchall(c)
    conn.close()
    return render_template('login.html', teams=teams)

@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name','').strip()
    username = request.form.get('username','').strip()
    password = request.form.get('password','')
    password2 = request.form.get('password2','')
    role = request.form.get('role','engineer')
    team_id = request.form.get('team_id') or None

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM teams ORDER BY name")
    teams = fetchall(c)

    if not name or not username or not password:
        flash('모든 항목을 입력해주세요.', 'error')
        conn.close()
        return render_template('login.html', teams=teams)
    if len(password) < 6:
        flash('비밀번호는 6자 이상이어야 합니다.', 'error')
        conn.close()
        return render_template('login.html', teams=teams)
    if password != password2:
        flash('비밀번호가 일치하지 않습니다.', 'error')
        conn.close()
        return render_template('login.html', teams=teams)
    if role not in ('engineer', 'manager'):
        role = 'engineer'

    c.execute("SELECT id FROM users WHERE username=%s", (username,))
    if fetchone(c):
        flash('이미 사용 중인 아이디입니다.', 'error')
        conn.close()
        return render_template('login.html', teams=teams)

    try:
        c.execute("INSERT INTO users (username,password,name,role,team_id) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                  (username, hash_pw(password), name, role, team_id))
        new_id = c.fetchone()[0]
        if role == 'manager' and team_id:
            c.execute("UPDATE teams SET manager_id=%s WHERE id=%s", (new_id, team_id))
        conn.commit()
        conn.close()
        flash(f'가입 완료! {name}님 환영합니다. 로그인해주세요 😊', 'success')
        return redirect(url_for('login'))
    except Exception:
        conn.close()
        flash('가입 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── 대시보드 ────────────────────────────────────────────
@app.route('/')
def dashboard():
    u = current_user()
    if not u:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()

    if u['role'] == 'master':
        c.execute('''SELECT a.*, u.name as engineer_name, t.name as team_name
            FROM assessments a JOIN users u ON a.engineer_id=u.id
            JOIN teams t ON a.team_id=t.id ORDER BY a.submitted_at DESC LIMIT 50''')
        assessments = fetchall(c)
        c.execute("SELECT * FROM teams")
        teams = fetchall(c)
        c.execute("SELECT * FROM users")
        users = fetchall(c)
        c.execute("SELECT COUNT(*) FROM assessments"); stats_total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM assessments WHERE status='pending'"); stats_pending = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM assessments WHERE status='approved'"); stats_approved = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM assessments WHERE status='rejected'"); stats_rejected = c.fetchone()[0]
        stats = {'total': stats_total, 'pending': stats_pending, 'approved': stats_approved, 'rejected': stats_rejected}
        conn.close()
        return render_template('dashboard_master.html', u=u, assessments=assessments,
                               teams=teams, users=users, stats=stats)

    elif u['role'] == 'manager':
        c.execute('''SELECT a.*, u.name as engineer_name, t.name as team_name
            FROM assessments a JOIN users u ON a.engineer_id=u.id
            JOIN teams t ON a.team_id=t.id WHERE a.team_id=%s
            ORDER BY a.submitted_at DESC''', (u['team_id'],))
        assessments = fetchall(c)
        c.execute("SELECT COUNT(*) FROM assessments WHERE team_id=%s AND status='pending'", (u['team_id'],)); p = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM assessments WHERE team_id=%s AND status='approved'", (u['team_id'],)); a2 = c.fetchone()[0]
        stats = {'pending': p, 'approved': a2}
        conn.close()
        return render_template('dashboard_manager.html', u=u, assessments=assessments, stats=stats)

    else:
        c.execute('''SELECT a.*, t.name as team_name FROM assessments a
            JOIN teams t ON a.team_id=t.id WHERE a.engineer_id=%s
            ORDER BY a.submitted_at DESC''', (u['id'],))
        assessments = fetchall(c)
        conn.close()
        return render_template('dashboard_engineer.html', u=u, assessments=assessments)

# ── 위험성평가 작성 ─────────────────────────────────────
@app.route('/assessment/new', methods=['GET','POST'])
def new_assessment():
    u = current_user()
    if not u or u['role'] != 'engineer':
        return redirect(url_for('login'))

    if request.method == 'POST':
        data = request.form
        pre_check = {k: data.get(k,'') for k in [
            'pre_1_1','pre_1_2','pre_1_3','pre_2_1','pre_2_2','pre_2_3',
            'pre_3_1','pre_3_2','pre_3_3','pre_4_1','pre_4_2','pre_5_1','pre_5_2'
        ]}
        site_keys = ['mgmt_1','mgmt_2','mgmt_3','fac_1','pmt_1','pmt_2',
            'conf_1','conf_2','conf_3','conf_4','conf_5',
            'hgt_1','hgt_2','hgt_3','hgt_4','hgt_5',
            'fire_1','fire_2','chem_1','chem_2','equip_1','equip_2',
            'trans_1','trans_2','heavy_1','heavy_2','mach_1','mach_2','etc_1']
        site_check = {f'site_{k}': data.get(f'site_{k}','해당없음') for k in site_keys}
        for k in ['mgmt','facility','permit','confined','height','fire','chemical','equip','transport','heavy','machine','etc']:
            site_check[f'measure_{k}'] = data.get(f'measure_{k}','')

        sign_worker = data.get('sign_worker') or data.get('sign_worker_1','')

        conn = get_db()
        c = conn.cursor()
        c.execute('''INSERT INTO assessments
            (engineer_id,team_id,company,work_place,work_name,work_date,
             work_responsible,worker_count,pre_check,site_check,status,sign_requester,sign_worker)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (u['id'], u['team_id'],
             data.get('company',''), data.get('work_place',''),
             data.get('work_name',''), data.get('work_date',''),
             data.get('work_responsible',''), data.get('worker_count','1인 단독'),
             json.dumps(pre_check, ensure_ascii=False),
             json.dumps(site_check, ensure_ascii=False),
             'pending', data.get('sign_requester',''), sign_worker))
        assessment_id = c.fetchone()[0]

        c.execute("SELECT * FROM teams WHERE id=%s", (u['team_id'],))
        team = fetchone(c)
        if team and team['manager_id']:
            add_notification(team['manager_id'],
                f"[승인 요청] {u['name']}님이 위험성평가를 제출했습니다.", assessment_id)
        c.execute("SELECT id FROM users WHERE role='master'")
        masters = fetchall(c)
        for m in masters:
            add_notification(m['id'],
                f"[새 평가] {u['name']}님 위험성평가 제출 ({data.get('work_place','')})", assessment_id)

        conn.commit()
        conn.close()
        flash('위험성평가가 제출되었습니다. 담당자 승인을 기다려주세요.')
        return redirect(url_for('dashboard'))

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM teams WHERE id=%s", (u['team_id'],))
    team = fetchone(c)
    conn.close()
    return render_template('assessment_form.html', u=u, team=team,
                           today=datetime.now().strftime('%Y-%m-%d'))

# ── 평가 상세 ───────────────────────────────────────────
@app.route('/assessment/<int:aid>')
def view_assessment(aid):
    u = current_user()
    if not u:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT a.*, u.name as engineer_name, t.name as team_name
        FROM assessments a JOIN users u ON a.engineer_id=u.id
        JOIN teams t ON a.team_id=t.id WHERE a.id=%s''', (aid,))
    a = fetchone(c)
    conn.close()
    if not a:
        return "없는 평가입니다.", 404
    if u['role'] == 'engineer' and a['engineer_id'] != u['id']:
        return "권한 없음", 403
    if u['role'] == 'manager' and a['team_id'] != u['team_id']:
        return "권한 없음", 403
    pre = json.loads(a['pre_check'] or '{}')
    site = json.loads(a['site_check'] or '{}')
    return render_template('assessment_detail.html', u=u, a=a, pre=pre, site=site)

# ── 승인 / 반려 ─────────────────────────────────────────
@app.route('/assessment/<int:aid>/approve', methods=['POST'])
def approve_assessment(aid):
    u = current_user()
    if not u or u['role'] not in ('manager','master'):
        return jsonify({'error': '권한 없음'}), 403
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM assessments WHERE id=%s", (aid,))
    a = fetchone(c)
    c.execute("UPDATE assessments SET status='approved', reviewed_at=%s, reviewer_id=%s WHERE id=%s",
              (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), u['id'], aid))
    conn.commit()
    conn.close()
    add_notification(a['engineer_id'], "✅ 위험성평가가 승인되었습니다. 작업을 진행할 수 있습니다.", aid)
    return jsonify({'status': 'approved'})

@app.route('/assessment/<int:aid>/reject', methods=['POST'])
def reject_assessment(aid):
    u = current_user()
    if not u or u['role'] not in ('manager','master'):
        return jsonify({'error': '권한 없음'}), 403
    reason = request.json.get('reason', '')
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM assessments WHERE id=%s", (aid,))
    a = fetchone(c)
    c.execute("UPDATE assessments SET status='rejected', reject_reason=%s, reviewed_at=%s, reviewer_id=%s WHERE id=%s",
              (reason, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), u['id'], aid))
    conn.commit()
    conn.close()
    add_notification(a['engineer_id'], f"❌ 위험성평가가 반려되었습니다. 사유: {reason}", aid)
    return jsonify({'status': 'rejected'})

# ── 알림 ───────────────────────────────────────────────
@app.route('/api/notifications')
def get_notifications():
    u = current_user()
    if not u:
        return jsonify([])
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 20", (u['id'],))
    notes = fetchall(c)
    c.execute("UPDATE notifications SET is_read=1 WHERE user_id=%s", (u['id'],))
    conn.commit()
    conn.close()
    return jsonify(notes)

@app.route('/api/notifications/count')
def notification_count():
    u = current_user()
    if not u:
        return jsonify({'count': 0})
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM notifications WHERE user_id=%s AND is_read=0", (u['id'],))
    cnt = c.fetchone()[0]
    conn.close()
    return jsonify({'count': cnt})

# ── 사용자 관리 (마스터) ────────────────────────────────
@app.route('/admin/users', methods=['GET','POST'])
def admin_users():
    u = current_user()
    if not u or u['role'] != 'master':
        return redirect(url_for('dashboard'))
    conn = get_db()
    c = conn.cursor()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_team':
            c.execute("INSERT INTO teams (name) VALUES (%s)", (request.form['team_name'],))
        elif action == 'add_user':
            pw = hash_pw(request.form['password'])
            tid = request.form.get('team_id') or None
            c.execute("INSERT INTO users (username,password,name,role,team_id) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                      (request.form['username'], pw, request.form['name'], request.form['role'], tid))
            new_id = c.fetchone()[0]
            if request.form['role'] == 'manager' and tid:
                c.execute("UPDATE teams SET manager_id=%s WHERE id=%s", (new_id, tid))
        elif action == 'delete_user':
            c.execute("DELETE FROM users WHERE id=%s AND role!='master'", (request.form['user_id'],))
        conn.commit()

    c.execute('''SELECT u.*, t.name as team_name FROM users u
        LEFT JOIN teams t ON u.team_id=t.id ORDER BY u.role, u.name''')
    users = fetchall(c)
    c.execute("SELECT * FROM teams")
    teams = fetchall(c)
    conn.close()
    return render_template('admin_users.html', u=u, users=users, teams=teams)

# ── PDF ─────────────────────────────────────────────────
@app.route('/assessment/<int:aid>/pdf')
def download_pdf(aid):
    u = current_user()
    if not u:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT a.*, u.name as engineer_name, t.name as team_name
        FROM assessments a JOIN users u ON a.engineer_id=u.id
        JOIN teams t ON a.team_id=t.id WHERE a.id=%s''', (aid,))
    a = fetchone(c)
    conn.close()
    if not a:
        return "없는 평가입니다.", 404
    pre = json.loads(a['pre_check'] or '{}')
    site = json.loads(a['site_check'] or '{}')
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    if not WEASYPRINT_OK:
        return "PDF 생성 라이브러리가 설치되지 않았습니다.", 500
    html_content = render_template('assessment_pdf.html', a=a, pre=pre, site=site, now=now)
    pdf = HTML(string=html_content).write_pdf()
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=risk_assessment_{aid}.pdf'
    return response

# ── PWA ─────────────────────────────────────────────────
@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "위험성평가 시스템",
        "short_name": "위험성평가",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#1a73e8",
        "theme_color": "#1a73e8",
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"}
        ]
    })

@app.route('/sw.js')
def service_worker():
    from flask import Response
    sw_code = """
const CACHE = "risk-v1";
const OFFLINE_URLS = ["/", "/assessment/new", "/static/css/style.css"];
self.addEventListener("install", e => {
    e.waitUntil(caches.open(CACHE).then(c => c.addAll(OFFLINE_URLS)));
});
self.addEventListener("fetch", e => {
    e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});
"""
    return Response(sw_code, mimetype='application/javascript')

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
