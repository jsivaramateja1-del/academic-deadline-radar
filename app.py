from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
from datetime import datetime
import random

app = Flask(__name__)
app.secret_key = "academic_deadline_secret"

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()

    # users
    c.execute('''
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    ''')

    # tasks
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

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET','POST'])
def login():

    if request.method == 'POST':

        # ask captcha first
        if 'captcha_verified' not in session:
            a = random.randint(1,9)
            b = random.randint(1,9)
            session['captcha_answer'] = a + b
            session['pending_login'] = request.form
            return render_template("captcha.html",
                                   question=f"{a} + {b}",
                                   next="login")

        # real login
        username = session['pending_login']['username']
        password = session['pending_login']['password']

        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?",(username,password))
        user = c.fetchone()
        conn.close()

        session.pop('captcha_verified',None)
        session.pop('pending_login',None)

        if user:
            session['user']=username
            return redirect('/')
        else:
            flash("Invalid username or password")
            return redirect('/login')

    return render_template('login.html')


# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET','POST'])
def register():

    if request.method == 'POST':

        if 'captcha_verified' not in session:
            a=random.randint(1,9)
            b=random.randint(1,9)
            session['captcha_answer']=a+b
            session['pending_register']=request.form
            return render_template("captcha.html",
                                   question=f"{a} + {b}",
                                   next="register")

        username=session['pending_register']['username']
        password=session['pending_register']['password']

        if len(username)<4:
            flash("Username must be minimum 4 characters")
            return redirect('/register')

        if len(password)<6:
            flash("Password must be minimum 6 characters")
            return redirect('/register')

        conn=sqlite3.connect('tasks.db')
        c=conn.cursor()

        try:
            c.execute("INSERT INTO users (username,password) VALUES (?,?)",(username,password))
            conn.commit()
        except:
            flash("Username already exists")
            return redirect('/register')

        conn.close()

        session.pop('captcha_verified',None)
        session.pop('pending_register',None)

        flash("Account created. Please login.")
        return redirect('/login')

    return render_template('register.html')


# ---------------- CAPTCHA VERIFY ----------------
@app.route('/verify_captcha', methods=['POST'])
def verify_captcha():
    if int(request.form['captcha'])==session.get('captcha_answer'):
        session['captcha_verified']=True
    else:
        flash("Wrong answer!")
        return redirect(request.referrer)

    if request.form['next']=="login":
        return redirect('/login')
    else:
        return redirect('/register')


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

    subject=request.form['subject']
    title=request.form['title']
    task_type=request.form['task_type']
    deadline=request.form['deadline']
    hours=int(request.form['hours'])

    if hours<0:
        flash("Hours cannot be negative")
        return redirect('/')

    conn=sqlite3.connect('tasks.db')
    c=conn.cursor()
    c.execute("INSERT INTO tasks (user,subject,title,task_type,deadline,hours) VALUES (?,?,?,?,?,?)",
              (session['user'],subject,title,task_type,deadline,hours))
    conn.commit()
    conn.close()

    return redirect('/')


# ---------------- DASHBOARD ----------------
@app.route('/')
def home():
    if 'user' not in session:
        return redirect('/login')

    conn=sqlite3.connect('tasks.db')
    c=conn.cursor()
    c.execute("SELECT * FROM tasks WHERE user=?",(session['user'],))
    tasks=c.fetchall()
    conn.close()

    today=datetime.today()
    task_data=[]

    for task in tasks:
        deadline=datetime.strptime(task[5],"%Y-%m-%d")
        days_left=(deadline-today).days

        # urgency color
        if days_left<0:
            color="red"
        elif days_left<=1:
            color="red"
        elif days_left<=3:
            color="orange"
        elif days_left<=7:
            color="yellow"
        else:
            color="green"

        task_data.append((task,days_left,color))

    return render_template("index.html",
                           tasks=task_data,
                           username=session['user'])


if __name__=='__main__':
    app.run(debug=True)
