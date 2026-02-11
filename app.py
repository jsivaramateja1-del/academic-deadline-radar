from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import random
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "super_secret_key_123"

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        subject TEXT,
        title TEXT,
        type TEXT,
        deadline TEXT,
        hours INTEGER
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- CAPTCHA GENERATOR ----------------
def generate_captcha():
    a = random.randint(1,9)
    b = random.randint(1,9)
    session['captcha'] = str(a + b)
    return a, b

# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET','POST'])
def register():

    if request.method == 'POST':

        username = request.form.get('username','').strip()
        password = request.form.get('password','').strip()
        answer = request.form.get('answer','').strip()

        # captcha check
        if 'captcha' not in session:
            flash("Verification expired. Try again.")
            return redirect(url_for('register'))

        if answer != session['captcha']:
            flash("Wrong verification answer.")
            return redirect(url_for('register'))

        # validation
        if len(username) < 4:
            flash("Username must be at least 4 characters.")
            return redirect(url_for('register'))

        if len(password) < 6:
            flash("Password must be at least 6 characters.")
            return redirect(url_for('register'))

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()

        cur.execute("SELECT username FROM users WHERE username = ?", (username,))
        existing = cur.fetchone()

        if existing:
            conn.close()
            flash("Username already exists")
            return redirect(url_for('register'))

        hashed = generate_password_hash(password)

        cur.execute("INSERT INTO users (username,password) VALUES (?,?)",(username,hashed))
        conn.commit()
        conn.close()

        session.pop('captcha', None)

        flash("Account created successfully! Please login.")
        return redirect(url_for('login'))

    a,b = generate_captcha()
    return render_template("register.html", num1=a, num2=b)


# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET','POST'])
def login():

    if request.method == 'POST':

        username = request.form.get('username','').strip()
        password = request.form.get('password','').strip()
        answer = request.form.get('answer','').strip()

        if 'captcha' not in session:
            flash("Verification expired.")
            return redirect(url_for('login'))

        if answer != session['captcha']:
            flash("Wrong verification answer.")
            return redirect(url_for('login'))

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()

        cur.execute("SELECT * FROM users WHERE username = ?",(username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session.pop('captcha', None)
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password.")
            return redirect(url_for('login'))

    a,b = generate_captcha()
    return render_template("login.html", num1=a, num2=b)


# ---------------- DASHBOARD ----------------
@app.route('/')
@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("SELECT * FROM tasks WHERE user_id=?",(session['user_id'],))
    tasks = cur.fetchall()
    conn.close()

    return render_template("dashboard.html", tasks=tasks, username=session['username'])


# ---------------- ADD TASK ----------------
@app.route('/add_task', methods=['POST'])
def add_task():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    subject = request.form.get('subject')
    title = request.form.get('title')
    task_type = request.form.get('type')
    deadline = request.form.get('deadline')
    hours = request.form.get('hours')

    try:
        hours = int(hours)
        if hours < 0:
            hours = 0
    except:
        hours = 0

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO tasks (user_id,subject,title,type,deadline,hours)
    VALUES (?,?,?,?,?,?)
    """,(session['user_id'],subject,title,task_type,deadline,hours))

    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
