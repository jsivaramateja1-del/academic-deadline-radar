import os
from flask import Flask, render_template, request, redirect, session, flash, g
import sqlite3
import random
import string
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

try:
    from flask_mail import Mail, Message
    MAIL_AVAILABLE = True
except ImportError:
    MAIL_AVAILABLE = False

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback_dev_key_change_in_production")

app.config['MAIL_SERVER']         = 'smtp.gmail.com'
app.config['MAIL_PORT']           = 587
app.config['MAIL_USE_TLS']        = True
app.config['MAIL_USERNAME']       = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD']       = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', '')

if MAIL_AVAILABLE:
    mail = Mail(app)


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect("database.db")
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT UNIQUE,
            password    TEXT,
            is_verified INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS otps (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT,
            otp        TEXT,
            purpose    TEXT,
            expires_at TEXT,
            used       INTEGER DEFAULT 0
        )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
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
    db.execute(
        "UPDATE otps SET used=1 WHERE email=? AND purpose=? AND used=0",
        (email, purpose)
    )
    expires = (datetime.now() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "INSERT INTO otps(email,otp,purpose,expires_at,used) VALUES(?,?,?,?,0)",
        (email, otp, purpose, expires)
    )
    db.commit()

def verify_otp_code(email, otp, purpose):
    db  = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = db.execute(
        """SELECT id FROM otps
           WHERE email=? AND otp=? AND purpose=?
             AND used=0 AND expires_at > ?""",
        (email, otp, purpose, now)
    ).fetchone()
    if row:
        db.execute("UPDATE otps SET used=1 WHERE id=?", (row["id"],))
        db.commit()
    return row is not None

def send_otp_email(email, otp, purpose):
    labels = {
        'register': 'Email Verification',
        'login':    'Login Verification',
        'forgot':   'Password Reset'
    }
    label = labels.get(purpose, 'Verification')
    body  = (
        f"Academic Deadline Radar — {label}\n\n"
        f"Your OTP is: {otp}\n\n"
        f"This code expires in 10 minutes.\n"
        f"If you did not request this, ignore this email.\n\n"
        f"— Academic Deadline Radar Team"
    )
    print(f"\n{'='*50}\n  OTP [{purpose.upper()}] for {email}: {otp}\n{'='*50}\n")
    if MAIL_AVAILABLE and app.config['MAIL_USERNAME']:
        try:
            mail.send(Message(
                subject=f"Your {label} OTP — Academic Deadline Radar",
                recipients=[email],
                body=body
            ))
            return True
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

        db       = get_db()
        existing = db.execute(
            "SELECT id, is_verified FROM users WHERE email=?", (email,)
        ).fetchone()

        if existing and existing['is_verified'] == 1:
            flash("Email already registered. Please login.", "error")
            return redirect('/login')

        hashed = generate_password_hash(password)
        if not existing:
            db.execute(
                "INSERT INTO users(email,password,is_verified) VALUES(?,?,0)",
                (email, hashed)
            )
        else:
            db.execute(
                "UPDATE users SET password=? WHERE email=?", (hashed, email)
            )
        db.commit()

        otp  = generate_otp()
        save_otp(email, otp, 'register')
        sent = send_otp_email(email, otp, 'register')

        session['otp_email']   = email
        session['otp_purpose'] = 'register'

        flash(
            f"OTP sent to {email}. Check your inbox." if sent
            else f"OTP: {otp}  (email not configured — see console)",
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

        db   = get_db()
        user = db.execute(
            "SELECT password, is_verified FROM users WHERE email=?", (email,)
        ).fetchone()

        if not user or not check_password_hash(user['password'], password):
            flash("Incorrect email or password.", "error")
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
            else f"OTP: {otp}  (see console)",
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
                get_db().execute(
                    "UPDATE users SET is_verified=1 WHERE email=?", (email,)
                )
                get_db().commit()
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
        else f"New OTP: {otp}  (see console)",
        "success" if sent else "info"
    )
    return redirect('/verify-otp')


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        db    = get_db()
        user  = db.execute(
            "SELECT id FROM users WHERE email=? AND is_verified=1", (email,)
        ).fetchone()

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
            else f"OTP: {otp}  (see console)",
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
        db.execute(
            "UPDATE users SET password=? WHERE email=?",
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

    db   = get_db()
    rows = db.execute(
        "SELECT * FROM tasks WHERE email=? ORDER BY deadline ASC",
        (session['user'],)
    ).fetchall()

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
    db.execute(
        "INSERT INTO tasks(email,subject,title,type,deadline,hours) VALUES(?,?,?,?,?,?)",
        (session['user'], subject, title, type_, deadline, hours)
    )
    db.commit()
    return redirect('/dashboard')


@app.route('/edit_task/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    if 'user' not in session:
        return redirect('/login')

    db   = get_db()
    task = db.execute(
        "SELECT * FROM tasks WHERE id=? AND email=?",
        (task_id, session['user'])
    ).fetchone()

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

        db.execute(
            """UPDATE tasks SET subject=?, title=?, type=?, deadline=?, hours=?
               WHERE id=? AND email=?""",
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
    db.execute(
        "DELETE FROM tasks WHERE id=? AND email=?",
        (task_id, session['user'])
    )
    db.commit()
    return redirect('/dashboard')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


if __name__ == '__main__':
    app.run(debug=True)