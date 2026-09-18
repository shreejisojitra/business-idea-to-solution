/**
 * Business Transformation AI — Embeddable Public Chatbot Widget
 * Usage: <script src="https://your-domain/widget/chatbot.js"
 *                 data-chatbot-id="YOUR_CHATBOT_ID"
 *                 data-api-base="https://your-domain"></script>
 */
(function () {
  'use strict';

  const script = document.currentScript ||
    document.querySelector('script[data-chatbot-id]');

  const CHATBOT_ID = script && script.getAttribute('data-chatbot-id');
  const API_BASE = (script && script.getAttribute('data-api-base')) ||
    window.location.origin;

  if (!CHATBOT_ID) {
    console.error('[ChatbotWidget] data-chatbot-id is required.');
    return;
  }

  const API = {
    config: () =>
      fetch(`${API_BASE}/api/public/chatbots/${CHATBOT_ID}/config`)
        .then(r => r.ok ? r.json() : Promise.reject(r)),
    session: () =>
      fetch(`${API_BASE}/api/public/chatbots/${CHATBOT_ID}/session`, { method: 'POST' })
        .then(r => r.ok ? r.json() : Promise.reject(r)),
    chat: (sessionId, message) =>
      fetch(`${API_BASE}/api/public/chatbots/${CHATBOT_ID}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message }),
      }).then(r => r.ok ? r.json() : Promise.reject(r)),
  };

  // ── Styles ──────────────────────────────────────────────────────────────────
  const css = `
    #btai-widget-btn {
      position: fixed; bottom: 24px; right: 24px; z-index: 9998;
      width: 56px; height: 56px; border-radius: 50%;
      background: #2563eb; color: #fff; border: none; cursor: pointer;
      box-shadow: 0 4px 14px rgba(0,0,0,.25); font-size: 24px;
      display: flex; align-items: center; justify-content: center;
      transition: background .2s;
    }
    #btai-widget-btn:hover { background: #1d4ed8; }
    #btai-widget-box {
      position: fixed; bottom: 92px; right: 24px; z-index: 9999;
      width: 360px; max-height: 520px;
      background: #fff; border-radius: 12px;
      box-shadow: 0 8px 32px rgba(0,0,0,.18);
      display: flex; flex-direction: column; overflow: hidden;
      font-family: system-ui, sans-serif; font-size: 14px;
    }
    #btai-widget-box.btai-hidden { display: none; }
    #btai-header {
      background: #2563eb; color: #fff; padding: 14px 16px;
      font-weight: 600; font-size: 15px; display: flex;
      align-items: center; justify-content: space-between;
    }
    #btai-header button {
      background: none; border: none; color: #fff; cursor: pointer;
      font-size: 18px; line-height: 1; padding: 0;
    }
    #btai-messages {
      flex: 1; overflow-y: auto; padding: 12px;
      display: flex; flex-direction: column; gap: 8px;
    }
    .btai-msg {
      max-width: 82%; padding: 8px 12px; border-radius: 10px;
      line-height: 1.45; word-break: break-word;
    }
    .btai-msg.user {
      align-self: flex-end; background: #2563eb; color: #fff;
      border-bottom-right-radius: 3px;
    }
    .btai-msg.assistant {
      align-self: flex-start; background: #f1f5f9; color: #1e293b;
      border-bottom-left-radius: 3px;
    }
    .btai-msg.typing { color: #94a3b8; font-style: italic; }
    #btai-input-row {
      display: flex; gap: 8px; padding: 10px 12px;
      border-top: 1px solid #e2e8f0;
    }
    #btai-input {
      flex: 1; border: 1px solid #cbd5e1; border-radius: 8px;
      padding: 8px 10px; font-size: 14px; outline: none;
      resize: none; font-family: inherit;
    }
    #btai-input:focus { border-color: #2563eb; }
    #btai-send {
      background: #2563eb; color: #fff; border: none;
      border-radius: 8px; padding: 8px 14px; cursor: pointer;
      font-size: 14px; font-weight: 600; transition: background .2s;
    }
    #btai-send:hover { background: #1d4ed8; }
    #btai-send:disabled { background: #93c5fd; cursor: not-allowed; }
    #btai-error {
      color: #dc2626; font-size: 12px; padding: 4px 12px 8px;
      display: none;
    }
  `;

  // ── DOM ─────────────────────────────────────────────────────────────────────
  function inject() {
    const style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);

    const btn = document.createElement('button');
    btn.id = 'btai-widget-btn';
    btn.title = 'Chat with us';
    btn.innerHTML = '&#128172;';
    document.body.appendChild(btn);

    const box = document.createElement('div');
    box.id = 'btai-widget-box';
    box.classList.add('btai-hidden');
    box.innerHTML = `
      <div id="btai-header">
        <span id="btai-title">Chat</span>
        <button id="btai-close" title="Close">&#x2715;</button>
      </div>
      <div id="btai-messages"></div>
      <div id="btai-error"></div>
      <div id="btai-input-row">
        <textarea id="btai-input" rows="1" placeholder="Type a message…"></textarea>
        <button id="btai-send">Send</button>
      </div>
    `;
    document.body.appendChild(box);

    return {
      btn,
      box,
      title: box.querySelector('#btai-title'),
      messages: box.querySelector('#btai-messages'),
      input: box.querySelector('#btai-input'),
      send: box.querySelector('#btai-send'),
      close: box.querySelector('#btai-close'),
      error: box.querySelector('#btai-error'),
    };
  }

  // ── Widget logic ─────────────────────────────────────────────────────────────
  function addMessage(container, role, text) {
    const el = document.createElement('div');
    el.className = `btai-msg ${role}`;
    el.textContent = text;
    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
    return el;
  }

  function showError(el, msg) {
    el.textContent = msg;
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 4000);
  }

  async function init() {
    const ui = inject();
    let sessionId = null;
    let open = false;

    // Load config
    let config;
    try {
      config = await API.config();
      ui.title.textContent = config.name || 'Chat';
    } catch (_) {
      ui.title.textContent = 'Chat';
    }

    function toggle() {
      open = !open;
      ui.box.classList.toggle('btai-hidden', !open);
      if (open && !sessionId) {
        // Start session and show welcome on first open
        API.session()
          .then(s => {
            sessionId = s.session_id;
            if (config && config.welcome_message) {
              addMessage(ui.messages, 'assistant', config.welcome_message);
            }
          })
          .catch(() => showError(ui.error, 'Could not connect to chatbot.'));
      }
      if (open) ui.input.focus();
    }

    ui.btn.addEventListener('click', toggle);
    ui.close.addEventListener('click', toggle);

    async function sendMessage() {
      const text = ui.input.value.trim();
      if (!text || ui.send.disabled) return;

      ui.input.value = '';
      ui.send.disabled = true;
      addMessage(ui.messages, 'user', text);
      const typing = addMessage(ui.messages, 'assistant typing', 'Thinking…');

      try {
        if (!sessionId) {
          const s = await API.session();
          sessionId = s.session_id;
        }
        const res = await API.chat(sessionId, text);
        typing.remove();
        addMessage(ui.messages, 'assistant', res.message);
      } catch (_) {
        typing.remove();
        showError(ui.error, 'Failed to get a response. Please try again.');
      } finally {
        ui.send.disabled = false;
        ui.input.focus();
      }
    }

    ui.send.addEventListener('click', sendMessage);
    ui.input.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
