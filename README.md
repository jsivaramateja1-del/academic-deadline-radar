# Academic Deadline Radar

A smart academic planner that helps students decide what to study first based on urgency and workload.

---

## Problem Statement

Students often forget deadlines or start studying too late because they cannot properly prioritize assignments, labs, and exams. Traditional reminder apps only store tasks — they do not analyze which task should be started first.

This leads to last-minute submissions, academic stress, poor time management, and low productivity.

Academic Deadline Radar solves this by automatically analyzing deadlines and estimated effort, and recommending the most urgent task.

---

## Features

- Secure registration and login with OTP email verification
- Two-factor login via OTP
- Add assignments, labs, projects, exams, and quizzes
- Edit any task after adding it
- Mark tasks as complete / incomplete
- Deadline tracking with automatic priority calculation
- Color-coded urgency system:
  - 🔴 Red — Overdue
  - 🟠 Orange — Due within 1 day
  - 🟡 Yellow — Due within 3 days
  - 🔵 Blue — Due within 7 days
  - 🟢 Green — Safe / low priority
- Completed tasks sink to the bottom automatically
- Personalized dashboard per user
- Persistent SQLite database
- Password reset via OTP

---

## Priority Formula
Priority Score = (Days Remaining × 2) + Estimated Hours

Lower score = higher urgency. Overdue tasks always sort first. Completed tasks always sort last.

---

## Tech Stack

- **Frontend:** HTML, CSS, JavaScript
- **Backend:** Python (Flask)
- **Database:** SQLite3
- **Auth:** OTP via Flask-Mail, password hashing via Werkzeug
- **Deploy:** Render / Railway compatible

---

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/jsivaramateja1-del/academic-deadline-radar.git
cd academic-deadline-radar
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:
SECRET_KEY=your_random_secret_key
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_gmail_app_password
MAIL_DEFAULT_SENDER=Academic Deadline Radar your_email@gmail.com

> If you skip email setup, OTPs will be printed to the server console instead.

### 4. Run

```bash
python app.py
```

### 5. Open in browser
http://127.0.0.1:5000/

---

## Deploy to Render (free)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Render auto-detects `render.yaml` — click **Deploy**
5. Set environment variables in the Render dashboard under **Environment**

---

## Project Structure
academic-deadline-radar/
│
├── app.py
├── database.db           (auto-created on first run)
├── requirements.txt
├── render.yaml
├── run.bat
├── .env                  (not committed — create from .env.example)
├── .env.example
│
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── verify_otp.html
│   ├── forgot_password.html
│   ├── reset_password.html
│   ├── edit_task.html
│   └── dashboard.html
│
└── static/
├── style.css
└── app.js

---

## Team

- Siva Rama Teja
- Nikhil

---

## Future Scope

- Email reminders before deadlines
- Mobile app version
- Google Calendar integration
- Study time suggestions based on workload

---

## Security

Credentials and secret keys are loaded from a `.env` file which is not committed to version control. User passwords are hashed using Werkzeug. Sessions are managed server-side by Flask. Destructive actions (delete, toggle) use POST requests only.