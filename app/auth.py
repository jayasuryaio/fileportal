"""Sign-up, login and logout routes."""
import pymysql
from flask import (Blueprint, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from . import db
from .validators import ValidationError, validate_signup

bp = Blueprint("auth", __name__)

# Used to keep login timing similar whether or not the email exists.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


@bp.route("/")
def index():
    return redirect(url_for("files.dashboard" if g.user else "auth.login"))


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if g.user:
        return redirect(url_for("files.dashboard"))
    form_data, errors = {}, {}
    if request.method == "POST":
        form_data = request.form.to_dict()
        try:
            data = validate_signup(request.form)
            db.execute(
                "INSERT INTO users (name, age, address, email, mobile, password_hash) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (data["name"], data["age"], data["address"], data["email"],
                 data["mobile"], generate_password_hash(data["password"])),
            )
            flash("Account created! Please log in.", "success")
            return redirect(url_for("auth.login"))
        except ValidationError as err:
            errors = err.args[0] if isinstance(err.args[0], dict) else {"form": str(err)}
        except pymysql.err.IntegrityError:
            errors = {"email": "An account with this email already exists."}
        except pymysql.MySQLError:
            errors = {"form": "Database error. Please try again shortly."}
    return render_template("signup.html", errors=errors, form=form_data)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("files.dashboard"))
    email = ""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        try:
            user = db.query_one(
                "SELECT id, password_hash FROM users WHERE email = %s", (email,))
        except pymysql.MySQLError:
            flash("Database error. Please try again shortly.", "error")
            return render_template("login.html", email=email), 503
        ok = check_password_hash(user["password_hash"] if user else _DUMMY_HASH, password)
        if user and ok:
            session.clear()  # prevent session fixation
            session["user_id"] = user["id"]
            session.permanent = True
            return redirect(url_for("files.dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("login.html", email=email)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
