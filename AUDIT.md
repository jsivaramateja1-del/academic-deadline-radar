# Academic Deadline Radar — Complete Code Audit

## A. PROS — What the current site does well

1. **Clean auth flow** — Register → OTP → Login → OTP is solid. Brevo email with fallback to console logs is thoughtful for dev.
2. **Secure password hashing** — `werkzeug.security` with `generate_password_hash` / `check_password_hash` is correct.
3. **OTP invalidation** — Old OTPs are marked `used=1` before a new one is created. Expiry is checked server-side.
4. **User data isolation** — All task queries include `AND email=%s`, preventing cross-user access.
5. **Nice visual design** — Dark theme, animated blobs, color-coded urgency strips, Poppins font. Looks modern.
6. **Good OTP UX** — Auto-focus, auto-advance, paste support, backspace navigation, auto-submit.
7. **Password strength meter** — Real-time feedback in register form.
8. **Urgency color coding** — 5-level system (overdue/urgent/high/medium/safe) is reasonable.
9. **Sticky add form** — `position: sticky` on the add-task card is useful.
10. **Empty state** — Shows helpful message when no tasks exist.
11. **Gunicorn + Render deploy** — Production-ready server setup via render.yaml.

---

## B. CONS — Bugs, broken functionality, poor UX, security issues

### 🔴 CRITICAL

**B1 — DELETE via GET request (CSRF vulnerability)**
- `/delete_task/<id>` is a plain GET route with `<a href>` link.
- Any page or email can embed `<img src="/delete_task/42">` and silently delete a user's task on page load.
- Fix: Must be POST with CSRF token, or at minimum a form with method="POST".

**B2 — No CSRF protection anywhere**
- All forms (login, register, add_task, edit_task, reset_password) are POST forms with no CSRF tokens.
- Flask-WTF or manual CSRF tokens are required.

**B3 — Deadline stored as TEXT, not DATE**
- `deadline TEXT` in PostgreSQL. String comparisons on dates work by accident only when format is `YYYY-MM-DD`, but there's no constraint enforcing this.
- If a user somehow submits `13/05/2025`, the app crashes with `strptime` ValueError on dashboard.
- Fix: Use `DATE` column type in PostgreSQL.

**B4 — No input length limits / validation on task fields**
- `subject` and `title` accept unlimited text. A 100,000-character subject will be stored and may break the UI.
- Fix: Server-side `maxlength` enforcement.

**B5 — `init_db()` runs on every startup**
- Calling `init_db()` at module level means it runs on every worker startup. In a multi-worker Gunicorn setup this causes race conditions on table creation. Also opens a separate connection that bypasses the `g` connection pool.
- Fix: Use `IF NOT EXISTS` (already there) but move to a CLI command or startup hook, not bare module level.

**B6 — render.yaml references MAIL_USERNAME/MAIL_PASSWORD but app uses BREVO_API_KEY**
- The render.yaml env vars (`MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`) do not match what the app actually reads (`BREVO_API_KEY`, `MAIL_FROM`). Deploying from this file will silently fail to send emails.

**B7 — OTP countdown mismatch**
- OTP timer in the browser counts down 60 seconds (1 minute), but the OTP expires in 10 minutes server-side.
- The "Resend OTP" button activates after 60 seconds, but the original OTP is still valid for 9 more minutes.
- This is misleading and may cause unnecessary OTP spam.

**B8 — Session fixation risk**
- After successful login/OTP verification, the session is not regenerated. The session ID stays the same from the unauthenticated state.
- Fix: Call `session.clear()` then re-set `session['user']`.

### 🟠 HIGH

**B9 — No "completed" status on tasks**
- There is no way to mark a task as done. The CSS has `.task-done` and `.task-row.task-done` styles, and the dashboard template even references `task-check` button CSS — but the feature is completely unimplemented in both the backend and the HTML. The done/check button does not exist in the template.

**B10 — Priority score algorithm is backwards**
- `priority_score = (max(days_left, 0) * 2) + int(r['hours'])`
- Tasks are then sorted ascending by this score.
- A task due in 0 days with 1 hour gets score = 1. A task due in 10 days with 1 hour gets score = 21.
- This correctly puts urgent tasks first. BUT: an overdue task (`days_left < 0`) gets `max(days_left, 0) = 0`, same score as a task due TODAY. Overdue tasks aren't necessarily ranked first.
- Also: a 10-hour task due today (score = 10) sorts AFTER a 1-hour task due today (score = 1). High-workload urgent tasks should rank higher, not lower.

**B11 — No time component on deadlines**
- Deadlines are date-only (YYYY-MM-DD). A task "due today" could mean 11:59 PM vs 9:00 AM. At 11:00 PM, both show "Due today!" — the user has no idea which is truly urgent.

**B12 — `task-edit` and `task-del` are raw anchor tags, not wrapped in `.task-actions`**
- In the dashboard HTML, edit/delete links are direct `<a>` tags, not using the `.task-btn` or `.task-actions` CSS classes defined in the stylesheet. The hover effects for `.task-edit` conflict (defined twice in CSS with different styles).

**B13 — Dashboard `dash-body` has no `width: 100%`**
- The `.dash-body` has `max-width: 1180px; margin: 0 auto;` but no explicit `width: 100%`. On some browsers/screens, the content won't center correctly.

**B14 — Edit task page uses auth-page/auth-split layout**
- The edit task form reuses the login page layout (auth-split with left decorative panel). This is completely wrong UX — users navigated from their dashboard and are now on a page that looks like login. It should be a modal or an in-dashboard edit page.

