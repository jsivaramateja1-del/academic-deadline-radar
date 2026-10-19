import os
import random
import string
from datetime import datetime, timedelta, date

from flask import (
    Flask, render_template, request, redirect,
    session, flash, g, abort, url_for
)
from flask_wtf.csrf import CSRFProtect
import psycopg2
import psycopg2.extras
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import requests

load_dotenv()

app = Flask(__name__)

# ── Security ──────────────────────────────────────────────────────────────────
_secret = os.environ.get("SECRET_KEY", "")
if not _secret:
    raise RuntimeError("SECRET_KEY env var is required and must not be empty.")
app.secret_key = _secret
app.config["WTF_CSRF_TIME_LIMIT"] = 3600

csrf = CSRFProtect(app)

# ── Config ───────────────────────────────────────────────────────────────────
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
MAIL_FROM     = os.environ.get("MAIL_FROM", "noreply@deadlineradar.app")
DATABASE_URL  = os.environ.get("DATABASE_URL", "")

TASK_TYPES    = ["Assignment", "Exam", "Lab", "Project", "Quiz"]
MAX_SUBJECT   = 80
MAX_TITLE     = 120
MAX_NOTES     = 500


# ── Database ──────────────────────────────────────────────────────────────────
def get_db():
    if "db" not in g:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Run once at startup to ensure schema exists."""
    conn = psycopg2.connect(DATABASE_URL)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          SERIAL PRIMARY KEY,
            email       TEXT UNIQUE NOT NULL,
            password    TEXT NOT NULL,
            is_verified BOOLEAN DEFAULT FALSE,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS otps (
            id         SERIAL PRIMARY KEY,
            email      TEXT NOT NULL,
            otp        TEXT NOT NULL,
            purpose    TEXT NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            used       BOOLEAN DEFAULT FALSE
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id          SERIAL PRIMARY KEY,
            user_email  TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
            subject     TEXT NOT NULL,
            title       TEXT NOT NULL,
            type        TEXT NOT NULL,
            deadline    DATE NOT NULL,
            deadline_time TIME,
            hours       SMALLINT DEFAULT 1,
            notes       TEXT DEFAULT '',
            completed   BOOLEAN DEFAULT FALSE,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    # Index for fast per-user task lookups
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_user_email
        ON tasks(user_email)
    """)
    conn.commit()
    conn.close()


try:
    init_db()
except Exception as e:
    print(f"[DB] init_db warning: {e}")


# ── Helpers ───────────────────────────────────────────────────────────────────
def generate_otp():
    return "".join(random.choices(string.digits, k=6))


def save_otp(email: str, otp: str, purpose: str):
    db = get_db()
    c  = db.cursor()
    # Invalidate previous unused OTPs for same email+purpose
    c.execute(
        "UPDATE otps SET used=TRUE WHERE email=%s AND purpose=%s AND used=FALSE",
        (email, purpose)
    )
    expires = datetime.now() + timedelta(minutes=10)
    c.execute(
        "INSERT INTO otps(email,otp,purpose,expires_at,used) VALUES(%s,%s,%s,%s,FALSE)",
        (email, otp, purpose, expires)
    )
    db.commit()


