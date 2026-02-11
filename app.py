from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
import random
from datetime import datetime

app = Flask(__name__)
app.secret_key = "hackathon_secret_key_123"

# ---------------- DATABASE ----------------

def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
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

# ---------------- BOT QUESTION ----------------

def generate_question():
    a = random.randint(1,9)
    b = random.randint(1,9)
    session['captcha_answer'] = str(a+b)
    session['captcha_question'] = f"{a} + {b}"

# ---------------- REGISTER ----------------

@app.route('/register', methods=['GET','POST'])
def register():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']
        answer = request.form['answer']

        if answer != session.get('captcha_answer'):
            flash("Wrong verification answer")
            generate_question()
            return redirect('/register')

        if len(username) < 4:
            flash("Username must be at least 4 characters")
            generate_question()
            return redirect('/register')

        if len(password) < 6:
            flash("Password must be at least 6 characters")
            generate_question()
            return redirect('/register')

        try:
            conn = sqlite3.connect("database.db")
            c = conn.cursor()
            c.execute("INSERT INTO users(username,password) VALUES (?,?)",(username,password))
            conn.commit()
            conn.close()
            flash("Account created! Please login.")
            return redirect('/login')

        except:
            flash("Username already exists")
            generate_question()
            return redirect('/register')

    generate_question()
    return render_template("register.html", question=session.get('captcha_question'))

# ---------------- LOGIN ----------------

@app.route('/', methods=['GET','POST'])
@app.route('/login', methods=['GET','POST'])
def login():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']
        answer = request.form['answer']

        if answer != session.get('captcha_answer'):
            flash("Wrong verification answer")
            generate_question()
            return redirect('/login')

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE username=? AND password=?",(username,password))
        user = c.fetchone()
        conn.close()

        if user:
            session['user'] = username
            return redirect('/dashboard')
        else:
            flash("Invalid username or password")
            generate_question()
            return redirect('/login')

    generate_question()
    return render_template("login.html", question=session.get('captcha_question'))

# ---------------- DASHBOARD ----------------

@app.route('/dashboard')
def dashboard():

    if 'user' not in session:
        return redirect('/login')

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM tasks WHERE username=?",(session['user'],))
    rows = c.fetchall()

    tasks = []
    today = datetime.now().date()

    for r in rows:
        deadline_date = datetime.strptime(r["deadline"], "%Y-%m-%d").date()
        days_left = (deadline_date - today).days

        if days_left < 0:
            color = "red"
        elif days_left <= 1:
            color = "red"
        elif days_left <= 3:
            color = "orange"
        elif days_left <= 7:
            color = "yellow"
        else:
            color = "green"

        tasks.append({
            "subject": r["subject"],
            "title": r["title"],
            "type": r["type"],
            "deadline": r["deadline"],
            "hours": r["hours"],
            "days_left": days_left,
            "color": color
        })

    conn.close()

    return render_template("dashboard.html",username=session['user'],tasks=tasks)

# ---------------- ADD TASK ----------------

@app.route('/add_task', methods=['POST'])
def add_task():

    if 'user' not in session:
        return redirect('/login')

    subject = request.form['subject']
    title = request.form['title']
    type_ = request.form['type']
    deadline = request.form['deadline']
    hours = request.form['hours']

    if int(hours) < 0:
        hours = 0

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
    INSERT INTO tasks(username,subject,title,type,deadline,hours)
    VALUES (?,?,?,?,?,?)
    """,(session['user'],subject,title,type_,deadline,hours))

    conn.commit()
    conn.close()

    return redirect('/dashboard')

# ---------------- LOGOUT ----------------

@app.route('/logout')
def logout():
    session.pop('user',None)
    return redirect('/login')

if __name__ == '__main__':
    app.run(debug=True)
