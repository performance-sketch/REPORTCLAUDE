from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

DASHBOARD_USERNAME = os.environ["DASHBOARD_USERNAME"]
DASHBOARD_PASSWORD = os.environ["DASHBOARD_PASSWORD"]
SESSION_SECRET_KEY = os.environ["SESSION_SECRET_KEY"]
INDEX_HTML_PATH = Path(__file__).parent / "index.html"

app = FastAPI(docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    session_cookie="reportclaude_session",
    same_site="lax",
    https_only=True,
)

LOGIN_PAGE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Login — Vertical Rio Dashboard</title>
<style>
  body {{ background:#0f172a; color:#f1f5f9; font-family:system-ui,sans-serif;
         display:flex; align-items:center; justify-content:center; height:100vh; margin:0; }}
  form {{ background:#1e293b; border:1px solid #334155; border-radius:12px; padding:32px;
          width:280px; display:flex; flex-direction:column; gap:12px; }}
  input {{ background:#263248; border:1px solid #334155; border-radius:8px; padding:10px 12px;
           color:#f1f5f9; font-size:.9rem; }}
  button {{ background:#6366f1; border:none; border-radius:8px; padding:10px; color:#fff;
            font-weight:600; cursor:pointer; }}
  button:hover {{ background:#4f46e5; }}
  .error {{ color:#ef4444; font-size:.8rem; }}
  h1 {{ font-size:1rem; margin:0 0 4px; }}
</style>
</head>
<body>
<form method="post" action="/login">
  <h1>Vertical Rio — Dashboard</h1>
  {error}
  <input type="text" name="username" placeholder="Usuário" autofocus required>
  <input type="password" name="password" placeholder="Senha" required>
  <button type="submit">Entrar</button>
</form>
</body>
</html>"""


@app.get("/login", response_class=HTMLResponse)
async def login_form():
    return LOGIN_PAGE.format(error="")


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    valid = secrets.compare_digest(username, DASHBOARD_USERNAME) & secrets.compare_digest(
        password, DASHBOARD_PASSWORD
    )
    if not valid:
        return HTMLResponse(
            LOGIN_PAGE.format(error='<div class="error">Usuário ou senha inválidos.</div>'),
            status_code=401,
        )
    request.session["authenticated"] = True
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/")
async def dashboard(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)
    return FileResponse(INDEX_HTML_PATH)