def verify_otp_code(email: str, otp: str, purpose: str) -> bool:
    db  = get_db()
    c   = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    now = datetime.now()
    c.execute(
        """SELECT id FROM otps
           WHERE email=%s AND otp=%s AND purpose=%s
             AND used=FALSE AND expires_at > %s""",
        (email, otp, purpose, now)
    )
    row = c.fetchone()
    if row:
        c.execute("UPDATE otps SET used=TRUE WHERE id=%s", (row["id"],))
        db.commit()
    return row is not None


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            flash("Please sign in to continue.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ── Urgency algorithm ─────────────────────────────────────────────────────────
def compute_urgency(task_row, now: datetime):
    """
    Returns (color, label, sort_key).

    Sort key: lower = more urgent (shown first).

    Algorithm:
      1. Completed tasks always go last.
      2. Overdue = deadline < today → color 'overdue', sort by how many days past.
      3. Due today → 'urgent'
      4. Due within 3 days → 'high'
      5. Due within 7 days → 'medium'
      6. Future → 'safe'

    Within same urgency band, tasks with more estimated hours sort first
    (you should start the heavy ones sooner).
    Exams always sort before Assignments/Labs/Quizzes within the same band.
    """
    if task_row["completed"]:
        return ("done", "Completed", 10000)

    today = now.date()
    dl    = task_row["deadline"]  # already a date object from psycopg2

    # Combine with time if present
    if task_row.get("deadline_time"):
        dl_dt = datetime.combine(dl, task_row["deadline_time"])
    else:
        dl_dt = datetime.combine(dl, datetime.max.time())  # end of day

    minutes_left = (dl_dt - now).total_seconds() / 60

    if minutes_left < 0:
        color = "overdue"
        band  = 0
    elif minutes_left < 24 * 60:        # within 24 hours
        color = "urgent"
        band  = 1
    elif minutes_left < 3 * 24 * 60:   # within 3 days
        color = "high"
        band  = 2
    elif minutes_left < 7 * 24 * 60:   # within 7 days
        color = "medium"
        band  = 3
    else:
        color = "safe"
        band  = 4

    # Type weight: Exam=0, Project=1, Assignment/Lab/Quiz=2
    type_weight = {"Exam": 0, "Project": 1}.get(task_row["type"], 2)

    # Within a band: sort by minutes_left ASC, then type, then hours DESC
    hours = task_row.get("hours") or 1
    sort_key = (band, minutes_left, type_weight, -hours)

    label_map = {
        "overdue": "Overdue",
        "urgent":  "Due today",
        "high":    "Due soon",
        "medium":  "This week",
        "safe":    "Upcoming",
    }
    return (color, label_map[color], sort_key)


def days_left_display(task_row, now: datetime) -> str:
    today = now.date()
    dl    = task_row["deadline"]
    days  = (dl - today).days
    if days < 0:
        return f"{abs(days)}d overdue"
    elif days == 0:
        if task_row.get("deadline_time"):
            t = task_row["deadline_time"]
            return f"Today {t.strftime('%H:%M')}"
        return "Due today"
    elif days == 1:
        return "Tomorrow"
    else:
        return f"{days}d left"


# ── Email ─────────────────────────────────────────────────────────────────────
def send_otp_email(email: str, otp: str, purpose: str) -> bool:
    configs = {
        "register": {
            "subject": "Verify your Academic Deadline Radar account",
            "headline": "One last step — verify your email.",
            "body": "You're almost in. Use the code below to confirm your email address.",
            "note": "If you didn't create this account, you can safely ignore this email.",
        },
        "login": {
            "subject": "Your login code for Academic Deadline Radar",
            "headline": "Here's your sign-in code.",
            "body": "Use the 6-digit code below to complete your sign-in. It expires in 10 minutes.",
            "note": "If you didn't try to sign in, your password may be compromised.",
        },
        "forgot": {
            "subject": "Reset your Academic Deadline Radar password",
            "headline": "Password reset requested.",
            "body": "Use the code below to reset your password. It expires in 10 minutes.",
            "note": "If you didn't request this, ignore this email — your password won't change.",
        },
    }
    cfg = configs.get(purpose, configs["register"])

    # Always print to logs (for dev / fallback)
    print(f"\n{'='*50}\n  OTP [{purpose.upper()}] → {email}: {otp}\n{'='*50}\n")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0F1117;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">
  <tr><td align="center">
    <table width="540" cellpadding="0" cellspacing="0" style="background:#1A1D27;border-radius:16px;overflow:hidden;border:1px solid rgba(255,255,255,0.1);max-width:540px;">
      <tr><td style="padding:32px 40px 24px;">
        <p style="margin:0 0 4px;font-size:18px;font-weight:700;color:#F1F5F9;">🎯 Academic Deadline Radar</p>
        <p style="margin:0 0 24px;font-size:13px;color:#64748B;">Never miss a deadline</p>
        <p style="margin:0 0 8px;font-size:16px;font-weight:600;color:#F1F5F9;">{cfg['headline']}</p>
        <p style="margin:0 0 28px;font-size:14px;color:#94A3B8;line-height:1.6;">{cfg['body']}</p>
        <div style="text-align:center;letter-spacing:12px;font-size:36px;font-weight:800;color:#8B5CF6;margin:0 0 28px;font-family:monospace;">{otp}</div>
        <p style="margin:0;font-size:12px;color:#475569;border-top:1px solid rgba(255,255,255,0.07);padding-top:16px;">{cfg['note']}</p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""

    plain = f"Academic Deadline Radar\n\n{cfg['headline']}\n\n{cfg['body']}\n\nYour code: {otp}\n\n{cfg['note']}"

    if not BREVO_API_KEY:
        return False

    try:
        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
            json={
                "sender":      {"name": "Academic Deadline Radar", "email": MAIL_FROM},
                "to":          [{"email": email}],
                "subject":     cfg["subject"],
                "htmlContent": html,
                "textContent": plain,
            },
            timeout=15,
        )
        if resp.status_code in (200, 201):
            return True
        print(f"[Mail] Brevo error {resp.status_code}: {resp.text}")
    except Exception as exc:
        print(f"[Mail] Exception: {exc}")
    return False


