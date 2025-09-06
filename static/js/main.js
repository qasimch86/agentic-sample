// main.js - Loads HTML components into index.html

function loadComponent(id, url) {
    return fetch(url)
        .then(res => res.text())
        .then(html => {
            document.getElementById(id).innerHTML = html;
        });
}

document.addEventListener('DOMContentLoaded', function() {
    Promise.all([
        loadComponent('header', '/templates/components/header.html'),
        loadComponent('recent-chats', '/templates/components/recent-chats.html'),
        loadComponent('chat-area', '/templates/components/chat-area.html'),
        loadComponent('right-sidebar', '/templates/components/right-sidebar.html')
    ]).then(() => {
        // Re-initialize UI logic after all components are loaded
        if (typeof setInitialLogoState === 'function') setInitialLogoState();
        // Add event listener for dark mode toggle
        const toggleBtn = document.getElementById('toggle-dark-btn');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', function() {
                if (typeof toggleDarkMode === 'function') toggleDarkMode();
            });
        }
        // Re-initialize chat and recent-chats logic
        if (typeof loadChats === 'function') loadChats();
        if (typeof renderChatBox === 'function') renderChatBox();
        // If chat.js has its own init, call it here
        if (typeof window.initChat === 'function') window.initChat();
    // Ensure chat session event listeners are attached
    if (typeof window.initChatSessionEvents === 'function') window.initChatSessionEvents();
    });
});
