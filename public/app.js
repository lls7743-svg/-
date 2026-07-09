const consentScreen = document.getElementById('consentScreen');
const mainScreen = document.getElementById('mainScreen');
const consentCheck = document.getElementById('consentCheck');
const startBtn = document.getElementById('startBtn');
const micBtn = document.getElementById('micBtn');
const micLabel = document.getElementById('micLabel');
const statusText = document.getElementById('statusText');
const relationshipSelect = document.getElementById('relationshipSelect');
const transcriptBox = document.getElementById('transcriptBox');
const adviceFeed = document.getElementById('adviceFeed');
const moodIndicator = document.getElementById('moodIndicator');

const MIN_ADVICE_INTERVAL_MS = 7000; // 助言をリクエストする最短間隔
const MIN_NEW_CHARS = 12; // これ未満の新規発話ではリクエストしない
const CONTEXT_WINDOW_CHARS = 800; // Claudeへ渡す直近会話の文字数

let recognition = null;
let listening = false;
let fullFinalTranscript = '';
let sinceLastAdviceBuffer = '';
let lastAdviceAt = 0;
let adviceInFlight = false;
let restartTimer = null;
let rapidRestartCount = 0;
let lastRestartAt = 0;

consentCheck.addEventListener('change', () => {
  startBtn.disabled = !consentCheck.checked;
});

startBtn.addEventListener('click', () => {
  consentScreen.hidden = true;
  mainScreen.hidden = false;
});

const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;

function setStatus(text) {
  statusText.textContent = text;
}

function ensureRecognition() {
  if (!SpeechRecognitionImpl) {
    setStatus('このブラウザは音声認識に対応していません（Chrome推奨）');
    micBtn.disabled = true;
    return null;
  }
  const rec = new SpeechRecognitionImpl();
  rec.lang = 'ja-JP';
  rec.continuous = true;
  rec.interimResults = true;

  rec.onresult = (event) => {
    let interim = '';
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const result = event.results[i];
      const text = result[0].transcript;
      if (result.isFinal) {
        fullFinalTranscript += text;
        sinceLastAdviceBuffer += text;
      } else {
        interim += text;
      }
    }
    renderTranscript(interim);
    maybeRequestAdvice();
  };

  rec.onerror = (event) => {
    console.error('speech recognition error', event.error);
    if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
      setStatus('マイクの使用が許可されていません');
      stopListening();
    } else if (event.error === 'aborted' || event.error === 'no-speech' || event.error === 'network') {
      // モバイルのChromeでは無音・回線状況などでよく起こる。onendで自動再接続するため致命的ではない
      setStatus('聞いています…（再接続中）');
    } else {
      setStatus(`音声認識エラー: ${event.error}`);
    }
  };

  rec.onend = () => {
    if (!listening) return;

    const now = Date.now();
    // 短時間に何度も再起動を繰り返す場合は、マイクが実際には使えない状態とみなして止める
    if (now - lastRestartAt < 2000) {
      rapidRestartCount += 1;
    } else {
      rapidRestartCount = 0;
    }
    lastRestartAt = now;

    if (rapidRestartCount > 6) {
      setStatus('音声認識が不安定です。マイクの許可設定を確認し、開始し直してください');
      stopListening();
      return;
    }

    // 直後にstart()すると失敗しやすいため少し待ってから再開する
    clearTimeout(restartTimer);
    restartTimer = setTimeout(() => {
      if (!listening) return;
      try {
        rec.start();
        setStatus('聞いています…');
      } catch {
        // 既に開始中などの場合は無視（次のonendで再試行される）
      }
    }, 300);
  };

  return rec;
}

function renderTranscript(interim) {
  const finalPart = fullFinalTranscript
    ? `<span class="final">${escapeHtml(fullFinalTranscript)}</span>`
    : '';
  const interimPart = interim ? `<span>${escapeHtml(interim)}</span>` : '';
  transcriptBox.innerHTML = finalPart + interimPart;
  transcriptBox.scrollTop = transcriptBox.scrollHeight;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

async function maybeRequestAdvice() {
  const now = Date.now();
  if (adviceInFlight) return;
  if (sinceLastAdviceBuffer.trim().length < MIN_NEW_CHARS) return;
  if (now - lastAdviceAt < MIN_ADVICE_INTERVAL_MS) return;

  const recentTranscript = fullFinalTranscript.slice(-CONTEXT_WINDOW_CHARS);
  sinceLastAdviceBuffer = '';
  lastAdviceAt = now;
  adviceInFlight = true;

  try {
    const res = await fetch('/api/advice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        recentTranscript,
        relationship: relationshipSelect.value,
      }),
    });
    if (!res.ok) throw new Error(`status ${res.status}`);
    const data = await res.json();
    if (data.mood) {
      moodIndicator.dataset.mood = data.mood;
      moodIndicator.textContent = `雰囲気: ${moodLabel(data.mood)}`;
    }
    if (data.advice) {
      addAdviceCard(data.advice);
    }
  } catch (err) {
    console.error('advice request failed', err);
  } finally {
    adviceInFlight = false;
  }
}

function moodLabel(mood) {
  return { good: '良い感じ', neutral: '普通', caution: '要注意' }[mood] || '-';
}

function addAdviceCard(text) {
  const placeholder = adviceFeed.querySelector('.advice-placeholder');
  if (placeholder) placeholder.remove();

  const card = document.createElement('div');
  card.className = 'advice-card';
  const time = document.createElement('time');
  time.textContent = new Date().toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  card.textContent = text;
  card.appendChild(time);
  adviceFeed.prepend(card);
}

function startListening() {
  recognition = ensureRecognition();
  if (!recognition) return;
  try {
    recognition.start();
    listening = true;
    micBtn.classList.add('active');
    micLabel.textContent = 'マイク停止';
    setStatus('聞いています…');
  } catch (err) {
    console.error(err);
    setStatus('マイクの開始に失敗しました');
  }
}

function stopListening() {
  listening = false;
  clearTimeout(restartTimer);
  rapidRestartCount = 0;
  micBtn.classList.remove('active');
  micLabel.textContent = 'マイク開始';
  setStatus('待機中');
  if (recognition) {
    recognition.stop();
  }
}

micBtn.addEventListener('click', () => {
  if (listening) {
    stopListening();
  } else {
    startListening();
  }
});
