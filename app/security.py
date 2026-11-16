"""Session, CSRF and login-required helpers."""
import hmac
import secrets
from functools import wraps

from flask import abort, g, redirect, request, session, url_for

from . import db


def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def protect_csrf():
    """before_request hook: reject state-changing requests without a valid token."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        sent = request.form.get("csrf_token", "")
        expected = session.get("csrf", "")
        if not expected or not hmac.compare_digest(sent, expected):
            abort(400, "Invalid or missing security token. Please reload and retry.")


def load_user():
    """before_request hook: attach the logged-in user (or None) to ``g``."""
    uid = session.get("user_id")
    g.user = db.query_one(
        "SELECT id, name, email FROM users WHERE id = %s", (uid,)
    ) if uid else None
    if uid and g.user is None:
        session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped
