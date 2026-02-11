from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
from datetime import datetime
import random

app = Flask(__name__)
app.secret_key = "adr_super_secure_key_2026"


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


# ---------------- CAPTCHA GENERATOR ----------------
def generate_captcha():
    a = random.randint(1,9)
    b = random.randint(1,9)
    session['captcha_answer'] = a + b
    return f"{a} + {b}"


# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET','POST'])
def register():

    if request.method == 'POST':

        # Step 2: captcha verification
        if 'captcha_answer' in session and 'pending_user' in session:

            user_answer = request.form.get('captcha')

            if user_answer and int(user_answer) == session['captcha_answer']:
                username = session['pending_user']['username']
                password = session['pending_user']['password']

                conn = sqlite3.connect('tasks.db')
                c = conn.cursor()
                try:
                    c.execute("INSERT INTO users (username,password) VALUES (?,?)",(username,password))
                    conn.commit()
                except:
                    flash("Username already exists")
                    conn.close()
                    return redirect('/register')

                conn.close()
                session.pop('pending_user')
                session.pop('captcha_answer')
                flash("Account created! Please login.")
                return redirect('/login')
            else:
                flash("Incorrect human verification.")
                return redirect('/register')

        # Step 1: normal register submit
        username = request.form['username']
        password = request.form['password']

        if len(username) < 4:
            flash("Username must be at least 4 characters.")
            return redirect('/register')

        if len(password) < 6:
            flash("Password must be at least 6 characters.")
            return redirect('/register')

        session['pending_user'] = {
            'username': username,
            'password': password
        }

        session['captcha_question'] = generate_captcha()
        return render_template('captcha.html', mode="register", question=session['captcha_question'])

    return render_template('register.html')


# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET','POST'])
def login():

    if request.method == 'POST':

        # captcha verification
        if 'captcha_answer' in session and 'pending_login' in session:

            user_answer = request.form.get('captcha')

            if user_answer and int(user_answer) == session['captcha_answer']:

                username = session['pending_login']['username']
                password = session['pending_login']['password']

                conn = sqlite3.connect('tasks.db')
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE username=? AND password=?",(username,password))
                user = c.fetchone()
                conn.close()

                session.pop('pending_login')
                session.pop('captcha_answer')

                if user:
                    session['user'] = username
                    return redirect('/')
                else:
                    flash("Invalid username or password.")
                    return redirect('/login')

            else:
                flash("Incorrect human verification.")
                return redirect('/login')

        # first submit
        username = request.form['username']
        password = request.form['password']

        session['pending_login'] = {
            'username': username,
            'password': password
        }

        session['captcha_question'] = generate_captcha()
        return render_template('captcha.html', mode="login", question=session['captcha_question'])

    return render_template('login.html')


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
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
        flash("Hours cannot be negative.")
        return redirect('/')

    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("INSERT INTO tasks VALUES (NULL,?,?,?,?,?,?)",
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
    conn.close()

    today = datetime.today()
    colored_tasks = []

    for t in tasks:
        deadline = datetime.strptime(t[5], "%Y-%m-%d")
        days = (deadline - today).days

        if days < 0:
            color = "overdue"
        elif days <= 1:
            color = "red"
        elif days <= 3:
            color = "orange"
        elif days <= 7:
            color = "yellow"
        else:
            color = "green"

        colored_tasks.append((t,color,days))

    return render_template('index.html', tasks=colored_tasks, username=session['user'])


if __name__ == '__main__':
    app.run(debug=True)
