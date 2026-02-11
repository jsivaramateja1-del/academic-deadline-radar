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
