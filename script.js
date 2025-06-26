/* ---------- DOM Shortcuts ---------- */
const form      = document.getElementById('uploadForm');
const emailIn   = document.getElementById('email');
const fileIn    = document.getElementById('resume');
const btn       = document.getElementById('submitButton');
const msg       = document.getElementById('message');
const progWrap  = document.getElementById('progWrap');
const progBar   = document.getElementById('progBar');

/* ---------- Helpers ---------- */
function showMsg(text, type) {
  msg.textContent   = text;
  msg.className     = type;
  msg.style.display = 'block';
}

/* ---------- Progress-bar control ---------- */
let apiFinished   = false;
let apiResponseOK = false;
let apiText       = '';
let progTimer;

function startProgress() {
  let w = 0;
  progWrap.style.display = 'block';
  progBar.style.width    = '0%';

  progTimer = setInterval(() => {
    if (w < 95) {
      w += 1 + Math.random() * 3;            // 1–4 % step
      progBar.style.width = `${w}%`;
    } else if (apiFinished) {                // wait here until fetch resolves
      clearInterval(progTimer);
      progBar.style.width = '100%';
      setTimeout(() => {                      // tiny pause so 100 % is visible
        showMsg(apiText, apiResponseOK ? 'success' : 'error');
        progWrap.style.display = 'none';
        btn.disabled = false;
        btn.textContent = 'Analyze Resume';
      }, 400);
    }
  }, 120);
}

/* ---------- Main submit handler ---------- */
form.addEventListener('submit', e => {
  e.preventDefault();

  /* basic front-end validation */
  const email = emailIn.value.trim();
  const file  = fileIn.files[0];

  if (!/^.+@.+\..+$/.test(email)) { showMsg('Enter a valid email.',  'error'); return; }
  if (!file)                       { showMsg('Please upload a file.', 'error'); return; }

  /* init UI */
  btn.disabled = true;
  btn.textContent = 'Analyzing…';
  showMsg('Analyzing your resume. Please wait…', 'loading');
  apiFinished = false;
  startProgress();

  /* read file & call API */
  const reader = new FileReader();
  reader.onloadend = async () => {
    try {
      const body = {
        email,
        resume_content_base64: reader.result.split(',')[1],
        resume_file_type: file.type
      };

      const api = 'https://4i8fsa5psa.execute-api.us-east-1.amazonaws.com/Stage';
      const res = await fetch(api, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(body)
      });

      const data  = await res.json();
      apiFinished = true;
      apiResponseOK = res.ok;
      apiText = res.ok
        ? (data.message || 'Success! Check your inbox.')
        : (data.error   || 'Server error.');

    } catch (err) {
      apiFinished = true;
      apiResponseOK = false;
      apiText = 'A technical error occurred. Please try again.';
      console.error(err);
    }
  };
  reader.onerror = () => {
    apiFinished = true;
    apiResponseOK = false;
    apiText = 'Failed to read the file.';
  };

  reader.readAsDataURL(file);
});
