from flask import Flask, render_template, request, redirect, session, flash, jsonify
import sqlite3
from datetime import datetime
import random

app = Flask(__name__)
app.secret_key = "adr_2026_secret_key"


# ---------------- DATABASE ----------------
def get_db():
    return sqlite3.connect("tasks.db")


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        subject TEXT,
        title TEXT,
        task_type TEXT,
        deadline TEXT,
        hours INTEGER
    )
    """)

    conn.commit()
    conn.close()

init_db()


# ---------------- CAPTCHA ----------------
@app.route("/captcha_question")
def captcha_question():
    a = random.randint(1,9)
    b = random.randint(1,9)
    session["captcha_answer"] = a+b
    return jsonify({"q":f"{a} + {b}"})


# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        username=request.form["username"]
        password=request.form["password"]
        captcha=request.form["captcha"]

        if str(session.get("captcha_answer"))!=captcha:
            flash("Wrong verification answer")
            return redirect("/register")

        if len(username)<4:
            flash("Username must be 4+ characters")
            return redirect("/register")

        if len(password)<6:
            flash("Password must be at least 6 characters")
            return redirect("/register")

        try:
            conn=get_db()
            c=conn.cursor()
            c.execute("INSERT INTO users(username,password) VALUES(?,?)",(username,password))
            conn.commit()
            conn.close()
            flash("Account created! Login now.")
            return redirect("/login")
        except:
            flash("Username already exists")
            return redirect("/register")

    return render_template("register.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        username=request.form["username"]
        password=request.form["password"]
        captcha=request.form["captcha"]

        if str(session.get("captcha_answer"))!=captcha:
            flash("Wrong verification answer")
            return redirect("/login")

        conn=get_db()
        c=conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?",(username,password))
        user=c.fetchone()
        conn.close()

        if user:
            session["user"]=username
            return redirect("/")
        else:
            flash("Invalid username or password")
            return redirect("/login")

    return render_template("login.html")


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------------- ADD TASK ----------------
@app.route("/add", methods=["POST"])
def add():
    if "user" not in session:
        return redirect("/login")

    subject=request.form["subject"]
    title=request.form["title"]
    task_type=request.form["task_type"]
    deadline=request.form["deadline"]
    hours=int(request.form["hours"])

    if hours<0:
        flash("Hours cannot be negative")
        return redirect("/")

    conn=get_db()
    c=conn.cursor()
    c.execute("INSERT INTO tasks(user,subject,title,task_type,deadline,hours) VALUES(?,?,?,?,?,?)",
              (session["user"],subject,title,task_type,deadline,hours))
    conn.commit()
    conn.close()

    return redirect("/")


# ---------------- DASHBOARD ----------------
@app.route("/")
def home():
    if "user" not in session:
        return redirect("/login")

    conn=get_db()
    c=conn.cursor()
    c.execute("SELECT * FROM tasks WHERE user=?",(session["user"],))
    tasks=c.fetchall()
    conn.close()

    today=datetime.today()
    final=[]

    for t in tasks:
        deadline=datetime.strptime(t[5],"%Y-%m-%d")
        days=(deadline-today).days

        if days<=0:
            color="red"
        elif days<=2:
            color="orange"
        elif days<=5:
            color="yellow"
        else:
            color="green"

        final.append((t,days,color))

    return render_template("index.html",tasks=final,username=session["user"])


if __name__=="__main__":
    app.run(debug=True)
