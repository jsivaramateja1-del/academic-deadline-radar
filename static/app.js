'use strict';

/* ── OTP boxes ──────────────────────────────────────────────────────────────── */
(function () {
  const boxes = document.querySelectorAll('.otp-boxes input');
  if (!boxes.length) return;

  boxes[0].focus();

  boxes.forEach((box, idx) => {
    box.addEventListener('input', e => {
      const val = e.target.value.replace(/\D/g, '');
      e.target.value = val.slice(-1);
      e.target.classList.toggle('has-val', !!e.target.value);
      if (val && idx < boxes.length - 1) boxes[idx + 1].focus();
      tryAutoSubmit();
    });

    box.addEventListener('keydown', e => {
      if (e.key === 'Backspace' && !box.value && idx > 0) {
        boxes[idx - 1].value = '';
        boxes[idx - 1].classList.remove('has-val');
        boxes[idx - 1].focus();
      }
    });

    box.addEventListener('paste', e => {
      e.preventDefault();
      const digits = (e.clipboardData || window.clipboardData)
        .getData('text').replace(/\D/g, '').slice(0, 6);
      digits.split('').forEach((ch, i) => {
        if (boxes[i]) { boxes[i].value = ch; boxes[i].classList.add('has-val'); }
      });
      const next = Math.min(digits.length, boxes.length - 1);
      boxes[next].focus();
      tryAutoSubmit();
    });
  });

  function tryAutoSubmit() {
    if ([...boxes].every(b => b.value.length === 1)) {
      setTimeout(() => document.getElementById('otp-form')?.submit(), 280);
    }
  }
})();

/* ── OTP countdown (10 minutes matching server) ─────────────────────────────── */
(function () {
  const el     = document.getElementById('countdown');
  const resend = document.getElementById('resend-btn');
  if (!el) return;

  // 10 minutes = 600 seconds; enable resend after 60s
  let secs = 600;
  let resendEnabled = false;

  const tick = setInterval(() => {
    secs--;
    if (secs <= 0) {
      clearInterval(tick);
      el.textContent = '0:00';
      el.classList.add('done');
      enableResend();
      return;
    }
    el.textContent = `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`;
    if (!resendEnabled && secs <= 540) { // after 60s
      enableResend();
    }
  }, 1000);

  function enableResend() {
    resendEnabled = true;
    if (resend) {
      resend.classList.add('active');
      resend.removeAttribute('aria-disabled');
    }
  }
})();

/* ── Password strength meter ────────────────────────────────────────────────── */
(function () {
  const pw    = document.getElementById('pass');
  const fill  = document.getElementById('str-fill');
  const label = document.getElementById('str-lbl');
  if (!pw || !fill || !label) return;

  const levels = [
    { t: '',             p: '0%',   c: 'transparent' },
    { t: 'Weak',         p: '25%',  c: '#EF4444' },
    { t: 'Fair',         p: '50%',  c: '#F97316' },
    { t: 'Good',         p: '75%',  c: '#EAB308' },
    { t: 'Strong',       p: '90%',  c: '#22C55E' },
    { t: 'Very strong',  p: '100%', c: '#14B8A6' },
  ];

  pw.addEventListener('input', () => {
    const v = pw.value;
    let score = 0;
    if (v.length >= 8)           score++;
    if (v.length >= 12)          score++;
    if (/[A-Z]/.test(v))         score++;
    if (/[0-9]/.test(v))         score++;
    if (/[^A-Za-z0-9]/.test(v))  score++;
    const lvl = levels[Math.min(score, 5)];
    fill.style.width      = lvl.p;
    fill.style.background = lvl.c;
    label.textContent     = lvl.t;
    label.style.color     = lvl.c;
  });
})();

/* ── Password visibility toggle ─────────────────────────────────────────────── */
document.querySelectorAll('.pw-toggle').forEach(btn => {
  btn.addEventListener('click', () => {
    const inp = btn.closest('.pw-wrap').querySelector('input');
    if (!inp) return;
    const show = inp.type === 'password';
    inp.type = show ? 'text' : 'password';
    btn.querySelector('.eye-icon').textContent = show ? '🙈' : '👁';
    btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
  });
});

/* ── Submit button loading state (prevents double-submit) ───────────────────── */
document.querySelectorAll('form').forEach(form => {
  form.addEventListener('submit', () => {
    const btn = form.querySelector('button[type="submit"]');
    if (!btn) return;
    btn.disabled = true;
    const text    = btn.querySelector('.btn-text');
    const spinner = btn.querySelector('.btn-spinner');
    if (text)    text.hidden = true;
    if (spinner) spinner.hidden = false;
    // re-enable after 8s in case server is slow / user navigates back
    setTimeout(() => { btn.disabled = false; }, 8000);
  });
});

