from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime

app = Flask(__name__)

# ---------- DATABASE ----------
def init_db():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()

    c.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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

# ---------- ADD TASK ----------
@app.route('/add', methods=['POST'])
def add():
    subject = request.form['subject']
    title = request.form['title']
    task_type = request.form['task_type']
    deadline = request.form['deadline']
    hours = request.form['hours']

    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()

    c.execute("INSERT INTO tasks (subject, title, task_type, deadline, hours) VALUES (?, ?, ?, ?, ?)",
              (subject, title, task_type, deadline, hours))

    conn.commit()
    conn.close()

    return redirect('/')

# ---------- HOME + RECOMMENDATION ----------
@app.route('/')
def home():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()

    c.execute("SELECT * FROM tasks")
    tasks = c.fetchall()

    # RECOMMENDATION ALGORITHM
    recommended = None
    today = datetime.today()

    best_score = 999999

    for task in tasks:
        deadline = datetime.strptime(task[4], "%Y-%m-%d")
        days_left = (deadline - today).days

        hours = int(task[5])

        # Priority formula
        score = (days_left * 2) + hours

        if score < best_score:
            best_score = score
            recommended = task

    conn.close()

    return render_template('index.html', tasks=tasks, recommended=recommended)


if __name__ == '__main__':
    app.run(debug=True)
