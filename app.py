import os
from flask import Flask, render_template, request, redirect, session, flash, g
import psycopg2
import psycopg2.extras
import random
import string
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

import requests

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback_dev_key_change_in_production")

BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
MAIL_FROM     = os.environ.get('MAIL_FROM', 'aistudyhub8@gmail.com')

DATABASE_URL = os.environ.get('DATABASE_URL', '')


def get_db():
    if 'db' not in g:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        g.db = conn
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          SERIAL PRIMARY KEY,
            email       TEXT UNIQUE,
            password    TEXT,
            is_verified INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS otps (
            id         SERIAL PRIMARY KEY,
            email      TEXT,
            otp        TEXT,
            purpose    TEXT,
            expires_at TEXT,
            used       INTEGER DEFAULT 0
        )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id         SERIAL PRIMARY KEY,
            email      TEXT,
            subject    TEXT,
            title      TEXT,
            type       TEXT,
            deadline   TEXT,
            hours      INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
    conn.commit()
    conn.close()

init_db()


def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def save_otp(email, otp, purpose):
    db = get_db()
    c  = db.cursor()
    c.execute(
        "UPDATE otps SET used=1 WHERE email=%s AND purpose=%s AND used=0",
        (email, purpose)
    )
    expires = (datetime.now() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "INSERT INTO otps(email,otp,purpose,expires_at,used) VALUES(%s,%s,%s,%s,0)",
        (email, otp, purpose, expires)
    )
    db.commit()

def verify_otp_code(email, otp, purpose):
    db  = get_db()
    c   = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        """SELECT id FROM otps
           WHERE email=%s AND otp=%s AND purpose=%s
             AND used=0 AND expires_at > %s""",
        (email, otp, purpose, now)
    )
    row = c.fetchone()
    if row:
        c.execute("UPDATE otps SET used=1 WHERE id=%s", (row["id"],))
        db.commit()
    return row is not None

def send_otp_email(email, otp, purpose):
    configs = {
        'register': {
            'label': 'Email Verification',
            'subject': '🎓 Verify your Academic Deadline Radar account',
            'headline': 'Welcome aboard! One last step.',
            'subtext': "You're almost in! Verify your email to start tracking your deadlines.",
            'color': '#4F46E5',
            'light': '#EEF2FF',
            'icon': '📬',
            'cta': 'Use this code to complete your registration:',
            'security_note': 'If you did not create an account with Academic Deadline Radar, you can safely ignore this email.'
        },
        'login': {
            'label': 'Login Verification',
            'subject': '🔐 Your Academic Deadline Radar login code',
            'headline': 'Someone (hopefully you!) is signing in.',
            'subtext': "Your one-time login code is ready. It expires in 10 minutes.",
            'color': '#0891B2',
            'light': '#ECFEFF',
            'icon': '🚀',
            'cta': 'Enter this code to access your account:',
            'security_note': 'If you did not attempt to log in, your password may be compromised. Consider changing it immediately.'
        },
        'forgot': {
            'label': 'Password Reset',
            'subject': '🔑 Reset your Academic Deadline Radar password',
            'headline': "Forgot your password? No worries.",
            'subtext': "It happens to the best of us. Use the code below to reset your password.",
            'color': '#D97706',
            'light': '#FFFBEB',
            'icon': '🔓',
            'cta': 'Use this code to reset your password:',
            'security_note': 'If you did not request a password reset, ignore this email. Your password will not change unless you use this code.'
        },
    }

    cfg = configs.get(purpose, {
        'label': 'Verification',
        'subject': 'Your Academic Deadline Radar OTP',
        'headline': 'Your verification code is here.',
        'subtext': 'Use the code below to continue.',
        'color': '#4F46E5',
        'light': '#EEF2FF',
        'icon': '✉️',
        'cta': 'Enter this code to continue:',
        'security_note': 'If you did not request this code, please ignore this email.'
    })

    # ── OTP digits split for individual boxes ──────────────────────────
    d = list(otp)
    digit_box = (
        "background:#111111;border:1px solid #b8860b;border-radius:6px;"
        "display:inline-block;width:40px;height:52px;line-height:52px;"
        "text-align:center;font-size:26px;font-weight:700;color:#ffd700;"
        "font-family:'Courier New',monospace;margin:0 3px;vertical-align:middle;"
    )
    separator = (
        "display:inline-block;width:12px;text-align:center;"
        "color:#4a3800;font-size:20px;vertical-align:middle;"
    )
    digits_html = (
        f'<span style="{digit_box}">{d[0]}</span>'
        f'<span style="{digit_box}">{d[1]}</span>'
        f'<span style="{digit_box}">{d[2]}</span>'
        f'<span style="{separator}">&#xb7;</span>'
        f'<span style="{digit_box}">{d[3]}</span>'
        f'<span style="{digit_box}">{d[4]}</span>'
        f'<span style="{digit_box}">{d[5]}</span>'
    )

    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{cfg['label']} — Academic Deadline Radar</title>