/* ── Dashboard: search + filter + sort ─────────────────────────────────────── */
(function () {
  const searchEl   = document.getElementById('task-search');
  const sortEl     = document.getElementById('sort-sel');
  const filterTabs = document.querySelectorAll('.filter-tab');
  const taskList   = document.getElementById('task-list');
  const noResults  = document.getElementById('no-results');
  if (!taskList) return;

  let activeFilter = 'active';
  let activeSort   = 'urgency';
  let searchQuery  = '';

  function getRows() {
    return Array.from(taskList.querySelectorAll('.task-row'));
  }

  function applyFilter() {
    const rows   = getRows();
    let visible  = 0;

    rows.forEach(row => {
      const completed = row.dataset.completed === 'true';
      const color     = row.dataset.color;
      const title     = row.dataset.title || '';
      const subject   = row.dataset.subject || '';
      const q         = searchQuery.toLowerCase();
      const matchSearch = !q || title.includes(q) || subject.includes(q);

      let matchFilter = true;
      if (activeFilter === 'active')  matchFilter = !completed;
      if (activeFilter === 'overdue') matchFilter = !completed && color === 'overdue';
      if (activeFilter === 'done')    matchFilter = completed;
      // 'all' shows everything

      const show = matchSearch && matchFilter;
      row.hidden = !show;
      if (show) visible++;
    });

    if (noResults) noResults.hidden = visible > 0;
  }

  function applySort() {
    const rows = getRows();
    rows.sort((a, b) => {
      if (activeSort === 'deadline') {
        return (a.dataset.deadline || '').localeCompare(b.dataset.deadline || '');
      }
      if (activeSort === 'subject') {
        return (a.dataset.subject || '').localeCompare(b.dataset.subject || '');
      }
      if (activeSort === 'hours') {
        return parseInt(b.dataset.hours || 0) - parseInt(a.dataset.hours || 0);
      }
      // Default: urgency — keep DOM order (already sorted server-side)
      return 0;
    });
    rows.forEach(r => taskList.appendChild(r));
  }

  if (searchEl) {
    searchEl.addEventListener('input', () => {
      searchQuery = searchEl.value.trim();
      applyFilter();
    });
  }

  filterTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      filterTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      activeFilter = tab.dataset.filter;
      applyFilter();
    });
  });

  if (sortEl) {
    sortEl.addEventListener('change', () => {
      activeSort = sortEl.value;
      applySort();
    });
  }

  // Initial state: show active tasks only
  applyFilter();
})();

/* ── Date input: prevent past dates on add form ─────────────────────────────── */
(function () {
  const dl = document.getElementById('f-deadline');
  if (!dl) return;
  const today = new Date().toISOString().split('T')[0];
  dl.setAttribute('min', today);
})();

/* ── Group toggle (completed section) ──────────────────────────────────────── */
function toggleGroup(btn) {
  const body = btn.closest('.task-group').querySelector('.group-body');
  if (!body) return;
  const collapsed = body.classList.toggle('collapsed');
  btn.textContent = collapsed ? '▶' : '▼';
}

/* ── Search across grouped layout ───────────────────────────────────────────── */
(function () {
  const searchEl  = document.getElementById('task-search');
  const filterTabs = document.querySelectorAll('.filter-tab');
  const noResults  = document.getElementById('no-results');
  if (!searchEl) return;

  let activeFilter = 'active';
  let searchQuery  = '';

  function applyAll() {
    const rows = document.querySelectorAll('.task-row');
    let visible = 0;

    rows.forEach(row => {
      const completed = row.dataset.completed === 'true';
      const color     = row.dataset.color;
      const title     = row.dataset.title || '';
      const subject   = row.dataset.subject || '';
      const q         = searchQuery.toLowerCase();

      const matchSearch = !q || title.includes(q) || subject.includes(q);

      let matchFilter = true;
      if (activeFilter === 'active')  matchFilter = !completed;
      if (activeFilter === 'overdue') matchFilter = !completed && color === 'overdue';
      if (activeFilter === 'done')    matchFilter = completed;

      const show = matchSearch && matchFilter;
      row.hidden = !show;
      if (show) visible++;
    });

    // Hide empty group headers
    document.querySelectorAll('.task-group').forEach(group => {
      const anyVisible = [...group.querySelectorAll('.task-row')].some(r => !r.hidden);
      group.hidden = !anyVisible;
    });

    if (noResults) noResults.hidden = visible > 0;
  }

  searchEl.addEventListener('input', () => {
    searchQuery = searchEl.value.trim();
    applyAll();
  });

  filterTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      filterTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      activeFilter = tab.dataset.filter;
      applyAll();
    });
  });

  // Start on active filter
  applyAll();
})();
