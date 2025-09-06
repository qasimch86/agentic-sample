// static/js/chat_sessions.js
// Purpose: manage recent chats sidebar + localStorage only.
// IMPORTANT: This file does NOT talk to the backend and does NOT handle sending.
// The compose/chat pipeline lives in static/js/chat.js.

const CHAT_STORAGE_KEY = 'recentChats';
const CHAT_MSG_KEY_PREFIX = 'chatSession_';
let currentSessionId = null;

// ---- Utils ----
function _listEl() {
  // Try several selectors so it works with your component layout
  return document.querySelector('#chat-list, #recent-chats ul, .recent-chats ul');
}
function _chatBoxEl() {
  return document.querySelector('.chat-area .chat-box');
}

// ---- Sidebar load/render ----
function loadChats() {
  const ul = _listEl();
  if (!ul) {
    console.warn('chat_sessions: chat list container not found yet.');
    return;
  }
  ul.innerHTML = '';

  const chats = JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY) || '[]');
  chats.forEach((chat, idx) => {
    const li = document.createElement('li');

    // Preview: first two words of first user message
    const msgs = JSON.parse(localStorage.getItem(CHAT_MSG_KEY_PREFIX + chat.sessionId) || '[]');
    let fallbackPreview = '';
    for (let m of msgs) {
      if (m.role === 'user' && m.content) {
        const words = String(m.content).split(/\s+/);
        fallbackPreview = words.slice(0, 2).join(' ');
        if (words.length > 2) fallbackPreview += '...';
        break;
      }
    }

    // Use stored topic name if present
    let displayName = (chat.name && chat.name.trim()) ? chat.name : fallbackPreview || `Chat ${idx+1}`;
    let shownName = displayName.length > 28 ? displayName.slice(0, 25) + '...' : displayName;

    li.innerHTML = `<span class="chat-name">${shownName}</span>`;
    li.setAttribute('title', displayName);
    li.dataset.sessionId = chat.sessionId;
    if (chat.sessionId === currentSessionId) li.classList.add('active-chat');

    const delBtn = document.createElement('button');
    delBtn.className = 'delete-chat-btn';
    delBtn.title = 'Delete chat';
    delBtn.textContent = '×';
    delBtn.onclick = function (e) {
      e.stopPropagation();
      deleteChat(chat.sessionId);
    };
    li.appendChild(delBtn);

    li.onclick = function () {
      selectChat(chat.sessionId);
    };

    ul.appendChild(li);
  });
}

function saveChats(chats) {
  localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(chats));
}

// ---- Session CRUD ----
function addChat() {
  const chats = JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY) || '[]');
  const sessionId = 'chat_' + Date.now() + '_' + Math.floor(Math.random() * 10000);
  chats.push({ name: '', sessionId });
  saveChats(chats);
  localStorage.setItem(CHAT_MSG_KEY_PREFIX + sessionId, JSON.stringify([]));
  selectChat(sessionId);
}

function deleteChat(sessionId) {
  let chats = JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY) || '[]');
  chats = chats.filter(chat => chat.sessionId !== sessionId);
  saveChats(chats);
  localStorage.removeItem(CHAT_MSG_KEY_PREFIX + sessionId);
  if (currentSessionId === sessionId) {
    currentSessionId = null;
    clearChatBox();
    if (chats.length) selectChat(chats[0].sessionId);
    else loadChats();
  } else {
    loadChats();
  }
}

function selectChat(sessionId) {
  currentSessionId = sessionId;
  loadChats();
  renderChatBox();
}

// ---- Chat area (render from localStorage ONLY, no backend calls here) ----
function renderChatBox() {
  const chatBox = _chatBoxEl();
  if (!chatBox) return;
  chatBox.innerHTML = '';

  if (!currentSessionId) return;
  const msgs = JSON.parse(localStorage.getItem(CHAT_MSG_KEY_PREFIX + currentSessionId) || '[]');
  msgs.forEach(m => {
    const card = document.createElement('div');
    card.className = 'chat-card ' + (m.role === 'user' ? 'user-card' : 'bot-card');
    const header = `<div class="chat-header">${m.role === 'user' ? 'User' : 'Bot'}</div>`;
    // NOTE: Bot messages may contain HTML from /api/compose; do not escape them.
    const body = (m.role === 'bot_html')
      ? m.content
      : `<p>${escapeHtml(m.content)}</p>`;
    card.innerHTML = header + body;
    chatBox.appendChild(card);
  });
  chatBox.scrollTop = chatBox.scrollHeight;
}

function clearChatBox() {
  const chatBox = _chatBoxEl();
  if (chatBox) chatBox.innerHTML = '';
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, function (m) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
  });
}

// ---- Public helpers used from chat.js ----
function pushMessage(role, content, { html = false } = {}) {
  if (!currentSessionId) return;
  const key = CHAT_MSG_KEY_PREFIX + currentSessionId;
  const msgs = JSON.parse(localStorage.getItem(key) || '[]');
  msgs.push({ role: html ? 'bot_html' : role, content });
  localStorage.setItem(key, JSON.stringify(msgs));
  renderChatBox();
  loadChats();
}

function setChatName(name) {
  if (!currentSessionId) return;
  const chats = JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY) || '[]');
  const idx = chats.findIndex(c => c.sessionId === currentSessionId);
  if (idx !== -1) {
    chats[idx].name = name;
    saveChats(chats);
    loadChats();
  }
}

function initChatSessionEvents() {
  // Only bind "add chat" here. DO NOT attach send button or call backend from this file.
  const addChatBtn = document.getElementById('add-chat-btn');
  if (addChatBtn) addChatBtn.addEventListener('click', addChat);
}

// ---- Bootstrap ----
document.addEventListener('DOMContentLoaded', function () {
  // Wait for components to load (recent-chats might be injected later)
  const tryInit = () => {
    loadChats();
    const chats = JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY) || '[]');
    if (!currentSessionId && chats.length) selectChat(chats[0].sessionId);
    initChatSessionEvents();
  };

  // If the list isn't present yet, observe until it is.
  if (_listEl()) {
    tryInit();
  } else {
    const obs = new MutationObserver(() => {
      if (_listEl()) {
        tryInit();
        obs.disconnect();
      }
    });
    obs.observe(document.body, { childList: true, subtree: true });
  }
});

// Expose helpers for chat.js
window.chatSessions = {
  addChat, deleteChat, selectChat, loadChats,
  pushMessage, setChatName
};