</head>
<body style="margin:0;padding:0;background:#111111;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#111111;padding:36px 0;">
  <tr>
    <td align="center">
      <table width="540" cellpadding="0" cellspacing="0"
             style="background:#0a0a0a;border-radius:12px;overflow:hidden;border:1px solid #2a2a2a;max-width:540px;">

        <!-- Gold top bar -->
        <tr>
          <td style="height:3px;background:linear-gradient(90deg,#111,#b8860b,#ffd700,#b8860b,#111);font-size:0;line-height:0;">&nbsp;</td>
        </tr>

        <!-- Header -->
        <tr>
          <td style="background:#0a0a0a;padding:32px 40px 24px;text-align:center;border-bottom:1px solid #1a1400;">
            <p style="margin:0 0 4px;font-size:10px;letter-spacing:4px;color:#6b5c00;text-transform:uppercase;">Academic</p>
            <p style="margin:0 0 4px;font-size:22px;font-weight:700;color:#ffd700;letter-spacing:1px;">Deadline Radar</p>
            <p style="margin:0;font-size:10px;letter-spacing:3px;color:#4a3800;text-transform:uppercase;">Never miss a deadline</p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:32px 40px 24px;">
            <p style="margin:0 0 8px;font-size:16px;font-weight:600;color:#c8a000;">{cfg['headline']}</p>
            <p style="margin:0 0 28px;font-size:14px;color:#888888;line-height:1.7;">{cfg['subtext']}</p>

            <!-- OTP label -->
            <p style="margin:0 0 12px;font-size:10px;letter-spacing:3px;color:#6b5000;text-transform:uppercase;text-align:center;">{cfg['cta']}</p>

            <!-- OTP digits -->
            <div style="text-align:center;margin:0 0 20px;">
              {digits_html}
            </div>

            <!-- Expiry notice -->
            <table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 20px;">
              <tr>
                <td style="background:#0f0d00;border:1px solid #2a1800;border-radius:8px;padding:12px 16px;">
                  <table cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="width:28px;vertical-align:middle;">
                        <div style="width:26px;height:26px;border-radius:50%;background:#1a1400;border:1px solid #b8860b;text-align:center;line-height:26px;font-size:13px;">&#128336;</div>
                      </td>
                      <td style="padding-left:10px;font-size:13px;color:#8a7000;vertical-align:middle;">
                        This code expires in <strong style="color:#c8a000;">10 minutes</strong>. Do not share it with anyone.
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>

            <!-- Thin gold divider -->
            <div style="height:1px;background:linear-gradient(90deg,#111,#2a1800,#111);margin:0 0 20px;"></div>

            <!-- Security note -->
            <p style="margin:0;font-size:12px;color:#555555;line-height:1.7;padding-left:12px;border-left:2px solid #2a1800;">
              {cfg['security_note']}
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#050500;padding:18px 40px;text-align:center;border-top:1px solid #1a1400;">
            <p style="margin:0 0 4px;font-size:11px;letter-spacing:2px;color:#4a3800;text-transform:uppercase;">Academic Deadline Radar</p>
            <p style="margin:0;font-size:11px;color:#333333;">automated message — please do not reply</p>
          </td>
        </tr>

        <!-- Gold bottom bar -->
        <tr>
          <td style="height:2px;background:linear-gradient(90deg,#111,#b8860b,#ffd700,#b8860b,#111);font-size:0;line-height:0;">&nbsp;</td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>"""

    plain_body = (
        f"Academic Deadline Radar — {cfg['label']}\n\n"
        f"{cfg['headline']}\n"
        f"{cfg['subtext']}\n\n"
        f"Your OTP: {otp}\n\n"
        f"This code expires in 10 minutes.\n"
        f"If you didn't request this, ignore this email.\n\n"
        f"— Academic Deadline Radar Team"
    )

    print(f"\n{'='*50}\n  OTP [{purpose.upper()}] for {email}: {otp}\n{'='*50}\n")

    if BREVO_API_KEY:
        try:
            response = requests.post(
                'https://api.brevo.com/v3/smtp/email',
                headers={
                    'api-key': BREVO_API_KEY,
                    'Content-Type': 'application/json'
                },
                json={
                    'sender': {'name': 'Academic Deadline Radar', 'email': MAIL_FROM},
                    'to': [{'email': email}],
                    'subject': cfg['subject'],
                    'htmlContent': html_body,
                    'textContent': plain_body
                },
                timeout=30
            )
            if response.status_code in (200, 201):
                print("[Mail] Sent successfully via Brevo!")
                return True
            else:
                print(f"[Mail Error] Brevo: {response.status_code} {response.text}")
        except Exception as e:
            print(f"[Mail Error] {e}")
    return False


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user' in session:
        return redirect('/dashboard')
    if request.method == 'POST':
        email    = request.form['email'].strip().lower()
        password = request.form['password']

        if '@' not in email or '.' not in email:
            flash("Please enter a valid email address.", "error")
            return redirect('/register')
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return redirect('/register')

        db = get_db()
        c  = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT id, is_verified FROM users WHERE email=%s", (email,))
        existing = c.fetchone()

        if existing and existing['is_verified'] == 1:
            flash("Email already registered. Please login.", "error")
            return redirect('/login')

        hashed = generate_password_hash(password)
        if not existing:
            c.execute(
                "INSERT INTO users(email,password,is_verified) VALUES(%s,%s,0)",
                (email, hashed)
            )
        else:
            c.execute(
                "UPDATE users SET password=%s WHERE email=%s", (hashed, email)
            )
        db.commit()

        otp  = generate_otp()
        save_otp(email, otp, 'register')
        sent = send_otp_email(email, otp, 'register')

        session['otp_email']   = email
        session['otp_purpose'] = 'register'

        flash(
            f"OTP sent to {email}. Check your inbox." if sent
            else f"OTP: {otp}  (check Render logs)",
            "success" if sent else "info"
        )
        return redirect('/verify-otp')
    return render_template('register.html')


@app.route('/',      methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect('/dashboard')
    if request.method == 'POST':
        email    = request.form['email'].strip().lower()
        password = request.form['password']

        db = get_db()
        c  = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT password, is_verified FROM users WHERE email=%s", (email,))
        user = c.fetchone()

        if not user:
            flash("No account found with this email.", "error")
            return redirect('/login')
        if not check_password_hash(user['password'], password):
            flash("Incorrect password.", "error")
            return redirect('/login')

        if not user['is_verified']:
            session['otp_email']   = email
            session['otp_purpose'] = 'register'
            flash("Please verify your email first.", "error")
            return redirect('/verify-otp')

        otp  = generate_otp()
        save_otp(email, otp, 'login')
        sent = send_otp_email(email, otp, 'login')

        session['otp_email']   = email
        session['otp_purpose'] = 'login'

        flash(
            f"OTP sent to {email}." if sent
            else f"OTP: {otp}  (check Render logs)",
            "success" if sent else "info"
        )
        return redirect('/verify-otp')
    return render_template('login.html')


@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    email   = session.get('otp_email')
    purpose = session.get('otp_purpose')
    if not email or not purpose:
        return redirect('/login')

    if request.method == 'POST':
        otp = ''.join(
            request.form.get(f'd{i}', '') for i in range(1, 7)
        ).strip()

        if verify_otp_code(email, otp, purpose):
            if purpose == 'register':
                db = get_db()
                c  = db.cursor()
                c.execute("UPDATE users SET is_verified=1 WHERE email=%s", (email,))
                db.commit()
                session.pop('otp_email',   None)
                session.pop('otp_purpose', None)
                flash("Email verified! Please login.", "success")
                return redirect('/login')
            elif purpose == 'login':
                session['user'] = email
                session.pop('otp_email',   None)
                session.pop('otp_purpose', None)
                return redirect('/dashboard')
            elif purpose == 'forgot':
                session['reset_email'] = email
                session.pop('otp_email',   None)
                session.pop('otp_purpose', None)
                return redirect('/reset-password')
        else:
            flash("Invalid or expired OTP. Try again.", "error")
            return redirect('/verify-otp')

    return render_template('verify_otp.html', email=email, purpose=purpose)


@app.route('/resend-otp')
def resend_otp():
    email   = session.get('otp_email')
    purpose = session.get('otp_purpose')
    if not email or not purpose:
        return redirect('/login')

    otp  = generate_otp()
    save_otp(email, otp, purpose)
    sent = send_otp_email(email, otp, purpose)

    flash(
        "New OTP sent to your email." if sent
        else f"New OTP: {otp}  (check Render logs)",
        "success" if sent else "info"
    )
    return redirect('/verify-otp')


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        db    = get_db()
        c     = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT id FROM users WHERE email=%s AND is_verified=1", (email,))
        user  = c.fetchone()

        if not user:
            flash("No verified account found with this email.", "error")
            return redirect('/forgot-password')

        otp  = generate_otp()
        save_otp(email, otp, 'forgot')
        sent = send_otp_email(email, otp, 'forgot')

        session['otp_email']   = email
        session['otp_purpose'] = 'forgot'

        flash(
            f"Reset OTP sent to {email}." if sent
            else f"OTP: {otp}  (check Render logs)",
            "success" if sent else "info"
        )
        return redirect('/verify-otp')
    return render_template('forgot_password.html')


@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    email = session.get('reset_email')
    if not email:
        return redirect('/login')

    if request.method == 'POST':
        password = request.form['password']
        confirm  = request.form['confirm']

        if password != confirm:
            flash("Passwords do not match.", "error")
            return redirect('/reset-password')
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return redirect('/reset-password')

        db = get_db()
        c  = db.cursor()
        c.execute(
            "UPDATE users SET password=%s WHERE email=%s",
            (generate_password_hash(password), email)
        )
        db.commit()
        session.pop('reset_email', None)
        flash("Password reset! Please login.", "success")
        return redirect('/login')

    return render_template('reset_password.html')


@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')

    db = get_db()
    c  = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute(
        "SELECT * FROM tasks WHERE email=%s ORDER BY deadline ASC",
        (session['user'],)
    )
    rows  = c.fetchall()
    tasks = []
    today = datetime.now().date()

    for r in rows:
        deadline_date  = datetime.strptime(r['deadline'], "%Y-%m-%d").date()
        days_left      = (deadline_date - today).days
        priority_score = (max(days_left, 0) * 2) + int(r['hours'])

        if days_left < 0:
            color = "overdue"
        elif days_left <= 1:
            color = "urgent"
        elif days_left <= 3:
            color = "high"
        elif days_left <= 7:
            color = "medium"
        else:
            color = "safe"

        tasks.append({
            "id":             r['id'],
            "subject":        r['subject'],
            "title":          r['title'],
            "type":           r['type'],
            "deadline":       r['deadline'],
            "hours":          r['hours'],
            "days_left":      days_left,
            "color":          color,
            "priority_score": priority_score
        })

    tasks.sort(key=lambda x: x['priority_score'])
    return render_template('dashboard.html', email=session['user'], tasks=tasks)


@app.route('/add_task', methods=['POST'])
def add_task():
    if 'user' not in session:
        return redirect('/login')

    subject  = request.form['subject'].strip()
    title    = request.form['title'].strip()
    type_    = request.form['type']
    deadline = request.form['deadline']
    try:
        hours = max(0, int(request.form['hours']))
    except ValueError:
        hours = 0

    db = get_db()
    c  = db.cursor()
    c.execute(
        "INSERT INTO tasks(email,subject,title,type,deadline,hours) VALUES(%s,%s,%s,%s,%s,%s)",
        (session['user'], subject, title, type_, deadline, hours)
    )
    db.commit()
    return redirect('/dashboard')


@app.route('/edit_task/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    if 'user' not in session:
        return redirect('/login')

    db = get_db()
    c  = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM tasks WHERE id=%s AND email=%s", (task_id, session['user']))
    task = c.fetchone()

    if not task:
        flash("Task not found.", "error")
        return redirect('/dashboard')

    if request.method == 'POST':
        subject  = request.form['subject'].strip()
        title    = request.form['title'].strip()
        type_    = request.form['type']
        deadline = request.form['deadline']
        try:
            hours = max(0, int(request.form['hours']))
        except ValueError:
            hours = 0

        c.execute(
            """UPDATE tasks SET subject=%s, title=%s, type=%s, deadline=%s, hours=%s
               WHERE id=%s AND email=%s""",
            (subject, title, type_, deadline, hours, task_id, session['user'])
        )
        db.commit()
        flash("Task updated successfully.", "success")
        return redirect('/dashboard')

    return render_template('edit_task.html', task=task)


@app.route('/delete_task/<int:task_id>')
def delete_task(task_id):
    if 'user' not in session:
        return redirect('/login')

    db = get_db()
    c  = db.cursor()
    c.execute("DELETE FROM tasks WHERE id=%s AND email=%s", (task_id, session['user']))
    db.commit()
    return redirect('/dashboard')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


if __name__ == '__main__':
    app.run(debug=True)