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
const adviceStatusText = document.getElementById('adviceStatusText');

const modeMicBtn = document.getElementById('modeMicBtn');
const modeTextBtn = document.getElementById('modeTextBtn');
const micView = document.getElementById('micView');
const textView = document.getElementById('textView');
const conversationText = document.getElementById('conversationText');
const analyzeTextBtn = document.getElementById('analyzeTextBtn');
const textAdviceResult = document.getElementById('textAdviceResult');
const textMoodIndicator = document.getElementById('textMoodIndicator');

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
let currentInterim = '';
let interimUnchangedTicks = 0;
let staleCheckTimer = null;
let lastCommittedSegment = '';
let erroredSinceLastResult = false;

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
        appendFinalSegment(text);
      } else {
        interim += text;
      }
    }
    currentInterim = interim;
    interimUnchangedTicks = 0;
    erroredSinceLastResult = false;
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
      erroredSinceLastResult = true;
      setStatus('聞いています…（再接続中）');
    } else {
      setStatus(`音声認識エラー: ${event.error}`);
    }
  };

  rec.onend = () => {
    if (!listening) return;

    // エラーによる強制再接続の場合、話している途中の音声が新しいセッションで
    // 再度拾われ直すことが多く、ここで確定させると同じセリフが重複してしまう。
    // 本当に発話が止まって終了した場合のみ、確定していなかった分を繰り入れる。
    if (!erroredSinceLastResult) {
      commitInterim();
    }
    erroredSinceLastResult = false;

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

function appendFinalSegment(text) {
  const trimmed = text.trim();
  if (!trimmed) return;
  // 再接続直後は直前と同じ内容を再度拾いがちなので、完全一致の連続重複は無視する
  if (trimmed === lastCommittedSegment) return;
  fullFinalTranscript += text;
  sinceLastAdviceBuffer += text;
  lastCommittedSegment = trimmed;
}

function commitInterim() {
  if (!currentInterim.trim()) return;
  appendFinalSegment(currentInterim);
  currentInterim = '';
  interimUnchangedTicks = 0;
  renderTranscript('');
}

function checkStaleInterim() {
  if (!listening) return;
  if (currentInterim.trim()) {
    // 数秒間テキストが更新されていない = 発言の切れ目とみなして確定させる
    interimUnchangedTicks += 1;
    if (interimUnchangedTicks >= 2) {
      commitInterim();
    }
  }
  maybeRequestAdvice();
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
  adviceStatusText.classList.remove('error');
  adviceStatusText.textContent = '分析中…';

  try {
    const res = await fetch('/api/advice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        recentTranscript,
        relationship: relationshipSelect.value,
      }),
    });
    if (!res.ok) {
      let detail = `status ${res.status}`;
      try {
        const errBody = await res.json();
        if (errBody?.error) detail += ` / ${errBody.error}`;
      } catch {
        // レスポンスがJSONでない場合は無視
      }
      throw new Error(detail);
    }
    const data = await res.json();
    if (data.mood) {
      moodIndicator.dataset.mood = data.mood;
      moodIndicator.textContent = `雰囲気: ${moodLabel(data.mood)}`;
    }
    if (data.advice) {
      addAdviceCard(data.advice);
      adviceStatusText.textContent = '';
    } else {
      adviceStatusText.textContent = '今回は特にアドバイスなし（会話は分析できています）';
    }
  } catch (err) {
    console.error('advice request failed', err);
    adviceStatusText.classList.add('error');
    adviceStatusText.textContent = `アドバイス取得エラー: ${err.message}`;
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
    currentInterim = '';
    interimUnchangedTicks = 0;
    lastCommittedSegment = '';
    erroredSinceLastResult = false;
    clearInterval(staleCheckTimer);
    staleCheckTimer = setInterval(checkStaleInterim, 2000);
  } catch (err) {
    console.error(err);
    setStatus('マイクの開始に失敗しました');
  }
}

function stopListening() {
  listening = false;
  clearTimeout(restartTimer);
  clearInterval(staleCheckTimer);
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

function setMode(mode) {
  const isMic = mode === 'mic';
  modeMicBtn.classList.toggle('active', isMic);
  modeTextBtn.classList.toggle('active', !isMic);
  micView.hidden = !isMic;
  textView.hidden = isMic;
  micBtn.hidden = !isMic;
  statusText.hidden = !isMic;

  if (!isMic && listening) {
    stopListening();
  }
}

modeMicBtn.addEventListener('click', () => setMode('mic'));
modeTextBtn.addEventListener('click', () => setMode('text'));

function addResultCard(container, { label, text, cssClass }) {
  const card = document.createElement('div');
  card.className = cssClass;
  if (label) {
    const labelEl = document.createElement('span');
    labelEl.className = 'reply-label';
    labelEl.textContent = label;
    card.appendChild(labelEl);
    card.appendChild(document.createTextNode(text));
  } else {
    card.textContent = text;
  }
  container.prepend(card);
}

analyzeTextBtn.addEventListener('click', async () => {
  const conversation = conversationText.value.trim();
  if (!conversation) return;

  analyzeTextBtn.disabled = true;
  analyzeTextBtn.textContent = '分析中…';

  try {
    const res = await fetch('/api/analyze-text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation,
        relationship: relationshipSelect.value,
      }),
    });
    if (!res.ok) throw new Error(`status ${res.status}`);
    const data = await res.json();

    const placeholder = textAdviceResult.querySelector('.advice-placeholder');
    if (placeholder) placeholder.remove();

    if (data.mood) {
      textMoodIndicator.dataset.mood = data.mood;
      textMoodIndicator.textContent = `雰囲気: ${moodLabel(data.mood)}`;
    }
    if (data.suggestedReply) {
      addResultCard(textAdviceResult, { label: '返信案', text: data.suggestedReply, cssClass: 'reply-card' });
    }
    if (data.advice) {
      addResultCard(textAdviceResult, { label: null, text: data.advice, cssClass: 'advice-card' });
    }
  } catch (err) {
    console.error('text analysis failed', err);
    addResultCard(textAdviceResult, { label: null, text: '分析に失敗しました。もう一度お試しください。', cssClass: 'advice-card' });
  } finally {
    analyzeTextBtn.disabled = false;
    analyzeTextBtn.textContent = '分析する';
  }
});
