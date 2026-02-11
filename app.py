from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "hackathon_secret_key_123"


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
        user TEXT,
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
@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()

        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            conn.close()
            return redirect('/login')
        except:
            error = "Username already exists!"
            conn.close()

    return render_template('register.html', error=error)


# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()

        if user:
            session['user'] = username
            return redirect('/')
        else:
            error = "Invalid username or password"

    return render_template('login.html', error=error)


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')


# ---------------- ADD TASK ----------------
@app.route('/add', methods=['POST'])
def add():
    if 'user' not in session:
        return redirect('/login')

    subject = request.form['subject']
    title = request.form['title']
    task_type = request.form['task_type']
    deadline = request.form['deadline']
    hours = int(request.form['hours'])

    if hours <= 0:
        return redirect('/')

    
    if not subject or not title or not deadline or not hours:
        return redirect('/')

    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()

    c.execute(
        "INSERT INTO tasks (user, subject, title, task_type, deadline, hours) VALUES (?, ?, ?, ?, ?, ?)",
        (session['user'], subject, title, task_type, deadline, hours)
    )

    conn.commit()
    conn.close()

    return redirect('/')


# ---------------- HOME ----------------
@app.route('/')
def home():
    if 'user' not in session:
        return redirect('/login')

    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()

    c.execute("SELECT * FROM tasks WHERE user=?", (session['user'],))
    tasks_db = c.fetchall()
    tasks = []

    today = datetime.today()

    for task in tasks_db:
        deadline = datetime.strptime(task[5], "%Y-%m-%d")
        days_left = (deadline - today).days

        if days_left < 0:
            color = "urgent"      # overdue → RED
        elif days_left <= 2:
            color = "danger"      # 1-2 days → ORANGE
        elif days_left <= 5:
            color = "warning"     # few days → YELLOW
        else:
            color = "safe"        # safe → GREEN

        tasks.append(task + (days_left, color))


    # -------- Recommendation --------
    recommended = None
    today = datetime.today()
    best_score = 999999

    for task in tasks:
        deadline = datetime.strptime(task[5], "%Y-%m-%d")
        days_left = (deadline - today).days
        hours = int(task[6])

        if days_left < 0:
            score = -100
        else:
            score = (days_left * 2) + hours

        if score < best_score:
            best_score = score
            recommended = task

    # -------- Workload Meter --------
    today_hours = 0
    for task in tasks:
        deadline = datetime.strptime(task[5], "%Y-%m-%d")
        days_left = (deadline - today).days
        hours = int(task[6])

        if days_left <= 2:
            today_hours += hours

    if today_hours == 0:
        workload = "Free Day 😌"
    elif today_hours <= 3:
        workload = "Light Work 📗"
    elif today_hours <= 6:
        workload = "Busy Day 📙"
    else:
        workload = "Overloaded 🚨"

    conn.close()

    return render_template(
        'index.html',
        tasks=tasks,
        recommended=recommended,
        username=session['user'],
        workload=workload,
        today_hours=today_hours
    )


if __name__ == '__main__':
    app.run(debug=True)
