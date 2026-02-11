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
