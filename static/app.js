// ── State ────────────────────────────────────────────
let ws = null;
let mediaRecorder = null;
let stream = null;
let sessionId = null;
let isRecording = false;
let chunkCount = 0;
let wordCount = 0;
let timerInterval = null;
let timerSeconds = 0;
let transcriptChunks = [];
let headerChunk = null;
let autoScroll = true;

// ── Session ID ───────────────────────────────────────
function generateSessionId() {
    return 'sess_' + Math.random().toString(36).substr(2, 9);
}

// ── Timer ────────────────────────────────────────────
function startTimer() {
    timerSeconds = 0;
    timerInterval = setInterval(() => {
        timerSeconds++;
        const m = String(Math.floor(timerSeconds / 60)).padStart(2, '0');
        const s = String(timerSeconds % 60).padStart(2, '0');
        document.getElementById('timer').textContent = `${m}:${s}`;
    }, 1000);
    document.getElementById('timer').classList.add('active');
}

function stopTimer() {
    clearInterval(timerInterval);
    document.getElementById('timer').classList.remove('active');
}

// ── Status badge ─────────────────────────────────────
function setStatus(state, text) {
    const badge = document.getElementById('status-badge');
    badge.className = 'status-badge ' + state;
    document.getElementById('status-text').textContent = text;
}

// ── Toast notifications ───────────────────────────────
function toast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toasts');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    const icons = { error: '✕', success: '✓', info: 'i' };
    el.innerHTML = `<div class="toast-icon">${icons[type] || 'i'}</div><span>${message}</span>`;
    container.appendChild(el);
    setTimeout(() => {
        el.style.transition = 'opacity 0.3s, transform 0.3s';
        el.style.opacity = '0';
        el.style.transform = 'translateX(10px)';
        setTimeout(() => el.remove(), 300);
    }, duration);
}

// ── WebSocket message handler ─────────────────────────
function handleMessage(data) {
    switch (data.type) {
        case 'status':
            toast(data.message, 'info');
            break;

        case 'transcript':
            appendTranscript(data.text, data.chunk_id);
            wordCount = data.total_words || wordCount + data.text.split(' ').length;
            chunkCount = data.chunk_id || chunkCount + 1;
            updateStats();
            break;

        case 'progressive_summary':
            renderProgressiveSummary(data.text);
            break;

        case 'final_summary':
            renderFinalSummary(data.text, data);
            break;

        case 'qa_answer':
            renderQAAnswer(data.text, data.question);
            break;

        case 'error':
            toast(data.message, 'error');
            console.error('Backend error:', data);
            break;
    }
}

// ── Transcript rendering ──────────────────────────────
function appendTranscript(text, chunkId) {
    const content = document.getElementById('transcript-content');

    // remove empty state
    const empty = content.querySelector('.transcript-empty');
    if (empty) empty.remove();

    const now = new Date().toLocaleTimeString('en', {
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });

    const chunk = document.createElement('div');
    chunk.className = 'transcript-chunk';
    chunk.innerHTML = `
        <div class="chunk-text">${escapeHtml(text)}</div>
        <div class="chunk-meta">
            <span class="chunk-num">#${chunkId}</span>
            <span class="chunk-time">${now}</span>
        </div>
    `;
    content.appendChild(chunk);

    // auto scroll only if user hasn't manually scrolled up
    const body = document.getElementById('transcript-body');
    if (autoScroll) {
        body.scrollTop = body.scrollHeight;
    }

    // update badge
    document.getElementById('transcript-count').textContent = `${chunkId} chunks`;
}

// ── Auto-scroll detection ─────────────────────────────
function initScrollDetection() {
    const body = document.getElementById('transcript-body');
    body.addEventListener('scroll', () => {
        const threshold = 60;
        const atBottom = body.scrollHeight - body.scrollTop - body.clientHeight < threshold;
        autoScroll = atBottom;

        // show/hide scroll-to-bottom button
        const btn = document.getElementById('scroll-bottom-btn');
        if (btn) btn.style.display = atBottom ? 'none' : 'flex';
    });
}

function scrollToBottom() {
    const body = document.getElementById('transcript-body');
    body.scrollTo({ top: body.scrollHeight, behavior: 'smooth' });
    autoScroll = true;
    const btn = document.getElementById('scroll-bottom-btn');
    if (btn) btn.style.display = 'none';
}

// ── Summary rendering ─────────────────────────────────
function renderFinalSummary(text, meta) {
    const el = document.getElementById('summary-content');
    el.innerHTML = parseMarkdown(text);

    const badge = document.getElementById('summary-badge');
    badge.textContent = meta.strategy || 'direct';

    toast('Final summary ready', 'success');
}

function renderProgressiveSummary(text) {
    const el = document.getElementById('progressive-content');
    const time = new Date().toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' });

    el.innerHTML = `
        <div class="progressive-tag">⟳ Updated at ${time}</div>
        ${parseMarkdown(text)}
    `;

    document.getElementById('prog-badge').textContent = `Last: ${time}`;
}

