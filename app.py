from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "deadline_radar_secret"


# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()

    c.execute('''
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS tasks(
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
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()

        try:
            c.execute("INSERT INTO users(username,password) VALUES(?,?)",(username,password))
            conn.commit()
            conn.close()
            return redirect('/login')
        except:
            conn.close()
            return render_template("register.html", error="Username already exists")

    return render_template("register.html")


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
            return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")


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
    hours = request.form['hours']

    if int(hours) < 0:
        hours = 0

    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()

    c.execute("INSERT INTO tasks(user,subject,title,task_type,deadline,hours) VALUES(?,?,?,?,?,?)",
              (session['user'],subject,title,task_type,deadline,hours))

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
    processed = []

    for t in tasks:
        deadline = datetime.strptime(t[5], "%Y-%m-%d")
        days_left = (deadline - today).days

        if days_left < 0:
            color = "overdue"
        elif days_left <= 1:
            color = "urgent"
        elif days_left <= 3:
            color = "warning"
        else:
            color = "safe"

        processed.append((t, days_left, color))

    conn.close()

    return render_template("index.html", tasks=processed, username=session['user'])


if __name__ == "__main__":
    app.run(debug=True)
