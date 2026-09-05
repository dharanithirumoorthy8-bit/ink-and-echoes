// Simple offline queue: save poem entries to localStorage when offline
(function(){
  const QUEUE_KEY = 'inkandechoes_admin_queue'

  function readQueue(){
    try{ return JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]') }catch(e){ return [] }
  }
  function writeQueue(q){ localStorage.setItem(QUEUE_KEY, JSON.stringify(q)) }

  async function syncQueue(){
    if(!navigator.onLine) return
    const q = readQueue()
    if(!q.length) return
    for(let i=0;i<q.length;){
      const item = q[i]
      try{
        const res = await fetch('/admin/poem/new', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(item)
        })
        if(res.ok){
          q.splice(i,1)
        }else{
          // stop on first failure to avoid tight loop
          console.warn('Sync failed', await res.text())
          break
        }
      }catch(err){
        console.warn('Network error during sync', err)
        break
      }
    }
    writeQueue(q)
    if(q.length===0){
      const notice = document.getElementById('offline-sync-notice')
      if(notice) notice.textContent = 'All queued poems synced.'
    }
  }

  // intercept admin form submit
  document.addEventListener('DOMContentLoaded', ()=>{
    const form = document.querySelector('form[action="/admin/poem/new"]')
    if(!form) return

    form.addEventListener('submit', (e)=>{
      if(navigator.onLine) return // let normal submit happen
      e.preventDefault()
      const title = (form.querySelector('input[name="title"]')||{}).value || ''
      const category = (form.querySelector('input[name="category"]')||{}).value || ''
      const body = (form.querySelector('textarea[name="body"]')||{}).value || ''
      if(!title.trim() || !body.trim()){
        alert('Please add both a title and the poem text.')
        return
      }
      const q = readQueue()
      q.push({title, category, body, created_at: new Date().toISOString()})
      writeQueue(q)
      const notice = document.getElementById('offline-sync-notice')
      if(notice) notice.textContent = 'Saved locally — will sync when online.'
      else alert('Saved locally — will sync when online.')
      form.reset()
    })

    // attempt initial sync
    syncQueue()
    // try syncing when back online
    window.addEventListener('online', ()=>{ syncQueue() })
  })
})();
