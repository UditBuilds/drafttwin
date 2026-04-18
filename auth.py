"""Flask-Login wiring + User model backed by the brands table."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager, UserMixin, current_user, login_required, login_user, logout_user,
)
from werkzeug.security import check_password_hash, generate_password_hash

import db

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "info"


class User(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.email = row["email"]
        self.name = row["name"]
        self.brain_md = row["brain_md"]
        self.version = row["version"]

    def get_id(self):
        return str(self.id)

    @property
    def has_brain(self):
        return bool(self.brain_md)


@login_manager.user_loader
def load_user(user_id):
    try:
        row = db.get_brand(int(user_id))
    except (TypeError, ValueError):
        return None
    return User(row) if row else None


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not email or not password:
            return render_template("signup.html", error="Email and password required."), 400
        if len(password) < 8:
            return render_template("signup.html", error="Password must be at least 8 characters.", email=email), 400
        if db.get_brand_by_email(email):
            return render_template("signup.html", error="An account with that email already exists.", email=email), 400

        brand_id = db.create_account(email, generate_password_hash(password))
        row = db.get_brand(brand_id)
        login_user(User(row))
        return redirect(url_for("onboarding"))

    return render_template("signup.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        row = db.get_brand_by_email(email)
        if not row or not row["password_hash"] or not check_password_hash(row["password_hash"], password):
            return render_template("login.html", error="Invalid email or password.", email=email), 401
        login_user(User(row))
        return redirect(url_for("index"))

    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("auth.login"))
