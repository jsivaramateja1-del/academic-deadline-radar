
# Academic Deadline Radar

Academic Deadline Radar is a small web app made for students to keep track of assignments, records and exams in one place.

Instead of just listing tasks, it helps the student know which work should be started first based on how close the deadline is.

---

## Why we made this

In college, deadlines come from many places like WhatsApp groups, classroom announcements and LMS portals.
Students often forget submission dates and end up doing work at the last moment.

We wanted a simple page where a student can enter all academic work and immediately see what is urgent.

---

## What the app does

* Add a task with a deadline
* Store the task in database
* Show all upcoming work
* Highlight the nearest deadline
* Delete work after completion

The app compares the remaining days for each task and shows the task that should be started first.

---

## Technologies

* Python (Flask)
* HTML
* CSS
* SQLite3
* GitHub

---

## How to run

1. Download or clone the project
2. Open the folder in terminal

Install requirements:
pip install -r requirements.txt

Run:
python app.py

Open browser:
http://127.0.0.1:5000

---

## Example

If a student adds:

* Math assignment due tomorrow
* Lab record due in 3 days
* Internal exam next week

The system will show the math assignment as the task to start first.

---

## Team

Teja – Backend and database
Nikhil – Frontend
Harsha – Testing and documentation

---

## Future ideas

* calendar view
* reminder notifications
* mobile layout

