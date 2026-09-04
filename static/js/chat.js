document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('chat-form');
  const msg = document.getElementById('msg');
  const chatbox = document.getElementById('chatbox');
  const promptButtons = document.querySelectorAll('.prompt-btn');

  if (!form || !msg || !chatbox) {
    return;
  }

  appendMessage('ai', 'I am here, listening. Tell me what your heart wants to say.');

  promptButtons.forEach((button) => {
    button.addEventListener('click', () => {
      msg.value = button.dataset.prompt || '';
      msg.focus();
    });
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = msg.value.trim();
    if (!text) return;

    appendMessage('user', text);
    msg.value = '';

    const typing = appendMessage('ai', 'The companion is thinking...', true);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
      });

      if (!res.ok) {
        throw new Error('Bad response');
      }

      const j = await res.json();
      typing.textContent = j.reply || '...';
      typing.classList.remove('typing');
    } catch (err) {
      typing.textContent = 'The companion is taking a quiet moment. Please try again.';
      typing.classList.remove('typing');
    }
  });

  function appendMessage(side, text, isTyping = false) {
    const el = document.createElement('div');
    el.className = `chat-message ${side}`;
    if (isTyping) {
      el.classList.add('typing');
    }
    el.textContent = text;
    chatbox.appendChild(el);
    chatbox.scrollTop = chatbox.scrollHeight;
    return el;
  }
});
