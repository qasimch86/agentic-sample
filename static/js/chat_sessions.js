// static/js/chat_sessions.js
// Manages recent chats + message storage (localStorage) and renders the chat box.

(function () {
  const CHAT_STORAGE_KEY = 'recentChats';
  const CHAT_MSG_KEY_PREFIX = 'chatSession_';
  let currentSessionId = null;

  // ---------- storage helpers ----------
  const getChats = () => JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY) || '[]');
  const saveChats = (chats) => localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(chats));
  const getMsgs = (sid) => JSON.parse(localStorage.getItem(CHAT_MSG_KEY_PREFIX + sid) || '[]');
  const saveMsgs = (sid, msgs) => localStorage.setItem(CHAT_MSG_KEY_PREFIX + sid, JSON.stringify(msgs));

  // Ensure at least one chat exists on first run
  function ensureFirstChat() {
    let chats = getChats();
    if (!Array.isArray(chats) || chats.length === 0) {
      const sessionId = 'chat_' + Date.now() + '_' + Math.floor(Math.random() * 10000);
      chats = [{ name: 'New chat', sessionId }];
      saveChats(chats);
      saveMsgs(sessionId, []);
      currentSessionId = sessionId;
    }
    if (!currentSessionId) currentSessionId = chats[0].sessionId;
  }

  // ---------- DOM helpers ----------
  function chatListContainer() {
    const container = document.getElementById('recent-chats') || document.querySelector('.recent-chats');
    if (!container) return null;
    let ul = container.querySelector('#chat-list');
    if (!ul) {
      ul = container.querySelector('ul');
      if (!ul) {
        ul = document.createElement('ul');
        ul.id = 'chat-list';
        container.appendChild(ul);
      } else {
        ul.id = 'chat-list';
      }
    }
    return ul;
  }

  function chatBoxEl() {
    return document.querySelector('.chat-area .chat-box');
  }

  // ---------- UI renderers ----------
  function loadChats() {
    const ul = chatListContainer();
    if (!ul) return; // sidebar not mounted yet
    const chats = getChats();
    ul.innerHTML = '';
    chats.forEach((chat, idx) => {
      const li = document.createElement('li');
      // derive a short preview from the first user message
      const msgs = getMsgs(chat.sessionId);
      let preview = '';
      for (const m of msgs) {
        if (m.role === 'user' && m.content) {
          const words = String(m.content).trim().split(/\s+/);
          preview = words.slice(0, 2).join(' ') + (words.length > 2 ? '…' : '');
          break;
        }
      }
      const displayName = (chat.name && chat.name.trim()) || preview || `Chat ${idx + 1}`;
      const shownName = displayName.length > 28 ? displayName.slice(0, 25) + '…' : displayName;

      li.className = (chat.sessionId === currentSessionId) ? 'active-chat' : '';
      li.dataset.sessionId = chat.sessionId;
      li.innerHTML = `<span class="chat-name">${shownName}</span>`;

      // delete button (optional)
      const delBtn = document.createElement('button');
      delBtn.className = 'delete-chat-btn';
      delBtn.title = 'Delete chat';
      delBtn.textContent = '×';
      delBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        deleteChat(chat.sessionId);
      });
      li.appendChild(delBtn);

      li.addEventListener('click', () => selectChat(chat.sessionId));
      ul.appendChild(li);
    });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (m) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  }

  function renderMessageContent(msg) {
    // If bot content marked as HTML, sanitize & return as HTML
    if (msg.role === 'bot' && msg.html) {
      let html = String(msg.content || '');
      if (window.DOMPurify) {
        html = DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
      }
      return { html: true, body: html };
    }
    // Otherwise: Markdown if available, else plain text
    if (window.marked) {
      const safe = String(msg.content || '');
      const body = marked.parse(safe, { breaks: true, gfm: true });
      return { html: true, body };
    }
    return { html: false, body: escapeHtml(msg.content || '') };
  }

  async function renderChatBox() {
    const box = chatBoxEl();
    if (!box || !currentSessionId) return;
    const msgs = getMsgs(currentSessionId);
    box.innerHTML = '';
    for (const m of msgs) {
      const card = document.createElement('div');
      card.className = 'chat-card ' + (m.role === 'user' ? 'user-card' : 'bot-card');
      const rendered = renderMessageContent(m);
      if (rendered.html) {
        card.innerHTML = `<div class="chat-header">${m.role === 'user' ? 'User' : 'Bot'}</div>${rendered.body}`;
      } else {
        card.innerHTML = `<div class="chat-header">${m.role === 'user' ? 'User' : 'Bot'}</div><p>${rendered.body}</p>`;
      }
      box.appendChild(card);
    }
    // Mermaid & KaTeX pass (optional)
    if (window.mermaid) {
      const codes = box.querySelectorAll('div.mermaid, code.language-mermaid, pre code.language-mermaid');
      for (const node of codes) {
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
    if (typeof renderMathInElement === 'function') {
      renderMathInElement(box, {
        delimiters: [
          { left: '$$', right: '$$', display: true },
          { left: '$', right: '$', display: false }
        ]
      });
    }
    box.scrollTop = box.scrollHeight;
  }

  // ---------- actions ----------
  function addChat(name = 'New chat') {
    const chats = getChats();
    const sessionId = 'chat_' + Date.now() + '_' + Math.floor(Math.random() * 10000);
    chats.push({ name, sessionId });
    saveChats(chats);
    saveMsgs(sessionId, []);
    currentSessionId = sessionId;
    loadChats();
    renderChatBox();
    return sessionId;
  }

  function deleteChat(sessionId) {
    let chats = getChats().filter(c => c.sessionId !== sessionId);
    saveChats(chats);
    localStorage.removeItem(CHAT_MSG_KEY_PREFIX + sessionId);
    if (currentSessionId === sessionId) {
      if (chats.length) currentSessionId = chats[0].sessionId;
      else {
        // Create a new one so UI is never empty
        ensureFirstChat();
      }
    }
    loadChats();
    renderChatBox();
  }

  function selectChat(sessionId) {
    currentSessionId = sessionId;
    loadChats();
    renderChatBox();
  }

  // Public API for other scripts (e.g., chat.js)
  window.chatSessions = {
    addChat,
    selectChat,
    getCurrentSessionId: () => currentSessionId,
    pushMessage(role, content, opts = {}) {
      ensureFirstChat();
      const sid = currentSessionId;
      const msgs = getMsgs(sid);
      msgs.push({ role, content, html: !!opts.html });
      saveMsgs(sid, msgs);
      // If first user message, optionally set a better chat name later (left simple here)
      renderChatBox();
      loadChats();
    }
  };

  // ---------- bootstrap ----------
  document.addEventListener('DOMContentLoaded', () => {
    // Wait for components to mount (sidebar + chat area) then boot
    let tries = 0;
    const t = setInterval(() => {
      const ready = chatListContainer() && chatBoxEl();
      if (ready) {
        clearInterval(t);
        ensureFirstChat();
        loadChats();
        renderChatBox();

        // Hook "Add chat" button if present
        const addBtn = document.getElementById('add-chat-btn');
        if (addBtn) addBtn.addEventListener('click', () => addChat());
      } else if (++tries > 100) {
        clearInterval(t);
        // Still ensure storage has a chat for future renders
        ensureFirstChat();
      }
    }, 100);
  });
})();
