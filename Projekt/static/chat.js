const socket = io();

const chatbox = document.getElementById('chatbox');
const usernameInput = document.getElementById('username');
const messageInput = document.getElementById('message');

// Nachricht senden
function sendMessage() {
    const username = usernameInput.value.trim();
    const message = messageInput.value.trim();

    if (!username || !message) {
        alert("Bitte gib sowohl deinen Namen als auch eine Nachricht ein.");
        return;
    }

    // Nur Benutzername und Nachricht senden
    socket.emit('message', { username, message });

    // Eingabefeld leeren
    messageInput.value = '';
}

// Nachricht im Chat anzeigen
function addMessage(data) {
    const newMessageDiv = document.createElement('div');
    newMessageDiv.classList.add('message');
    newMessageDiv.innerHTML = `<strong>${data.username}</strong> [${data.date} | ${data.time}]: ${data.message}`;
    chatbox.appendChild(newMessageDiv);
    chatbox.scrollTop = chatbox.scrollHeight;
}

function scrollToBottom{
    chatbox.scrollTop = chatbox.scrollHeight;
}
// Nachrichten vom Server empfangen
socket.on('message', function(data) {
    addMessage(data);
});

// Enter-Taste zum Senden
messageInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
        sendMessage();
        e.preventDefault();
    }
});
