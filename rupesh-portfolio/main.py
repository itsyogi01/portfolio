
from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pwdlib import PasswordHash

import database

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Rupesh Yogi Portfolio")

# Development key only. Replace before public deployment.
app.add_middleware(
    SessionMiddleware,
    secret_key="change-this-to-a-long-random-secret-before-deployment",
    same_site="lax",
    https_only=False,  # Local development only; enable HTTPS in production.
)

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static",
)

password_hash = PasswordHash.recommended()
database.init_db()


def render_page(request: Request, filename: str, **context):
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
    return templates.TemplateResponse(
        request=request,
        name=filename,
        context=context,
    )



@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return render_page(
        request,
        "index.html",
        logged_in=bool(request.session.get("user_id")),
    )



@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return render_page(request, "register.html", error=None)


@app.post("/register")
def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    name = name.strip()
    email = email.strip().lower()

    if not name or len(name) > 100:
        return render_page(
            request, "register.html",
            error="Please enter a valid name (up to 100 characters)."
        )

    if len(email) > 254 or "@" not in email:
        return render_page(
            request, "register.html",
            error="Please enter a valid email address."
        )

    if len(password) < 8:
        return render_page(
            request, "register.html",
            error="Password must be at least 8 characters."
        )

    try:
        user_id = database.create_user(
            name, email, password_hash.hash(password)
        )
    except Exception as exc:
        import sqlite3
        if isinstance(exc, sqlite3.IntegrityError):
            return render_page(
                request, "register.html",
                error="This email is already registered. Please log in."
            )
        raise

    request.session.clear()
    request.session["user_id"] = user_id
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render_page(request, "login.html", error=None)


@app.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    user = database.find_user_by_email(email.strip().lower())

    if not user or not password_hash.verify(password, user["password_hash"]):
        return render_page(
            request, "login.html",
            error="Incorrect email or password."
        )

    request.session.clear()
    request.session["user_id"] = user["id"]
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user_id = request.session.get("user_id")

    if not user_id:
        return RedirectResponse("/login", status_code=303)

    user = database.find_user_by_id(user_id)
    if not user:
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    return render_page(request, "dashboard.html", user=user)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)

@app.post("/profile/update")
def update_profile(
    request: Request,
    name: str = Form(...),
):
    user_id = request.session.get("user_id")

    if not user_id:
        return RedirectResponse("/login", status_code=303)

    name = name.strip()

    if not name or len(name) > 100:
        user = database.find_user_by_id(user_id)
        return render_page(
            request,
            "dashboard.html",
            user=user,
            profile_error="Name must be between 1 and 100 characters.",
            profile_success=None,
        )

    database.update_user_name(user_id, name)

    return RedirectResponse("/dashboard", status_code=303)

