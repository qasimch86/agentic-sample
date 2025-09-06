// static/js/chat.js
(function () {
  console.info('chat.js compose-mode loaded v9');

  // ---------- tiny DOM helpers ----------
  const qs = (sel, root = document) => root.querySelector(sel);
  const chatBoxEl = () => qs('.chat-area .chat-box');
  const textareaEl = () => qs('#chat-textarea');
  const sendBtnEl = () => qs('#send-btn');
  const attachEl = () => qs('#attach-file');

  // ---------- safe markdown (used only for /api/chat fallback or debug) ----------
  function sanitizeText(text) {
    return text.replace(/!\[.*?\]\(.*?\)/g, '').replace(/<img[^>]*>/gi, '');
  }

  function normalizeLists(text) {
    text = text.replace(/([^\n])\s*([-*])\s+/g, '$1\n$2 ');
    text = text.replace(/([^\n])\s*(\d+\.)\s+/g, '$1\n$2 ');
    text = text.replace(/(\|[-:]+[-| :]*)/g, '\n$1\n');
    text = text.replace(/([^\n])(\|.*\|)/g, '$1\n$2');
    return text;
  }
  function renderMarkdown(text) {
    let safe = sanitizeText(text);
    safe = normalizeLists(safe);
    return (window.marked ? marked.parse(safe, { breaks: true, gfm: true }) : safe);
  }

  // Find the most recent rendered LLM table in the chat area
  function getLastTableHTMLFromDOM() {
    const cards = document.querySelectorAll('.chat-area .chat-box .bot-card');
    for (let i = cards.length - 1; i >= 0; i--) {
      const t = cards[i].querySelector('table.llm-table');
      if (t) return t.outerHTML;
    }
    return null;
  }

  // ---------- compose helpers (HTML artifacts) ----------
  async function callComposeAPI(userText) {
    const res = await fetch('/api/compose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_input: userText })
    });
    return res.json();
  }

  function envelopeToHTML(env) {
    let html = env.final_template || '';
    if (env.variables && Object.keys(env.variables).length) {
      for (const [k, v] of Object.entries(env.variables)) {
        html = html.replaceAll(`{${k}}`, v || '');
      }
    }
    if (env.preamble) html = `<p>${env.preamble}</p>\n` + html;
    if (env.postamble) html = html + `\n<p>${env.postamble}</p>`;
    try {
      if (window.DOMPurify) {
        html = DOMPurify.sanitize(html, {
          USE_PROFILES: { html: true },
          ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto|tel):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i
        });
      }
    } catch (e) {
      console.warn('DOMPurify not available or failed; continuing unsanitized for debug.');
    }
    return html;
  }

  async function renderMermaidIn(el) {
    if (!window.mermaid) return;
    const blocks = el.querySelectorAll('div.mermaid, code.language-mermaid, pre code.language-mermaid');
    for (const node of blocks) {
      const src = node.textContent;
      const mount = document.createElement('div');
      const pre = node.closest('pre');
      (pre ? pre : node).replaceWith(mount);
      try {
        const { svg } = await mermaid.render('mmd-' + Math.random().toString(36).slice(2), src);
        mount.innerHTML = svg;
      } catch {
        mount.textContent = 'Mermaid parse error';
      }
    }
  }

  // ---------- renderers ----------
  function appendUser(text) {
    const box = chatBoxEl();
    if (!box) return;
    const card = document.createElement('div');
    card.className = 'chat-card user-card';
    card.innerHTML = `<div class="chat-header">User</div><p>${text}</p>`;
    box.appendChild(card);
    box.scrollTop = box.scrollHeight;
  }

  async function appendBotMarkdown(text) {
    const box = chatBoxEl();
    if (!box) return;
    const card = document.createElement('div');
    card.className = 'chat-card bot-card';
    card.innerHTML = `<div class="chat-header">Bot</div>${renderMarkdown(text)}`;
    box.appendChild(card);
    if (typeof renderMathInElement === 'function') {
      renderMathInElement(card, {
        delimiters: [
          { left: '$$', right: '$$', display: true },
          { left: '$', right: '$', display: false }
        ]
      });
    }
    await renderMermaidIn(card);
    box.scrollTop = box.scrollHeight;
  }

  async function appendBotEnvelopeHTML(env) {
    const box = chatBoxEl();
    if (!box) return;
    const card = document.createElement('div');
    card.className = 'chat-card bot-card';
    card.innerHTML = `<div class="chat-header">Bot</div>${envelopeToHTML(env)}`;
    box.appendChild(card);
    if (typeof renderMathInElement === 'function') {
      renderMathInElement(card, {
        delimiters: [
          { left: '$$', right: '$$', display: true },
          { left: '$', right: '$', display: false }
        ]
      });
    }
    await renderMermaidIn(card);
    box.scrollTop = box.scrollHeight;
  }

  // ---------- send flow (compose-first; no silent fallback) ----------
  // --- REPLACE your current handleSend() with this ---
  async function handleSend() {
    const ta = document.querySelector('#chat-textarea');
    if (!ta) return;
    const msg = (ta.value || '').trim();
    if (!msg) return;

    // Store user message -> chat_sessions re-renders the chat box
    window.chatSessions?.pushMessage?.('user', msg);

    ta.value = '';
    const cc = document.querySelector('#char-counter');
    if (cc) {
      const MAX = 3000;
      cc.textContent = `${Math.max(0, MAX - (ta?.value?.length || 0))} characters remaining`;
    }

    try {
      const context = { last_table: getLastTableHTMLFromDOM() };
      const env = await fetch('/api/compose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_input: msg, context })
      }).then(r => r.json());

      console.log('[compose] mode =', env.mode, env);

      if (env.mode === 'html') {
        // Build the final HTML (substitute placeholders), then store exactly once
        let html = env.final_template || '';
        if (env.variables) {
          for (const [k, v] of Object.entries(env.variables)) {
            html = html.replaceAll(`{${k}}`, v || '');
          }
        }
        if (env.preamble) html = `<p>${env.preamble}</p>\n` + html;
        if (env.postamble) html = html + `\n<p>${env.postamble}</p>`;
        if (window.DOMPurify) {
          html = DOMPurify.sanitize(html, {
            USE_PROFILES: { html: true },
            ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto|tel):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i
          });
        }
        window.chatSessions?.pushMessage?.('bot', html, { html: true });
        return;
      }

      if (env.mode === 'markdown') {
        const md = [env.preamble || '', env.final_template || '', env.postamble || '']
          .filter(Boolean).join('\n\n');
        window.chatSessions?.pushMessage?.('bot', md);
        return;
      }

      if (env.mode === 'blocked') {
        window.chatSessions?.pushMessage?.('bot', env.postamble || 'Request denied.');
        return;
      }

      // Unexpected shape: show it plainly to debug
      window.chatSessions?.pushMessage?.('bot',
        'Compose returned unexpected mode — raw JSON:\n```json\n' +
        JSON.stringify(env, null, 2) + '\n```'
      );

    } catch (e) {
      console.warn('compose error → fallback to /api/chat', e);
      try {
        const data = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: msg })
        }).then(r => r.json());
        window.chatSessions?.pushMessage?.('bot', data.reply || 'Sorry, the assistant is unavailable. Please try again later.');
      } catch {
        window.chatSessions?.pushMessage?.('bot', 'Sorry, the assistant is unavailable. Please try again later.');
      }
    }
  }


  // ---------- binding (safe; never blocks load) ----------
  function updateCharCounter() {
    const ta = textareaEl();
    const cc = qs('#char-counter');
    const MAX = 3000;
    const left = Math.max(0, MAX - (ta?.value?.length || 0));
    if (cc) cc.textContent = `${left} characters remaining`;
  }

  let sendBound = false;
  function tryBind() {
    const ta = textareaEl();
    const btn = sendBtnEl();
    const box = chatBoxEl();
    if (!ta || !btn || !box) return false;

    if (!sendBound) {
      btn.addEventListener('click', handleSend);
      ta.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          handleSend();
        }
      });
      const att = attachEl();
      if (att && typeof window.showAttachedFile === 'function') {
        att.addEventListener('change', window.showAttachedFile);
      }
      sendBound = true;
      console.info('chat.js: send bindings attached');
    }
    updateCharCounter();
    return true;
  }

  // Poll for the chat UI for up to 10s; do not block the page if components load late
  document.addEventListener('DOMContentLoaded', () => {
    let attempts = 0;
    const timer = setInterval(() => {
      attempts++;
      if (tryBind()) { clearInterval(timer); return; }
      if (attempts >= 100) { // 100 * 100ms = 10s
        clearInterval(timer);
        console.warn('chat.js: chat UI not found after 10s; bindings not attached.');
      }
    }, 100);
  });
})();