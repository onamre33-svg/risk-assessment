from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from datetime import datetime
import sqlite3, hashlib, os, json

app = Flask(__name__)
app.secret_key = 'risk-assessment-secret-2024'

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'risk.db')

# ── DB 초기화 ──────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL,       -- master / manager / engineer
            team_id INTEGER,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            manager_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engineer_id INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            company TEXT,
            work_place TEXT,
            work_name TEXT,
            work_date TEXT,
            work_responsible TEXT,
            worker_count TEXT,
            pre_check TEXT,          -- JSON
            site_check TEXT,         -- JSON
            status TEXT DEFAULT 'pending',  -- pending/approved/rejected
            reject_reason TEXT,
            submitted_at TEXT DEFAULT (datetime('now','localtime')),
            reviewed_at TEXT,
            reviewer_id INTEGER,
            offline_id TEXT           -- 오프라인 임시 ID
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            assessment_id INTEGER,
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
    ''')
    # 기본 마스터 계정 생성
    pw = hashlib.sha256('admin1234'.encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO users (username,password,name,role) VALUES (?,?,?,?)",
              ('admin', pw, '관리자', 'master'))
    conn.commit()
    conn.close()

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def current_user():
    if 'user_id' not in session:
        return None
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE id=?", (session['user_id'],)).fetchone()
    conn.close()
    return u

def add_notification(user_id, message, assessment_id=None):
    conn = get_db()
    conn.execute("INSERT INTO notifications (user_id,message,assessment_id) VALUES (?,?,?)",
                 (user_id, message, assessment_id))
    conn.commit()
    conn.close()

# ── 인증 ───────────────────────────────────────────────
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hash_pw(request.form['password'])
        conn = get_db()
        u = conn.execute("SELECT * FROM users WHERE username=? AND password=?",
                         (username, password)).fetchone()
        teams = conn.execute("SELECT * FROM teams ORDER BY name").fetchall()
        conn.close()
        if u:
            session['user_id'] = u['id']
            session['role'] = u['role']
            return redirect(url_for('dashboard'))
        flash('아이디 또는 비밀번호가 틀렸습니다.', 'error')
        return render_template('login.html', teams=teams)
    conn = get_db()
    teams = conn.execute("SELECT * FROM teams ORDER BY name").fetchall()
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
    teams = conn.execute("SELECT * FROM teams ORDER BY name").fetchall()

    if not name or not username or not password:
        flash('모든 항목을 입력해주세요.', 'error')
        return render_template('login.html', teams=teams)
    if len(password) < 6:
        flash('비밀번호는 6자 이상이어야 합니다.', 'error')
        return render_template('login.html', teams=teams)
    if password != password2:
        flash('비밀번호가 일치하지 않습니다.', 'error')
        return render_template('login.html', teams=teams)
    if role not in ('engineer', 'manager'):
        role = 'engineer'

    existing = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    if existing:
        flash('이미 사용 중인 아이디입니다.', 'error')
        conn.close()
        return render_template('login.html', teams=teams)

    try:
        cur = conn.execute(
            "INSERT INTO users (username, password, name, role, team_id) VALUES (?,?,?,?,?)",
            (username, hash_pw(password), name, role, team_id)
        )
        new_id = cur.lastrowid
        if role == 'manager' and team_id:
            conn.execute("UPDATE teams SET manager_id=? WHERE id=?", (new_id, team_id))
        conn.commit()
        conn.close()
        flash(f'가입 완료! {name}님 환영합니다. 로그인해주세요 😊', 'success')
        return redirect(url_for('login'))
    except Exception:
        conn.close()
        flash('가입 중 오류가 발생했습니다. 다시 시도해주세요.', 'error')
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

    if u['role'] == 'master':
        assessments = conn.execute('''
            SELECT a.*, u.name as engineer_name, t.name as team_name
            FROM assessments a
            JOIN users u ON a.engineer_id=u.id
            JOIN teams t ON a.team_id=t.id
            ORDER BY a.submitted_at DESC LIMIT 50
        ''').fetchall()
        teams = conn.execute("SELECT * FROM teams").fetchall()
        users = conn.execute("SELECT * FROM users").fetchall()
        stats = {
            'total': conn.execute("SELECT COUNT(*) FROM assessments").fetchone()[0],
            'pending': conn.execute("SELECT COUNT(*) FROM assessments WHERE status='pending'").fetchone()[0],
            'approved': conn.execute("SELECT COUNT(*) FROM assessments WHERE status='approved'").fetchone()[0],
            'rejected': conn.execute("SELECT COUNT(*) FROM assessments WHERE status='rejected'").fetchone()[0],
        }
        conn.close()
        return render_template('dashboard_master.html', u=u, assessments=assessments,
                               teams=teams, users=users, stats=stats)

    elif u['role'] == 'manager':
        assessments = conn.execute('''
            SELECT a.*, u.name as engineer_name, t.name as team_name
            FROM assessments a
            JOIN users u ON a.engineer_id=u.id
            JOIN teams t ON a.team_id=t.id
            WHERE a.team_id=?
            ORDER BY a.submitted_at DESC
        ''', (u['team_id'],)).fetchall()
        stats = {
            'pending': conn.execute("SELECT COUNT(*) FROM assessments WHERE team_id=? AND status='pending'", (u['team_id'],)).fetchone()[0],
            'approved': conn.execute("SELECT COUNT(*) FROM assessments WHERE team_id=? AND status='approved'", (u['team_id'],)).fetchone()[0],
        }
        conn.close()
        return render_template('dashboard_manager.html', u=u, assessments=assessments, stats=stats)

    else:  # engineer
        assessments = conn.execute('''
            SELECT a.*, t.name as team_name
            FROM assessments a
            JOIN teams t ON a.team_id=t.id
            WHERE a.engineer_id=?
            ORDER BY a.submitted_at DESC
        ''', (u['id'],)).fetchall()
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
        pre_check = {
            'work_understanding': data.getlist('pre_1'),
            'work_environment': data.getlist('pre_2'),
            'tools_equipment': data.getlist('pre_3'),
            'ppe_check': data.getlist('pre_4'),
            'signal_system': data.getlist('pre_5'),
        }
        site_check = {}
        categories = ['fire','height','electric','chemical','confined','traffic','machinery','etc']
        for cat in categories:
            items = data.getlist(f'site_{cat}')
            risk_level = data.get(f'risk_{cat}', '')
            measure = data.get(f'measure_{cat}', '')
            if items or measure:
                site_check[cat] = {'items': items, 'risk_level': risk_level, 'measure': measure}

        conn = get_db()
        cur = conn.execute('''
            INSERT INTO assessments
            (engineer_id, team_id, company, work_place, work_name, work_date,
             work_responsible, worker_count, pre_check, site_check, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            u['id'], u['team_id'],
            data.get('company',''), data.get('work_place',''),
            data.get('work_name',''), data.get('work_date',''),
            data.get('work_responsible',''), data.get('worker_count','1인 단독'),
            json.dumps(pre_check, ensure_ascii=False),
            json.dumps(site_check, ensure_ascii=False),
            'pending'
        ))
        assessment_id = cur.lastrowid

        # 팀 담당자 찾기 → 알림
        team = conn.execute("SELECT * FROM teams WHERE id=?", (u['team_id'],)).fetchone()
        if team and team['manager_id']:
            add_notification(team['manager_id'],
                f"[승인 요청] {u['name']}님이 위험성평가를 제출했습니다.", assessment_id)

        # 안전관리자(master) 전체 알림
        masters = conn.execute("SELECT id FROM users WHERE role='master'").fetchall()
        for m in masters:
            add_notification(m['id'],
                f"[새 평가] {u['name']}님 위험성평가 제출 ({data.get('work_place','')})", assessment_id)

        conn.commit()
        conn.close()
        flash('위험성평가가 제출되었습니다. 담당자 승인을 기다려주세요.')
        return redirect(url_for('dashboard'))

    conn = get_db()
    team = conn.execute("SELECT * FROM teams WHERE id=?", (u['team_id'],)).fetchone()
    conn.close()
    return render_template('assessment_form.html', u=u, team=team,
                           today=datetime.now().strftime('%Y-%m-%d'))

