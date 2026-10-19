'use strict';

/* ── OTP boxes ───────────────────────────────────────────────────────────────── */
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
      boxes[Math.min(digits.length, boxes.length - 1)].focus();
      tryAutoSubmit();
    });
  });
  function tryAutoSubmit() {
    if ([...boxes].every(b => b.value.length === 1))
      setTimeout(() => document.getElementById('otp-form')?.submit(), 280);
  }
})();

/* ── OTP countdown (10 min, resend after 60s) ───────────────────────────────── */
(function () {
  const el = document.getElementById('countdown');
  const resend = document.getElementById('resend-btn');
  if (!el) return;
  let secs = 600;
  const tick = setInterval(() => {
    secs--;
    if (secs <= 0) { clearInterval(tick); el.textContent = '0:00'; el.classList.add('done'); enableResend(); return; }
    el.textContent = `${Math.floor(secs/60)}:${String(secs%60).padStart(2,'0')}`;
    if (secs === 540) enableResend();
  }, 1000);
  function enableResend() {
    if (resend) { resend.classList.add('active'); resend.removeAttribute('aria-disabled'); }
  }
})();

/* ── Password strength meter ─────────────────────────────────────────────────── */
(function () {
  const pw = document.getElementById('pass');
  const fill = document.getElementById('str-fill');
  const label = document.getElementById('str-lbl');
  if (!pw || !fill || !label) return;
  const levels = [
    {t:'',p:'0%',c:'transparent'},
    {t:'Weak',p:'25%',c:'#EF4444'},
    {t:'Fair',p:'50%',c:'#F97316'},
    {t:'Good',p:'75%',c:'#EAB308'},
    {t:'Strong',p:'90%',c:'#22C55E'},
    {t:'Very strong',p:'100%',c:'#14B8A6'},
  ];
  pw.addEventListener('input', () => {
    const v = pw.value;
    let score = 0;
    if (v.length >= 8) score++;
    if (v.length >= 12) score++;
    if (/[A-Z]/.test(v)) score++;
    if (/[0-9]/.test(v)) score++;
    if (/[^A-Za-z0-9]/.test(v)) score++;
    const lvl = levels[Math.min(score,5)];
    fill.style.width = lvl.p; fill.style.background = lvl.c;
    label.textContent = lvl.t; label.style.color = lvl.c;
  });
})();

/* ── Password show/hide ──────────────────────────────────────────────────────── */
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

/* ── Submit loading state ────────────────────────────────────────────────────── */
document.querySelectorAll('form').forEach(form => {
  form.addEventListener('submit', () => {
    const btn = form.querySelector('button[type="submit"]');
    if (!btn || btn.classList.contains('task-check') || btn.classList.contains('task-del') ||
        btn.classList.contains('gh-toggle') || btn.classList.contains('theme-btn')) return;
    btn.disabled = true;
    setTimeout(() => { btn.disabled = false; }, 8000);
  });
});

/* ── Date min today ──────────────────────────────────────────────────────────── */
(function () {
  const dl = document.getElementById('f-deadline');
  if (!dl) return;
  dl.setAttribute('min', new Date().toISOString().split('T')[0]);
  // FIX 7: Warn if time already passed for today
  dl.addEventListener('change', checkTimeWarning);
  const timeEl = document.getElementById('f-time');
  if (timeEl) timeEl.addEventListener('change', checkTimeWarning);
  function checkTimeWarning() {
    const dateVal = dl.value;
    const timeVal = timeEl ? timeEl.value : '';
    if (!dateVal || !timeVal) return;
    const today = new Date().toISOString().split('T')[0];
    if (dateVal === today) {
      const now = new Date();
      const [h, m] = timeVal.split(':').map(Number);
      if (h < now.getHours() || (h === now.getHours() && m <= now.getMinutes())) {
        if (!document.getElementById('time-warn')) {
          const warn = document.createElement('div');
          warn.id = 'time-warn';
          warn.style.cssText = 'font-size:11px;color:#F97316;margin-top:4px;font-weight:600;';
          warn.textContent = '⚠️ This time has already passed today.';
          timeEl.parentElement.appendChild(warn);
        }
      } else {
        document.getElementById('time-warn')?.remove();
      }
    } else {
      document.getElementById('time-warn')?.remove();
    }
  }
})();

/* ── Group toggle ────────────────────────────────────────────────────────────── */
function toggleGroup(btn) {
  const body = btn.closest('.task-group').querySelector('.group-body');
  if (!body) return;
  btn.textContent = body.classList.toggle('collapsed') ? '▶' : '▼';
}

/* ── FIX 5: Bulk select ──────────────────────────────────────────────────────── */
(function () {
  const bulkCard    = document.getElementById('bulk-card');
  const bulkIdsEl   = document.getElementById('bulk-ids');
  const selCountEl  = document.getElementById('sel-count');
  const selectAllBtn = document.getElementById('select-all-btn');
  if (!bulkCard) return;

  function getChecked() {
    return [...document.querySelectorAll('.task-cb:checked')];
  }

  function updateBulk() {
    const checked = getChecked();
    bulkCard.hidden = checked.length === 0;
    if (selCountEl) selCountEl.textContent = checked.length;
    if (bulkIdsEl) {
      bulkIdsEl.innerHTML = '';
      checked.forEach(cb => {
        const inp = document.createElement('input');
        inp.type = 'hidden'; inp.name = 'task_ids'; inp.value = cb.dataset.id;
        bulkIdsEl.appendChild(inp);
      });
    }
  }

  document.addEventListener('change', e => {
    if (e.target.classList.contains('task-cb')) updateBulk();
  });

  if (selectAllBtn) {
    selectAllBtn.addEventListener('click', () => {
      const visible = [...document.querySelectorAll('.task-row:not([hidden]) .task-cb')];
      const allChecked = visible.every(cb => cb.checked);
      visible.forEach(cb => { cb.checked = !allChecked; });
      updateBulk();
    });
  }
})();

/* ── Search + filter across groups ──────────────────────────────────────────── */
(function () {
  const searchEl    = document.getElementById('task-search');
  const filterTabs  = document.querySelectorAll('.filter-tab');
  const noResults   = document.getElementById('no-results');
  if (!searchEl) return;

  let activeFilter = 'active';
  let searchQuery  = '';

  function applyAll() {
    let visible = 0;
    document.querySelectorAll('.task-row').forEach(row => {
      const completed = row.dataset.completed === 'true';
      const color     = row.dataset.color;
      const q         = searchQuery.toLowerCase();
      const matchSearch = !q || (row.dataset.title||'').includes(q) || (row.dataset.subject||'').includes(q);
      let matchFilter = true;
      if (activeFilter === 'active')  matchFilter = !completed;
      if (activeFilter === 'overdue') matchFilter = !completed && color === 'overdue';
      if (activeFilter === 'done')    matchFilter = completed;
      const show = matchSearch && matchFilter;
      row.hidden = !show;
      if (show) visible++;
    });
    document.querySelectorAll('.task-group').forEach(group => {
      const anyVisible = [...group.querySelectorAll('.task-row')].some(r => !r.hidden);
      group.hidden = !anyVisible;
    });
    if (noResults) noResults.hidden = visible > 0;
  }

  searchEl.addEventListener('input', () => { searchQuery = searchEl.value.trim(); applyAll(); });
  filterTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      filterTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      activeFilter = tab.dataset.filter;
      applyAll();
    });
  });

  applyAll();
})();