**B15 — No server-side validation on deadline date**
- The `add_task` and `edit_task` routes accept any string as `deadline`. No check that it's a valid date, not in the past (if desired), or in the correct format.

**B16 — Forgot password reveals whether email is registered**
- "No verified account found with this email." tells attackers which emails have accounts. Should always say "If an account exists, a code has been sent."

**B17 — Flash messages shown in dev (OTP in plaintext)**
- `flash(f"OTP: {otp}  (check Render logs)", "info")` — the raw OTP is shown in the UI as a flash message when email sending fails. This is dangerous if the failure happens in production.

### 🟡 MEDIUM

**B18 — No course management** — Tasks have a `subject` text field, but there's no structured course list. Each task requires typing the course name from scratch with no autocomplete or validation. Typos create phantom duplicate "courses."

**B19 — No search or filter** — With 20+ tasks, the list becomes unusable. No filter by subject, type, or urgency.

**B20 — OTP countdown is 60s but doesn't disable the resend link** — The resend link is enabled after 60s but there's no server-side rate limiting on `/resend-otp`. A user can spam OTP requests.

**B21 — No `autocomplete` on dashboard form fields** — Subjects must be retyped every time. Browsers can't help because there's no `autocomplete` attribute.

**B22 — `task-metas` hidden on mobile** — `@media (max-width:600px) { .task-metas { display:none; } }` removes the days-left and hours pills on mobile. This is the most important information on a deadline tracker and it's hidden on the device students most commonly use.

**B23 — No loading state on form submission** — Forms submit without any visual feedback. On slow networks, users double-submit.

**B24 — `hours` field is `required` in HTML but treated as optional server-side** — Server-side: `except ValueError: hours = 0`. The HTML `required` attribute is client-side only and can be bypassed.

**B25 — `is_verified` stored as INTEGER (0/1) in PostgreSQL** — Should be BOOLEAN. Minor schema inconsistency.

**B26 — `used` in OTPs stored as INTEGER** — Same issue as above.

**B27 — No `<meta name="description">` or page titles per-page** — Base template has `<title>Academic Deadline Radar</title>` hardcoded for all pages.

**B28 — OTP countdown only shows minutes:seconds but OTP lives 10 minutes** — Countdown shows "1:00" and counts to 0:00, but OTP is valid 10 minutes. The displayed timer is wrong.

### 🟢 LOW

**B29 — Animated blobs run on all pages including dashboard** — Three large blurred circles with CSS animation on every page. On low-power devices this is a constant GPU drain.

**B30 — Google Fonts loaded via `@import` in CSS** — Slower than a `<link rel="preconnect">` + `<link>` in `<head>`.

**B31 — No `favicon`** — Browser shows generic blank icon.

**B32 — `app.secret_key` fallback `"fallback_dev_key_change_in_production"`** — While this is better than a hardcoded key with no comment, an app running without a proper SECRET_KEY will still work but sessions will be insecure between restarts.

---

## C. MISSING FEATURES (important for the product)

- ✅ **Mark task complete** — Most critical missing feature
- 📅 **Deadline time (not just date)** — "Due at 11:59 PM" vs "Due at 9:00 AM"
- 🔍 **Filter/sort tasks** — By subject, type, urgency, date
- 📚 **Course list with autocomplete** — Structured subjects instead of free text
- 📊 **This week / calendar view** — Weekly summary of upcoming deadlines
- 🔔 **In-app notification system** — Browser notifications or email reminders
- 📝 **Task notes field** — Brief notes per task ("submission link: ...", "Prof's email: ...")
- 🗑 **Bulk delete** — Remove multiple tasks at once (e.g., clear completed)

---

## D. POTENTIAL FUTURE FEATURES

**Worth considering:**
- Recurring tasks (weekly labs)
- Export to .ics calendar
- Dark/light theme toggle

**Over-engineered for this stage:**
- AI suggestions (adds complexity, needs API costs)
- Collaboration/shared tasks
- Mobile app
- Analytics dashboard
- Kanban board view

---

## E. PRIORITY CLASSIFICATION SUMMARY

| # | Issue | Priority |
|---|-------|----------|
| B1 | DELETE via GET / CSRF on delete | 🔴 Critical |
| B2 | No CSRF protection on forms | 🔴 Critical |
| B3 | Deadline as TEXT not DATE | 🔴 Critical |
| B4 | No input length validation | 🔴 Critical |
| B6 | render.yaml env var mismatch | 🔴 Critical |
| B8 | Session fixation | 🔴 Critical |
| B9 | No task complete feature | 🟠 High |
| B10 | Priority sort algorithm | 🟠 High |
| B11 | No time component | 🟠 High |
| B14 | Edit page uses wrong layout | 🟠 High |
| B16 | Email enumeration via forgot pw | 🟠 High |
| B17 | OTP shown in UI on email fail | 🟠 High |
| B18 | No course management | 🟡 Medium |
| B19 | No search/filter | 🟡 Medium |
| B22 | task-metas hidden on mobile | 🟡 Medium |
| B23 | No form loading state | 🟡 Medium |
| B7 | OTP countdown mismatch | 🟡 Medium |
| B12 | CSS class mismatch on buttons | 🟡 Medium |
| B28 | Wrong countdown timer value | 🟡 Medium |
| B29 | Blobs on all pages (perf) | 🟢 Low |
| B30 | Font loading via @import | 🟢 Low |
| B31 | No favicon | 🟢 Low |