// ── Q&A rendering ─────────────────────────────────────
function renderQAAnswer(answer, question) {
    const messages = document.getElementById('qa-messages');

    // remove thinking bubble
    const thinking = document.getElementById('qa-thinking');
    if (thinking) thinking.remove();

    const answerEl = document.createElement('div');
    answerEl.className = 'qa-message qa-answer';
    answerEl.textContent = answer;
    messages.appendChild(answerEl);
    messages.scrollTop = messages.scrollHeight;

    // re-enable input
    const input = document.getElementById('qa-input');
    input.disabled = false;
    document.getElementById('qa-send').disabled = false;
    input.value = '';
    input.focus();
}

// ── Stats ─────────────────────────────────────────────
function updateStats() {
    document.getElementById('stat-chunks').textContent = chunkCount;
    document.getElementById('stat-words').textContent = wordCount;
}

// ── Start recording ───────────────────────────────────
async function startRecording() {
    if (isRecording) {
        toast('Already recording', 'error');
        return;
    }

    if (ws) { ws.close(); ws = null; }

    const source = document.getElementById('audio-source').value;
    sessionId = generateSessionId();

    try {
        stream = await _getAudioStream(source);
    } catch (err) {
        toast(`Audio access failed: ${err.message}`, 'error');
        return;
    }

    const wsUrl = `ws://${location.host}/ws/audio?session_id=${sessionId}`;
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        setStatus('connected', 'Connected');
        toast('Session started', 'success');
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleMessage(data);
        } catch (e) {
            console.error('Failed to parse message:', e);
        }
    };

    ws.onclose = () => {
        setStatus('', 'Disconnected');
        if (isRecording) {
            toast('Connection lost', 'error');
            stopRecording();
        }
    };

    ws.onerror = () => toast('WebSocket error', 'error');

    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';

    headerChunk = null;
    mediaRecorder = new MediaRecorder(stream, { mimeType });

    mediaRecorder.ondataavailable = async (event) => {
        if (event.data.size === 0) return;
        if (!ws || ws.readyState !== WebSocket.OPEN) return;

        const buffer = await event.data.arrayBuffer();

        if (headerChunk === null) {
            headerChunk = buffer.slice(0, 4096);
            ws.send(buffer);
        } else {
            const combined = new Uint8Array(headerChunk.byteLength + buffer.byteLength);
            combined.set(new Uint8Array(headerChunk), 0);
            combined.set(new Uint8Array(buffer), headerChunk.byteLength);
            ws.send(combined.buffer);
        }
    };

    mediaRecorder.start(15000);
    isRecording = true;
    autoScroll = true;
    startTimer();

    document.getElementById('btn-start').disabled = true;
    document.getElementById('btn-stop').disabled = false;
    document.getElementById('btn-summary').disabled = true;
    document.getElementById('audio-source').disabled = true;
    document.getElementById('wave').classList.add('active');
    document.getElementById('qa-input').disabled = false;
    document.getElementById('qa-send').disabled = false;
    setStatus('recording', 'Recording');

    const sourceLabel = { mic: 'Mic only', tab: 'Tab audio', both: 'Mic + Tab' }[source];
    toast(`Recording — ${sourceLabel}`, 'success');
}

// ── Get audio stream ──────────────────────────────────
async function _getAudioStream(source) {
    if (source === 'mic') {
        return await navigator.mediaDevices.getUserMedia({ audio: true });
    }

    if (source === 'tab') {
        const tabStream = await navigator.mediaDevices.getDisplayMedia({
            video: true,
            audio: { echoCancellation: false, noiseSuppression: false, sampleRate: 16000 }
        });
        tabStream.getVideoTracks().forEach(t => t.stop());
        if (tabStream.getAudioTracks().length === 0) {
            throw new Error('No tab audio captured. Check "Share tab audio" in the dialog.');
        }
        return tabStream;
    }

    if (source === 'both') {
        const [micStream, tabStream] = await Promise.all([
            navigator.mediaDevices.getUserMedia({ audio: true }),
            navigator.mediaDevices.getDisplayMedia({
                video: true,
                audio: { echoCancellation: false, noiseSuppression: false, sampleRate: 16000 }
            })
        ]);

        tabStream.getVideoTracks().forEach(t => t.stop());

        if (tabStream.getAudioTracks().length === 0) {
            toast('Tab audio not shared — using mic only', 'info');
            return micStream;
        }

        const audioContext = new AudioContext();
        const destination = audioContext.createMediaStreamDestination();
        audioContext.createMediaStreamSource(micStream).connect(destination);
        audioContext.createMediaStreamSource(tabStream).connect(destination);

        window._audioContext = audioContext;
        window._micStream = micStream;
        window._tabStream = tabStream;

        return destination.stream;
    }
}

