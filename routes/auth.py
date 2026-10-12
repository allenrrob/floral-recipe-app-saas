from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
import models

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("billing.status"))

    if request.method == "POST":
        workspace_name = request.form.get("workspace_name", "").strip()
        email = request.form.get("email", "").strip().casefold()
        password = request.form.get("password", "")

        email_name, separator, email_domain = email.partition("@")
        valid_email = (
            separator == "@"
            and email.count("@") == 1
            and bool(email_name)
            and "." in email_domain
            and not any(character.isspace() for character in email)
            and len(email) <= 254
        )
        if not workspace_name or not valid_email or len(password) < 12:
            flash("Enter a business name, a valid email, and a password of at least 12 characters.", "error")
            return render_template("signup.html"), 400

        workspace = models.Workspace(name=workspace_name)
        db.session.add(workspace)
        db.session.flush()
        user = models.User(
            email=email,
            password_hash=generate_password_hash(password),
            workspace_id=workspace.id,
        )
        workspace.subscription = models.Subscription(status="incomplete")
        db.session.add_all(
            [
                models.IngredientType(name="Standard Flower", markup=3.5, workspace_id=workspace.id),
                models.IngredientType(name="Premium Flower", markup=4.0, workspace_id=workspace.id),
                models.IngredientType(name="Greenery", markup=3.5, workspace_id=workspace.id),
                models.IngredientType(name="Hard Goods & Vases", markup=2.0, workspace_id=workspace.id),
                models.DesignType(
                    name="Everyday Arrangement",
                    design_fee_percentage=20.0,
                    workspace_id=workspace.id,
                ),
                models.DesignType(
                    name="Wedding / Event Floral",
                    design_fee_percentage=30.0,
                    workspace_id=workspace.id,
                ),
                models.DesignType(
                    name="Sympathy / Funeral Spray",
                    design_fee_percentage=25.0,
                    workspace_id=workspace.id,
                ),
                user,
            ]
        )
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("We couldn't create the account. The email may already be registered.", "error")
            return render_template("signup.html"), 409

        login_user(user)
        return redirect(url_for("billing.status"))

    return render_template("signup.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("billing.status"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().casefold()
        password = request.form.get("password", "")
        user = models.User.query.filter_by(email=email).first()
        if user is None or not check_password_hash(user.password_hash, password):
            flash("Email or password was incorrect.", "error")
            return render_template("login.html"), 401

        login_user(user)
        return redirect(url_for("billing.status"))

    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
