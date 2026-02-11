from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
from datetime import datetime
import random

app = Flask(__name__)
app.secret_key = "academic_deadline_secret_2026"


# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()

    # USERS
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    ''')

    # TASKS
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


# ---------------- CAPTCHA ----------------
def generate_captcha():
    a = random.randint(1,9)
    b = random.randint(1,9)
    session['captcha'] = a + b
    return f"{a} + {b}"


# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    captcha_question = generate_captcha()

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        captcha = request.form['captcha']

        # RULES
        if len(username) < 4:
            flash("Username must be at least 4 characters")
            return redirect('/register')

        if len(password) < 6:
            flash("Password must be at least 6 characters")
            return redirect('/register')

        if not password.isalnum():
            flash("Password must contain only letters and numbers")
            return redirect('/register')

        if int(captcha) != session.get('captcha'):
            flash("Bot verification failed")
            return redirect('/register')

        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()

        try:
            c.execute("INSERT INTO users (username, password) VALUES (?,?)",(username,password))
            conn.commit()
        except:
            flash("Username already exists")
            conn.close()
            return redirect('/register')

        conn.close()
        flash("Account created! Please login.")
        return redirect('/login')

    return render_template('register.html', captcha=captcha_question)


# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?",(username,password))
        user = c.fetchone()
        conn.close()

        if user:
            session['user'] = username
            return redirect('/')
        else:
            flash("Invalid username or password")
            return redirect('/login')

    return render_template('login.html')


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.pop('user',None)
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
    hours = request.form['hours']

    # VALIDATION
    if not subject or not title or not deadline or not hours:
        flash("Fill all fields")
        return redirect('/')

    hours = int(hours)
    if hours < 0:
        flash("Hours cannot be negative")
        return redirect('/')

    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()

    c.execute(
        "INSERT INTO tasks (user,subject,title,task_type,deadline,hours) VALUES (?,?,?,?,?,?)",
        (session['user'],subject,title,task_type,deadline,hours)
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
    c.execute("SELECT * FROM tasks WHERE user=?",(session['user'],))
    tasks = c.fetchall()

    today = datetime.today()
    processed_tasks = []

    for task in tasks:
        deadline = datetime.strptime(task[5], "%Y-%m-%d")
        days_left = (deadline - today).days

        # COLOR PRIORITY
        if days_left < 0:
            color = "red"
        elif days_left <= 1:
            color = "orange"
        elif days_left <= 3:
            color = "yellow"
        else:
            color = "green"

        processed_tasks.append((task,days_left,color))

    conn.close()

    return render_template('index.html',
                           tasks=processed_tasks,
                           username=session['user'])


if __name__ == '__main__':
    app.run(debug=True)