# ── Auth routes ───────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Validate
        if "@" not in email or "." not in email or len(email) > 254:
            flash("Please enter a valid email address.", "error")
            return redirect(url_for("register"))
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return redirect(url_for("register"))

        db = get_db()
        c  = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT id, is_verified FROM users WHERE email=%s", (email,))
        existing = c.fetchone()

        if existing and existing["is_verified"]:
            flash("An account with this email already exists. Please sign in.", "error")
            return redirect(url_for("login"))

        hashed = generate_password_hash(password)
        if not existing:
            c.execute(
                "INSERT INTO users(email,password,is_verified) VALUES(%s,%s,FALSE)",
                (email, hashed)
            )
        else:
            c.execute("UPDATE users SET password=%s WHERE email=%s", (hashed, email))
        db.commit()

        otp  = generate_otp()
        save_otp(email, otp, "register")
        sent = send_otp_email(email, otp, "register")

        session["otp_email"]   = email
        session["otp_purpose"] = "register"

        if sent:
            flash(f"A verification code was sent to {email}.", "success")
        else:
            # Dev fallback: show OTP in info flash only if email failed
            flash(f"Email sending failed. Dev code: {otp}", "info")

        return redirect(url_for("verify_otp"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        c  = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT password, is_verified FROM users WHERE email=%s", (email,))
        user = c.fetchone()

        # Constant-time-ish: always do hash check to prevent timing attacks
        if user:
            pw_ok = check_password_hash(user["password"], password)
        else:
            check_password_hash("dummy", password)  # prevent timing oracle
            pw_ok = False

        if not user or not pw_ok:
            flash("Incorrect email or password.", "error")
            return redirect(url_for("login"))

        if not user["is_verified"]:
            session["otp_email"]   = email
            session["otp_purpose"] = "register"
            flash("Please verify your email to continue.", "info")
            return redirect(url_for("verify_otp"))

        otp  = generate_otp()
        save_otp(email, otp, "login")
        sent = send_otp_email(email, otp, "login")

        session["otp_email"]   = email
        session["otp_purpose"] = "login"

        if sent:
            flash(f"A sign-in code was sent to {email}.", "success")
        else:
            flash(f"Email sending failed. Dev code: {otp}", "info")

        return redirect(url_for("verify_otp"))

    return render_template("login.html")


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    email   = session.get("otp_email")
    purpose = session.get("otp_purpose")
    if not email or not purpose:
        return redirect(url_for("login"))

    if request.method == "POST":
        otp = "".join(
            request.form.get(f"d{i}", "") for i in range(1, 7)
        ).strip()

        if verify_otp_code(email, otp, purpose):
            if purpose == "register":
                db = get_db()
                c  = db.cursor()
                c.execute("UPDATE users SET is_verified=TRUE WHERE email=%s", (email,))
                db.commit()
                session.pop("otp_email",   None)
                session.pop("otp_purpose", None)
                flash("Email verified! Please sign in.", "success")
                return redirect(url_for("login"))

            elif purpose == "login":
                session.clear()           # prevent session fixation
                session["user"] = email
                return redirect(url_for("dashboard"))

            elif purpose == "forgot":
                session["reset_email"] = email
                session.pop("otp_email",   None)
                session.pop("otp_purpose", None)
                return redirect(url_for("reset_password"))
        else:
            flash("Invalid or expired code. Please try again.", "error")
            return redirect(url_for("verify_otp"))

    return render_template("verify_otp.html", email=email, purpose=purpose)


@app.route("/resend-otp")
def resend_otp():
    email   = session.get("otp_email")
    purpose = session.get("otp_purpose")
    if not email or not purpose:
        return redirect(url_for("login"))

    otp  = generate_otp()
    save_otp(email, otp, purpose)
    sent = send_otp_email(email, otp, purpose)

    if sent:
        flash("A new code has been sent to your email.", "success")
    else:
        flash(f"Email sending failed. Dev code: {otp}", "info")
    return redirect(url_for("verify_otp"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        # Always show same message to prevent email enumeration
        db = get_db()
        c  = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT id FROM users WHERE email=%s AND is_verified=TRUE", (email,))
        user = c.fetchone()

        if user:
            otp  = generate_otp()
            save_otp(email, otp, "forgot")
            sent = send_otp_email(email, otp, "forgot")
            session["otp_email"]   = email
            session["otp_purpose"] = "forgot"
            if not sent:
                flash(f"Email sending failed. Dev code: {otp}", "info")

        flash("If that email is registered, a reset code has been sent.", "success")
        return redirect(url_for("verify_otp"))

    return render_template("forgot_password.html")


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    email = session.get("reset_email")
    if not email:
        return redirect(url_for("login"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm", "")

        if password != confirm:
            flash("Passwords do not match.", "error")
            return redirect(url_for("reset_password"))
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return redirect(url_for("reset_password"))

        db = get_db()
        c  = db.cursor()
        c.execute(
            "UPDATE users SET password=%s WHERE email=%s",
            (generate_password_hash(password), email)
        )
        db.commit()
        session.pop("reset_email", None)
        flash("Password updated. Please sign in.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    db  = get_db()
    c   = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    now = datetime.now()

    c.execute(
        """SELECT id, subject, title, type, deadline, deadline_time,
                  hours, notes, completed, created_at
           FROM tasks
           WHERE user_email=%s
           ORDER BY deadline ASC, deadline_time ASC NULLS LAST""",
        (session["user"],)
    )
    rows = c.fetchall()

    # Get distinct subjects for autocomplete
    c.execute(
        "SELECT DISTINCT subject FROM tasks WHERE user_email=%s ORDER BY subject",
        (session["user"],)
    )
    subjects = [r["subject"] for r in c.fetchall()]

    tasks = []
    for r in rows:
        color, urgency_label, sort_key = compute_urgency(r, now)
        dl_display = days_left_display(r, now)
        tasks.append({
            "id":            r["id"],
            "subject":       r["subject"],
            "title":         r["title"],
            "type":          r["type"],
            "deadline":      r["deadline"].strftime("%Y-%m-%d"),
            "deadline_time": r["deadline_time"].strftime("%H:%M") if r["deadline_time"] else None,
            "hours":         r["hours"],
            "notes":         r["notes"] or "",
            "completed":     r["completed"],
            "color":         color,
            "urgency_label": urgency_label,
            "dl_display":    dl_display,
            "_sort":         sort_key,
        })

    tasks.sort(key=lambda x: x["_sort"])

    # Stats
    active    = [t for t in tasks if not t["completed"]]
    completed = [t for t in tasks if t["completed"]]
    overdue   = [t for t in active if t["color"] == "overdue"]
    urgent    = [t for t in active if t["color"] in ("overdue", "urgent")]
    this_week = [t for t in active if t["color"] in ("overdue", "urgent", "high", "medium")]

    return render_template(
        "dashboard.html",
        email=session["user"],
        tasks=tasks,
        active=active,
        completed=completed,
        overdue=overdue,
        urgent=urgent,
        this_week=this_week,
        subjects=subjects,
        task_types=TASK_TYPES,
        now=now,
    )


# ── Task CRUD ─────────────────────────────────────────────────────────────────
@app.route("/add_task", methods=["POST"])
@login_required
def add_task():
    subject  = request.form.get("subject", "").strip()[:MAX_SUBJECT]
    title    = request.form.get("title", "").strip()[:MAX_TITLE]
    type_    = request.form.get("type", "Assignment")
    deadline = request.form.get("deadline", "")
    dl_time  = request.form.get("deadline_time", "").strip() or None
    notes    = request.form.get("notes", "").strip()[:MAX_NOTES]

    try:
        hours = max(1, min(200, int(request.form.get("hours", 1))))
    except (ValueError, TypeError):
        hours = 1

    if not subject or not title:
        flash("Subject and title are required.", "error")
        return redirect(url_for("dashboard"))

    if type_ not in TASK_TYPES:
        flash("Invalid task type.", "error")
        return redirect(url_for("dashboard"))

    try:
        dl_date = datetime.strptime(deadline, "%Y-%m-%d").date()
    except ValueError:
        flash("Please enter a valid deadline date.", "error")
        return redirect(url_for("dashboard"))

    # Parse time if provided
    parsed_time = None
    if dl_time:
        try:
            parsed_time = datetime.strptime(dl_time, "%H:%M").time()
        except ValueError:
            pass  # ignore invalid time, use date-only

    db = get_db()
    c  = db.cursor()
    c.execute(
        """INSERT INTO tasks(user_email,subject,title,type,deadline,deadline_time,hours,notes,completed)
           VALUES(%s,%s,%s,%s,%s,%s,%s,%s,FALSE)""",
        (session["user"], subject, title, type_, dl_date, parsed_time, hours, notes)
    )
    db.commit()
    flash(f'"{title}" added successfully.', "success")
    return redirect(url_for("dashboard"))


@app.route("/complete_task/<int:task_id>", methods=["POST"])
@login_required
def complete_task(task_id):
    db = get_db()
    c  = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # Verify ownership
    c.execute("SELECT id, completed FROM tasks WHERE id=%s AND user_email=%s", (task_id, session["user"]))
    task = c.fetchone()
    if not task:
        abort(404)
    new_state = not task["completed"]
    c.execute("UPDATE tasks SET completed=%s WHERE id=%s", (new_state, task_id))
    db.commit()
    return redirect(url_for("dashboard"))


@app.route("/edit_task/<int:task_id>", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    db = get_db()
    c  = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM tasks WHERE id=%s AND user_email=%s", (task_id, session["user"]))
    task = c.fetchone()

    if not task:
        flash("Task not found.", "error")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        subject  = request.form.get("subject", "").strip()[:MAX_SUBJECT]
        title    = request.form.get("title", "").strip()[:MAX_TITLE]
        type_    = request.form.get("type", "Assignment")
        deadline = request.form.get("deadline", "")
        dl_time  = request.form.get("deadline_time", "").strip() or None
        notes    = request.form.get("notes", "").strip()[:MAX_NOTES]

        try:
            hours = max(1, min(200, int(request.form.get("hours", 1))))
        except (ValueError, TypeError):
            hours = 1

        if not subject or not title:
            flash("Subject and title are required.", "error")
            return redirect(url_for("edit_task", task_id=task_id))

        if type_ not in TASK_TYPES:
            flash("Invalid task type.", "error")
            return redirect(url_for("edit_task", task_id=task_id))

        try:
            dl_date = datetime.strptime(deadline, "%Y-%m-%d").date()
        except ValueError:
            flash("Please enter a valid deadline date.", "error")
            return redirect(url_for("edit_task", task_id=task_id))

        parsed_time = None
        if dl_time:
            try:
                parsed_time = datetime.strptime(dl_time, "%H:%M").time()
            except ValueError:
                pass

        c.execute(
            """UPDATE tasks
               SET subject=%s, title=%s, type=%s, deadline=%s,
                   deadline_time=%s, hours=%s, notes=%s
               WHERE id=%s AND user_email=%s""",
            (subject, title, type_, dl_date, parsed_time, hours, notes, task_id, session["user"])
        )
        db.commit()
        flash("Task updated.", "success")
        return redirect(url_for("dashboard"))

    # Format for template
    task_data = dict(task)
    task_data["deadline"]      = task["deadline"].strftime("%Y-%m-%d")
    task_data["deadline_time"] = task["deadline_time"].strftime("%H:%M") if task["deadline_time"] else ""
    return render_template("edit_task.html", task=task_data, task_types=TASK_TYPES)


@app.route("/delete_task/<int:task_id>", methods=["POST"])
@login_required
def delete_task(task_id):
    db = get_db()
    c  = db.cursor()
    c.execute("DELETE FROM tasks WHERE id=%s AND user_email=%s", (task_id, session["user"]))
    if c.rowcount == 0:
        abort(404)
    db.commit()
    flash("Task deleted.", "success")
    return redirect(url_for("dashboard"))


# ── Error handlers ─────────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found."), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="Access denied."), 403


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500, message="Something went wrong. Please try again."), 500


if __name__ == "__main__":
    app.run(debug=False)


# ── Email Reminders ───────────────────────────────────────────────────────────
def send_reminder_email(email: str, task: dict, days_left: int) -> bool:
    """Send a deadline reminder email for a task."""
    if days_left < 0:
        when = f"{abs(days_left)} day{'s' if abs(days_left) != 1 else ''} overdue"
        urgency = "OVERDUE"
        color = "#EF4444"
    elif days_left == 0:
        when = "due TODAY"
        urgency = "DUE TODAY"
        color = "#F97316"
    elif days_left == 1:
        when = "due TOMORROW"
        urgency = "DUE TOMORROW"
        color = "#EAB308"
    else:
        when = f"due in {days_left} days"
        urgency = f"DUE IN {days_left} DAYS"
        color = "#3B82F6"

    subject = f"⏰ {urgency}: {task['title']} — Academic Deadline Radar"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0D1117;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">
  <tr><td align="center">
    <table width="540" cellpadding="0" cellspacing="0"
           style="background:#161B22;border-radius:16px;overflow:hidden;
                  border:1px solid rgba(255,255,255,0.1);max-width:540px;">
      <tr><td style="height:4px;background:{color};font-size:0;">&nbsp;</td></tr>
      <tr><td style="padding:28px 36px 24px;">
        <p style="margin:0 0 4px;font-size:18px;font-weight:700;color:#E6EDF3;">🎯 Academic Deadline Radar</p>
        <p style="margin:0 0 24px;font-size:12px;color:#484F58;">Deadline reminder</p>

        <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);
                    border-radius:12px;padding:20px 24px;margin-bottom:24px;">
          <p style="margin:0 0 6px;font-size:11px;font-weight:700;
                    text-transform:uppercase;letter-spacing:1px;color:{color};">{urgency}</p>
          <p style="margin:0 0 4px;font-size:20px;font-weight:800;color:#E6EDF3;">{task['title']}</p>
          <p style="margin:0;font-size:14px;color:#8B949E;">{task['subject']} · {task['type']}</p>
        </div>

        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
          <tr>
            <td style="padding:10px 14px;background:rgba(255,255,255,0.03);
                       border-radius:8px 0 0 8px;border:1px solid rgba(255,255,255,0.07);
                       font-size:12px;color:#8B949E;">📅 Deadline</td>
            <td style="padding:10px 14px;background:rgba(255,255,255,0.03);
                       border-radius:0 8px 8px 0;border:1px solid rgba(255,255,255,0.07);
                       border-left:none;font-size:14px;font-weight:600;color:#E6EDF3;">
              {task['deadline']}{' at ' + task['deadline_time'] if task.get('deadline_time') else ''}
            </td>
          </tr>
          <tr><td colspan="2" style="height:6px;"></td></tr>
          <tr>
            <td style="padding:10px 14px;background:rgba(255,255,255,0.03);
                       border-radius:8px 0 0 8px;border:1px solid rgba(255,255,255,0.07);
                       font-size:12px;color:#8B949E;">⏱ Est. hours</td>
            <td style="padding:10px 14px;background:rgba(255,255,255,0.03);
                       border-radius:0 8px 8px 0;border:1px solid rgba(255,255,255,0.07);
                       border-left:none;font-size:14px;font-weight:600;color:#E6EDF3;">
              {task['hours']} hour{'s' if task['hours'] != 1 else ''}
            </td>
          </tr>
          {f'''<tr><td colspan="2" style="height:6px;"></td></tr>
          <tr>
            <td style="padding:10px 14px;background:rgba(255,255,255,0.03);
                       border-radius:8px 0 0 8px;border:1px solid rgba(255,255,255,0.07);
                       font-size:12px;color:#8B949E;">📝 Notes</td>
            <td style="padding:10px 14px;background:rgba(255,255,255,0.03);
                       border-radius:0 8px 8px 0;border:1px solid rgba(255,255,255,0.07);
                       border-left:none;font-size:13px;color:#E6EDF3;">{task["notes"]}</td>
          </tr>''' if task.get('notes') else ''}
        </table>

        <p style="margin:0 0 20px;font-size:14px;color:#8B949E;line-height:1.6;">
          This task is <strong style="color:{color};">{when}</strong>.
          {'Get started now!' if days_left > 1 else 'Make sure you submit on time!'}
        </p>

        <p style="margin:0;font-size:11px;color:#484F58;border-top:1px solid rgba(255,255,255,0.07);
                  padding-top:16px;">
          You received this because you have an account on Academic Deadline Radar.<br>
          This is an automated reminder — please do not reply.
        </p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""

    plain = (
        f"Academic Deadline Radar — Reminder\n\n"
        f"{urgency}: {task['title']}\n"
        f"Subject: {task['subject']} | Type: {task['type']}\n"
        f"Deadline: {task['deadline']}"
        f"{' at ' + task['deadline_time'] if task.get('deadline_time') else ''}\n"
        f"Estimated: {task['hours']} hours\n\n"
        f"This task is {when}.\n\n"
        f"— Academic Deadline Radar"
    )

    print(f"[Reminder] Sending to {email}: {task['title']} ({when})")

    if not BREVO_API_KEY:
        return False

    try:
        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
            json={
                "sender":      {"name": "Academic Deadline Radar", "email": MAIL_FROM},
                "to":          [{"email": email}],
                "subject":     subject,
                "htmlContent": html,
                "textContent": plain,
            },
            timeout=15,
        )
        if resp.status_code in (200, 201):
            print(f"[Reminder] Sent successfully to {email}")
            return True
        print(f"[Reminder] Brevo error {resp.status_code}: {resp.text}")
    except Exception as exc:
        print(f"[Reminder] Exception: {exc}")
    return False


@app.route("/send-reminders")
def send_reminders():
    """
    Call this route via a cron job or scheduler to send deadline reminders.
    Sends reminders for tasks due in 7 days, 3 days, 1 day, today, and overdue.
    Protected by a secret token to prevent abuse.
    """
    token = request.args.get("token", "")
    expected = os.environ.get("REMINDER_TOKEN", "")
    if not expected or token != expected:
        abort(403)

    db  = get_db()
    c   = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    now = datetime.now()
    today = now.date()

    # Get all incomplete tasks with deadlines today or in future or overdue
    c.execute("""
        SELECT t.id, t.user_email, t.subject, t.title, t.type,
               t.deadline, t.deadline_time, t.hours, t.notes
        FROM tasks t
        WHERE t.completed = FALSE
        ORDER BY t.deadline ASC
    """)
    tasks = c.fetchall()

    sent_count = 0
    reminder_days = {0, 1, 3, 7}  # Send reminders on these days_left values

    for task in tasks:
        dl    = task["deadline"]
        days_left = (dl - today).days

        # Only send for overdue (up to 3 days past) or upcoming reminder days
        if days_left in reminder_days or (-3 <= days_left < 0):
            task_dict = {
                "title":         task["title"],
                "subject":       task["subject"],
                "type":          task["type"],
                "deadline":      dl.strftime("%Y-%m-%d"),
                "deadline_time": task["deadline_time"].strftime("%H:%M") if task["deadline_time"] else None,
                "hours":         task["hours"],
                "notes":         task["notes"] or "",
            }
            sent = send_reminder_email(task["user_email"], task_dict, days_left)
            if sent:
                sent_count += 1

    return {"status": "ok", "reminders_sent": sent_count}, 200
