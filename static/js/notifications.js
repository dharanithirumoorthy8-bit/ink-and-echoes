(function () {
  const button = document.querySelector('.notification-button')
  const panel = document.querySelector('.notification-panel')
  const count = document.querySelector('.notification-count')
  const list = document.querySelector('.notification-list')
  const empty = document.querySelector('.notification-empty')
  const enable = document.querySelector('.notification-enable')
  if (!button || !panel || !count || !list || !empty) return

  const seenKey = 'inkandechoes_last_poem_notification'
  let latestSeen = Number(localStorage.getItem(seenKey) || 0)
  let pending = []

  function render() {
    list.replaceChildren()
    empty.hidden = pending.length > 0
    pending.forEach((poem) => {
      const item = document.createElement('li')
      const link = document.createElement('a')
      link.href = poem.url
      link.textContent = poem.title
      item.appendChild(link)
      list.appendChild(item)
    })
    count.textContent = pending.length
    count.hidden = pending.length === 0
  }

  async function checkForPoems() {
    try {
      const response = await fetch('/api/v1/notifications', { cache: 'no-store' })
      if (!response.ok) return
      const poems = await response.json()
      if (!poems.length) return

      const newest = Math.max(...poems.map((poem) => new Date(poem.created_at).getTime()))
      if (!latestSeen) {
        latestSeen = newest
        localStorage.setItem(seenKey, String(latestSeen))
        return
      }

      const fresh = poems.filter((poem) => new Date(poem.created_at).getTime() > latestSeen)
      if (!fresh.length) return
      pending = [...fresh, ...pending].filter((poem, index, items) =>
        items.findIndex((item) => item.id === poem.id) === index
      )
      latestSeen = Math.max(latestSeen, newest)
      localStorage.setItem(seenKey, String(latestSeen))
      render()

      if (document.visibilityState !== 'visible' && 'Notification' in window && Notification.permission === 'granted') {
        new Notification('A new poem has arrived', { body: fresh[0].title })
      }
    } catch (error) {
      console.warn('Could not check poem notifications', error)
    }
  }

  button.addEventListener('click', () => {
    const isOpen = !panel.hidden
    panel.hidden = isOpen
    button.setAttribute('aria-expanded', String(!isOpen))
    if (!isOpen) {
      pending = []
      render()
    }
  })

  if (enable) {
    enable.addEventListener('click', async () => {
      if ('Notification' in window && Notification.permission === 'default') {
        await Notification.requestPermission()
      }
      enable.textContent = Notification.permission === 'granted' ? 'Alerts enabled' : 'Alerts blocked'
    })
  }

  checkForPoems()
  window.setInterval(checkForPoems, 20000)
})()