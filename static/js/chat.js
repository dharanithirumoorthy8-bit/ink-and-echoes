document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('chat-form');
  const msg = document.getElementById('msg');
  const chatbox = document.getElementById('chatbox');
  const promptButtons = document.querySelectorAll('.prompt-btn');

  if (!form || !msg || !chatbox) {
    return;
  }

  appendMessage(
    'ai',
    "Heyy 🌙 I'm here. What's on your mind?"
  );

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

    const typing = appendMessage(
      'ai',
      'The companion is thinking...',
      true
    );

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message: text
        })
      });

      const j = await res.json();

      if (!res.ok || !j.success) {
        throw new Error(
          j.response || 'Bad response'
        );
      }

      // IMPORTANT:
      // ai.py returns "response", NOT "reply"
      typing.textContent =
        j.response || 'I am here with you. 🌙';

      typing.classList.remove('typing');

    } catch (err) {

      console.error('AI Companion error:', err);

      typing.textContent =
        'The companion is taking a quiet moment. Please try again. 🌙';

      typing.classList.remove('typing');
    }

    chatbox.scrollTop = chatbox.scrollHeight;
  });

  function appendMessage(
    side,
    text,
    isTyping = false
  ) {
    const el = document.createElement('div');

    el.className = `chat-message ${side}`;

    if (isTyping) {
      el.classList.add('typing');
    }

    el.textContent = text;

    chatbox.appendChild(el);

    chatbox.scrollTop =
      chatbox.scrollHeight;

    return el;
  }
});
