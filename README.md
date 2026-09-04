# Ink & Echoes — Minimal Prototype

This prototype includes:
- Flask backend with SQLite
- Authentication (signup/login/logout) with DOB age check
- Simple AI chat endpoint (OpenAI-compatible fallback)
- Admin panel for adding poems
- Frontend templates and simple styling

Run locally:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:FLASK_APP='app'
setx OPENAI_API_KEY "your_key_here"
python app.py
```

You can also run the app with `flask run` after setting `FLASK_APP=app`.

Set `OPENAI_API_KEY` to enable AI chat via OpenAI. Otherwise the chat endpoint echoes back messages.

For the admin panel, set separate login credentials before running the app:

```powershell
$env:ADMIN_USERNAME='admin'
$env:ADMIN_PASSWORD='change-me-now'
```

The admin login uses these values instead of the normal user sign-in flow.
