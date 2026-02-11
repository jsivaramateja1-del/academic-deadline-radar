from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "academic-deadline-radar-secret"


# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()

    # USERS TABLE
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    ''')

    # TASKS TABLE
    c.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        subject TEXT,
        title TEXT,
        task_type TEXT,
        deadline TEXT,
        hours INTEGER
    )
    ''')

    conn.commit()
    conn.close()

init_db()


# ---------------- REGISTER ----------------
@app.route('/register')
def register_page():
    return render_template('register.html')


@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']

    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()

    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
    except:
        conn.close()
        return "Username already exists. Go back and try another."

    conn.close()
    return redirect('/login')


# ---------------- LOGIN ----------------
@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = c.fetchone()
    conn.close()

    if user:
        session['user_id'] = user[0]
        session['username'] = user[1]
        return redirect('/')
    else:
        return "Invalid username or password"


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ---------------- ADD TASK ----------------
@app.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session:
        return redirect('/login')

    subject = request.form['subject']
    title = request.form['title']
    task_type = request.form['task_type']
    deadline = request.form['deadline']
    hours = request.form['hours']

    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()

    c.execute("""
    INSERT INTO tasks (user_id, subject, title, task_type, deadline, hours)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (session['user_id'], subject, title, task_type, deadline, hours))

    conn.commit()
    conn.close()

    return redirect('/')


# ---------------- HOME + RECOMMENDATION ----------------
@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()

    # ONLY CURRENT USER TASKS
    c.execute("SELECT * FROM tasks WHERE user_id=?", (session['user_id'],))
    tasks = c.fetchall()

    # RECOMMENDATION SYSTEM
    recommended = None
    today = datetime.today()
    best_score = 999999

    for task in tasks:
        deadline = datetime.strptime(task[5], "%Y-%m-%d")
        days_left = (deadline - today).days
        hours = int(task[6])

        # priority formula
        score = (days_left * 2) + hours

        if score < best_score:
            best_score = score
            recommended = task

    conn.close()

    return render_template('index.html',
                           tasks=tasks,
                           recommended=recommended,
                           username=session['username'])


# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)
