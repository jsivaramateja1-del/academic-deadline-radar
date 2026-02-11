from datetime import datetime
from flask import Flask, render_template, request, redirect
import sqlite3

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


# ---------- HOME PAGE ----------
@app.route('/')
def home():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("SELECT * FROM tasks")
    tasks = c.fetchall()
    conn.close()

    today = datetime.today()
    prioritized_task = None
    highest_score = -1

    for task in tasks:
        deadline_str = task[4]  # deadline column
        hours = int(task[5])

        try:
            deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d")
            days_left = (deadline_date - today).days

            if days_left <= 0:
                days_left = 1

            score = hours / days_left

            if score > highest_score:
                highest_score = score
                prioritized_task = task

        except:
            continue

    return render_template('index.html', tasks=tasks, prioritized_task=prioritized_task)


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

    c.execute(
        "INSERT INTO tasks (subject, title, task_type, deadline, hours) VALUES (?, ?, ?, ?, ?)",
        (subject, title, task_type, deadline, hours)
    )

    conn.commit()
    conn.close()

    return redirect('/')


# ---------- RUN SERVER ----------
if __name__ == '__main__':
    app.run(debug=True)
