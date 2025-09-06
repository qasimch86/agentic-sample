function uploadFiles() {
    const fileInput = document.getElementById('file-input');
    const files = fileInput.files;
    const status = document.getElementById('file-upload-status');
    const fileList = document.getElementById('file-list');
    const maxFileSize = 10 * 1024 * 1024; // 10 MB
    const maxFiles = 10;
    let totalFiles = files.length;

    if (totalFiles === 0) {
        status.textContent = 'Select file(s) to upload.';
        return;
    }

    if (totalFiles > maxFiles) {
        status.textContent = `You can upload a maximum of ${maxFiles} files.`;
        return;
    }

    fileList.innerHTML = ''; // Clear the list before adding new files

    for (let i = 0; i < totalFiles; i++) {
        if (files[i].size > maxFileSize) {
            status.textContent = `File ${files[i].name} exceeds the 10 MB size limit.`;
            return;
        }

        if (files[i].type !== 'application/pdf') {
            status.textContent = `File ${files[i].name} is not a PDF.`;
            return;
        }

        const listItem = document.createElement('li');
        const fileName = document.createElement('span');
        fileName.textContent = files[i].name.length > 20 ? files[i].name.substring(0, 20) + '...' : files[i].name;
        const removeButton = document.createElement('button');
        removeButton.textContent = '✖';
        removeButton.onclick = () => {
            listItem.remove();
            fileInput.value = ''; // Clear the file input
        };

        listItem.appendChild(fileName);
        listItem.appendChild(removeButton);
        fileList.appendChild(listItem);
    }

    status.textContent = 'Files uploaded successfully!';
}

function showAttachedFile() {
    const attachFileInput = document.getElementById('attach-file');
    const attachedFileDiv = document.getElementById('attached-file');
    const file = attachFileInput.files[0];

    if (file) {
        attachedFileDiv.innerHTML = `Attached: ${file.name} <button onclick="removeAttachedFile()">✖</button>`;
        attachedFileDiv.style.display = 'block';
    } else {
        attachedFileDiv.style.display = 'none';
    }
}

function removeAttachedFile() {
    const attachFileInput = document.getElementById('attach-file');
    const attachedFileDiv = document.getElementById('attached-file');
    attachFileInput.value = ''; // Clear the file input
    attachedFileDiv.style.display = 'none';
}

function setInitialLogoState() {
    const body = document.body;
    const lightLogo = document.querySelector('.light-logo');
    const darkLogo = document.querySelector('.dark-logo');

    if (body.classList.contains('dark-mode')) {
        if (lightLogo) lightLogo.style.display = 'none';
        if (darkLogo) darkLogo.style.display = 'block';
    } else {
        if (lightLogo) lightLogo.style.display = 'block';
        if (darkLogo) darkLogo.style.display = 'none';
    }
}

function toggleDarkMode() {
    const body = document.body;
    const header = document.querySelector('header');
    const recentChats = document.querySelector('.recent-chats');
    const chatArea = document.querySelector('.chat-area');
    const rightSidebar = document.querySelector('.right-sidebar');
    const fileList = document.getElementById('file-list');
    const attachedFileDiv = document.getElementById('attached-file');
    const recentChatsItems = document.querySelectorAll('.recent-chats li');
    const lightLogo = document.querySelector('.light-logo');
    const darkLogo = document.querySelector('.dark-logo');

    body.classList.toggle('dark-mode');
    body.classList.toggle('light-mode');
    header.classList.toggle('dark-mode');
    header.classList.toggle('light-mode');
    recentChats.classList.toggle('dark-mode');
    recentChats.classList.toggle('light-mode');
    chatArea.classList.toggle('dark-mode');
    chatArea.classList.toggle('light-mode');
    rightSidebar.classList.toggle('dark-mode');
    rightSidebar.classList.toggle('light-mode');
    fileList.classList.toggle('dark-mode');
    fileList.classList.toggle('light-mode');
    attachedFileDiv.classList.toggle('dark-mode');
    attachedFileDiv.classList.toggle('light-mode');

    recentChatsItems.forEach(item => {
        item.classList.toggle('dark-mode');
        item.classList.toggle('light-mode');
    });

    // Ensure only one logo is displayed
    if (body.classList.contains('dark-mode')) {
        if (lightLogo) lightLogo.style.display = 'none';
        if (darkLogo) darkLogo.style.display = 'block';
    } else {
        if (lightLogo) lightLogo.style.display = 'block';
        if (darkLogo) darkLogo.style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const textarea = document.getElementById('chat-textarea');
    const charCounter = document.getElementById('char-counter');
    if (textarea && charCounter) {
        const maxChars = parseInt(textarea.getAttribute('maxlength'), 10);
        textarea.addEventListener('input', () => {
            // Update character counter
            const remainingChars = maxChars - textarea.value.length;
            charCounter.textContent = `${remainingChars} characters remaining`;

            // Auto-resize textarea
            textarea.style.height = 'auto'; // Reset height
            textarea.style.height = `${textarea.scrollHeight}px`; // Set new height
        });

        // Initial auto-resize
        textarea.style.height = `${textarea.scrollHeight}px`;
    }
});

document.addEventListener('DOMContentLoaded', setInitialLogoState);
document.addEventListener('DOMContentLoaded', () => {
    const attachFileInput = document.getElementById('attach-file');
    if (attachFileInput) {
        removeAttachedFile();
    }
});