# ── 평가 상세 조회 ──────────────────────────────────────
@app.route('/assessment/<int:aid>')
def view_assessment(aid):
    u = current_user()
    if not u:
        return redirect(url_for('login'))
    conn = get_db()
    a = conn.execute('''
        SELECT a.*, u.name as engineer_name, t.name as team_name
        FROM assessments a
        JOIN users u ON a.engineer_id=u.id
        JOIN teams t ON a.team_id=t.id
        WHERE a.id=?
    ''', (aid,)).fetchone()
    conn.close()
    if not a:
        return "없는 평가입니다.", 404
    # 권한 체크
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
    a = conn.execute("SELECT * FROM assessments WHERE id=?", (aid,)).fetchone()
    conn.execute('''
        UPDATE assessments SET status='approved', reviewed_at=datetime('now','localtime'),
        reviewer_id=? WHERE id=?
    ''', (u['id'], aid))
    # 엔지니어에게 알림
    add_notification(a['engineer_id'],
        f"✅ 위험성평가가 승인되었습니다. 작업을 진행할 수 있습니다.", aid)
    conn.commit()
    conn.close()
    return jsonify({'status': 'approved'})

@app.route('/assessment/<int:aid>/reject', methods=['POST'])
def reject_assessment(aid):
    u = current_user()
    if not u or u['role'] not in ('manager','master'):
        return jsonify({'error': '권한 없음'}), 403
    reason = request.json.get('reason', '')
    conn = get_db()
    a = conn.execute("SELECT * FROM assessments WHERE id=?", (aid,)).fetchone()
    conn.execute('''
        UPDATE assessments SET status='rejected', reject_reason=?,
        reviewed_at=datetime('now','localtime'), reviewer_id=? WHERE id=?
    ''', (reason, u['id'], aid))
    add_notification(a['engineer_id'],
        f"❌ 위험성평가가 반려되었습니다. 사유: {reason}", aid)
    conn.commit()
    conn.close()
    return jsonify({'status': 'rejected'})

