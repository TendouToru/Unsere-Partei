const socket = io();

// Aktive Nutzer
socket.on('update_active_users', (data) => {
    const el = document.getElementById('active-users');
    if (el && el.textContent !== data.count.toString()) {
        el.textContent = data.count;
        animateUpdate(el);
    }
});


// Initiale Stats laden + regelmäßig aktualisieren

function fetchStats() {
    fetch('/api/stats')
        .then(res => res.json())
        .then(data => {
            const mapping = {
                'today-messages': data.messages_today,
                'next-event': data.next_event
            };
            for (const [id, newValue] of Object.entries(mapping)) {
                const el = document.getElementById(id);
                if (el && el.textContent !== newValue.toString()) {
                    el.textContent = newValue;
                    animateUpdate(el);
                }
            }
        });
}



// Alle 30 Sekunden aktualisieren
fetchStats();
setInterval(fetchStats, 30000);

// Highlight-Animation bei Änderungen
function animateUpdate(element) {
    element.classList.add('updated');
    setTimeout(() => element.classList.remove('updated'), 500);
}

// In fetchStats():
document.querySelectorAll('.live-stats span').forEach(el => {
    const oldValue = el.textContent;
    const newValue = data[el.id];
    if (oldValue !== newValue.toString()) {
        animateUpdate(el);
    }
});