// ── Stop recording ────────────────────────────────────
function stopRecording() {
    if (!isRecording) return;

    isRecording = false;
    headerChunk = null;

    if (window._audioContext) { window._audioContext.close(); window._audioContext = null; }
    if (window._micStream) { window._micStream.getTracks().forEach(t => t.stop()); window._micStream = null; }
    if (window._tabStream) { window._tabStream.getTracks().forEach(t => t.stop()); window._tabStream = null; }

    if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();

    setTimeout(() => {
        if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
    }, 500);

    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'stop' }));
    }

    stopTimer();

    document.getElementById('btn-start').disabled = false;
    document.getElementById('btn-stop').disabled = true;
    document.getElementById('btn-summary').disabled = false;
    document.getElementById('audio-source').disabled = false;
    document.getElementById('wave').classList.remove('active');
    document.getElementById('qa-input').disabled = false;
    document.getElementById('qa-send').disabled = false;
    setStatus('connected', 'Stopped');

    toast('Recording stopped', 'info', 4000);
}

// ── Generate summary ──────────────────────────────────
function generateSummary() {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        toast('Not connected', 'error');
        return;
    }

    ws.send(JSON.stringify({ type: 'generate_summary' }));
    document.getElementById('btn-summary').disabled = true;

    document.getElementById('summary-content').innerHTML = `
        <div class="thinking"><span></span><span></span><span></span></div>
        <p style="color:var(--muted);font-size:12px;margin-top:10px;font-family:'Instrument Serif',serif;font-style:italic;">Generating summary…</p>
    `;

    toast('Generating summary…', 'info');
}

// ── Send question ─────────────────────────────────────
function sendQuestion() {
    const input = document.getElementById('qa-input');
    const question = input.value.trim();

    if (!question) return;

    if (!ws || ws.readyState !== WebSocket.OPEN) {
        toast('Not connected', 'error');
        return;
    }

    const messages = document.getElementById('qa-messages');

    const qEl = document.createElement('div');
    qEl.className = 'qa-message qa-question';
    qEl.textContent = question;
    messages.appendChild(qEl);

    const thinking = document.createElement('div');
    thinking.className = 'qa-message qa-answer';
    thinking.id = 'qa-thinking';
    thinking.innerHTML = '<div class="thinking"><span></span><span></span><span></span></div>';
    messages.appendChild(thinking);
    messages.scrollTop = messages.scrollHeight;

    ws.send(JSON.stringify({ type: 'question', text: question }));

    input.disabled = true;
    document.getElementById('qa-send').disabled = true;
}

// ── Clear session ─────────────────────────────────────
function clearSession() {
    if (isRecording) {
        toast('Stop recording first', 'error');
        return;
    }

    document.getElementById('transcript-content').innerHTML = `
        <div class="transcript-empty">
            <div class="icon">🎙</div>
            <p>Start recording to see live transcript</p>
        </div>
    `;
    document.getElementById('summary-content').innerHTML = `
        <div class="summary-empty">
            <div class="icon">✦</div>
            <p>Summary appears here after stopping recording</p>
        </div>
    `;
    document.getElementById('progressive-content').innerHTML = `
        <div class="summary-empty">
            <div class="icon">⟳</div>
            <p>Auto-updates every 10 minutes during recording</p>
        </div>
    `;
    document.getElementById('qa-messages').innerHTML = '';
    document.getElementById('transcript-count').textContent = '0 chunks';
    document.getElementById('summary-badge').textContent = '—';
    document.getElementById('prog-badge').textContent = 'Updates every 10 min';
    document.getElementById('timer').textContent = '00:00';

    chunkCount = 0;
    wordCount = 0;
    autoScroll = true;
    updateStats();

    if (ws) ws.close();

    toast('Session cleared', 'info');
}

// ── Helpers ───────────────────────────────────────────
function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function parseMarkdown(text) {
    return text
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n\n/g, '<br>');
}

// ── Init ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initScrollDetection();
    initResizeHandle();

    // Enter key for Q&A
    document.getElementById('qa-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendQuestion();
        }
    });
});

function initResizeHandle() {
    const handle = document.getElementById('resize-handle');
    const summaryPanel = document.getElementById('summary-panel');
    const rightCol = handle.parentElement;

    let isDragging = false;
    let startY = 0;
    let startHeight = 0;

    handle.addEventListener('mousedown', (e) => {
        isDragging = true;
        startY = e.clientY;
        startHeight = summaryPanel.offsetHeight;
        document.body.style.cursor = 'ns-resize';
        document.body.style.userSelect = 'none';
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        const delta = e.clientY - startY;
        const rightColHeight = rightCol.offsetHeight;
        const newHeight = Math.min(
            Math.max(startHeight + delta, 80),        // min 80px
            rightColHeight - 120 - 6                  // max: leave 120px for Q&A
        );
        summaryPanel.style.height = newHeight + 'px';
        summaryPanel.style.flex = 'none';
    });

    document.addEventListener('mouseup', () => {
        if (!isDragging) return;
        isDragging = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    });
}