# ── 알림 ───────────────────────────────────────────────
@app.route('/api/notifications')
def get_notifications():
    u = current_user()
    if not u:
        return jsonify([])
    conn = get_db()
    notes = conn.execute('''
        SELECT * FROM notifications WHERE user_id=?
        ORDER BY created_at DESC LIMIT 20
    ''', (u['id'],)).fetchall()
    conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (u['id'],))
    conn.commit()
    conn.close()
    return jsonify([dict(n) for n in notes])

@app.route('/api/notifications/count')
def notification_count():
    u = current_user()
    if not u:
        return jsonify({'count': 0})
    conn = get_db()
    cnt = conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0",
                       (u['id'],)).fetchone()[0]
    conn.close()
    return jsonify({'count': cnt})

# ── 사용자 관리 (마스터) ────────────────────────────────
@app.route('/admin/users', methods=['GET','POST'])
def admin_users():
    u = current_user()
    if not u or u['role'] != 'master':
        return redirect(url_for('dashboard'))
    conn = get_db()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_team':
            conn.execute("INSERT INTO teams (name) VALUES (?)", (request.form['team_name'],))
        elif action == 'add_user':
            pw = hash_pw(request.form['password'])
            tid = request.form.get('team_id') or None
            conn.execute("INSERT INTO users (username,password,name,role,team_id) VALUES (?,?,?,?,?)",
                         (request.form['username'], pw, request.form['name'],
                          request.form['role'], tid))
            # 팀 담당자면 teams.manager_id 업데이트
            if request.form['role'] == 'manager' and tid:
                new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute("UPDATE teams SET manager_id=? WHERE id=?", (new_id, tid))
        elif action == 'delete_user':
            conn.execute("DELETE FROM users WHERE id=? AND role!='master'",
                         (request.form['user_id'],))
        conn.commit()
    users = conn.execute('''
        SELECT u.*, t.name as team_name FROM users u
        LEFT JOIN teams t ON u.team_id=t.id ORDER BY u.role, u.name
    ''').fetchall()
    teams = conn.execute("SELECT * FROM teams").fetchall()
    conn.close()
    return render_template('admin_users.html', u=u, users=users, teams=teams)

# ── PWA 서비스워커 & 매니페스트 ────────────────────────
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
    sw_code = '''
const CACHE = "risk-v1";
const OFFLINE_URLS = ["/", "/assessment/new", "/static/css/style.css", "/static/js/app.js"];

self.addEventListener("install", e => {
    e.waitUntil(caches.open(CACHE).then(c => c.addAll(OFFLINE_URLS)));
});
self.addEventListener("fetch", e => {
    e.respondWith(
        fetch(e.request).catch(() => caches.match(e.request))
    );
});

// 오프라인 제출 데이터 백그라운드 동기화
self.addEventListener("sync", e => {
    if (e.tag === "sync-assessments") {
        e.waitUntil(syncOfflineData());
    }
});

async function syncOfflineData() {
    const db = await openDB();
    const pending = await db.getAll("offline_assessments");
    for (const item of pending) {
        try {
            await fetch("/assessment/new", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify(item)
            });
            await db.delete("offline_assessments", item.id);
        } catch(e) {}
    }
}
'''
    return Response(sw_code, mimetype='application/javascript')

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
