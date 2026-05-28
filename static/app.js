const otpBoxes = document.querySelectorAll('.otp-boxes input');

if (otpBoxes.length) {
  otpBoxes[0].focus();

  otpBoxes.forEach((box, idx) => {
    box.addEventListener('input', e => {
      const val = e.target.value.replace(/\D/g, '');
      e.target.value = val.slice(-1);
      e.target.classList.toggle('has-val', e.target.value !== '');
      if (val && idx < otpBoxes.length - 1) otpBoxes[idx + 1].focus();
      tryAutoSubmit();
    });

    box.addEventListener('keydown', e => {
      if (e.key === 'Backspace' && !box.value && idx > 0) {
        otpBoxes[idx - 1].value = '';
        otpBoxes[idx - 1].classList.remove('has-val');
        otpBoxes[idx - 1].focus();
      }
    });

    box.addEventListener('paste', e => {
      e.preventDefault();
      const text = (e.clipboardData || window.clipboardData)
        .getData('text').replace(/\D/g, '');
      text.split('').slice(0, 6).forEach((ch, i) => {
        if (otpBoxes[i]) {
          otpBoxes[i].value = ch;
          otpBoxes[i].classList.add('has-val');
        }
      });
      otpBoxes[Math.min(text.length, 5)].focus();
      tryAutoSubmit();
    });
  });

  function tryAutoSubmit() {
    if ([...otpBoxes].every(b => b.value.length === 1)) {
      setTimeout(() => document.getElementById('otp-form')?.submit(), 300);
    }
  }
}

const cdEl    = document.getElementById('countdown');
const rsndBtn = document.querySelector('.resend-btn');

if (cdEl) {
  let secs = 60;
  const iv = setInterval(() => {
    secs--;
    if (secs <= 0) {
      clearInterval(iv);
      cdEl.textContent = '0:00';
      cdEl.classList.add('done');
      if (rsndBtn) rsndBtn.classList.add('on');
      return;
    }
    cdEl.textContent =
      `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`;
  }, 1000);
}

const pwEl   = document.getElementById('pass');
const sfill  = document.getElementById('str-fill');
const slabel = document.getElementById('str-lbl');

if (pwEl) {
  pwEl.addEventListener('input', () => {
    const v = pwEl.value;
    let s = 0;
    if (v.length >= 6)           s++;
    if (v.length >= 10)          s++;
    if (/[A-Z]/.test(v))         s++;
    if (/[0-9]/.test(v))         s++;
    if (/[^A-Za-z0-9]/.test(v))  s++;

    const lvl = [
      { t: '',        p: '0%',   c: 'transparent' },
      { t: 'Weak',    p: '25%',  c: '#EF4444'     },
      { t: 'Fair',    p: '50%',  c: '#F97316'     },
      { t: 'Good',    p: '75%',  c: '#EAB308'     },
      { t: 'Strong',  p: '90%',  c: '#22C55E'     },
      { t: 'Great ✓', p: '100%', c: '#14B8A6'     }
    ][Math.min(s, 5)];

    if (sfill)  { sfill.style.width = lvl.p; sfill.style.background = lvl.c; }
    if (slabel) { slabel.textContent = lvl.t; slabel.style.color = lvl.c; }
  });
}

document.querySelectorAll('.pw-toggle').forEach(btn => {
  btn.addEventListener('click', () => {
    const inp = btn.previousElementSibling;
    inp.type        = inp.type === 'password' ? 'text' : 'password';
    btn.textContent = inp.type === 'password' ? '👁' : '🙈';
  });
});