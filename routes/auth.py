import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
import models

auth_bp = Blueprint("auth", __name__)


def _role_home(user):
    return url_for("pages.recipes") if user.role == "user" else url_for("billing.status")


@auth_bp.route("/team", methods=["GET", "POST"])
def team():
    if not current_user.is_admin:
        abort(403)

    invite_link = None
    if request.method == "POST":
        action = request.form.get("action")
        if action == "invite":
            email = request.form.get("email", "").strip().casefold()
            role = request.form.get("role", "")
            email_name, separator, email_domain = email.partition("@")
            if (
                not separator or not email_name or "." not in email_domain
                or any(character.isspace() for character in email) or len(email) > 254
            ):
                abort(400, description="Enter a valid email address.")
            if role not in {"admin", "user"}:
                abort(400, description="Select a valid access level.")
            if models.User.query.filter_by(email=email).first():
                flash("That email address already has an account.", "error")
            else:
                models.UserInvitation.query.filter_by(
                    workspace_id=current_user.workspace_id, email=email
                ).delete()
                token = secrets.token_urlsafe(32)
                invitation = models.UserInvitation(
                    workspace_id=current_user.workspace_id,
                    email=email,
                    role=role,
                    token_hash=hashlib.sha256(token.encode()).hexdigest(),
                    expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7),
                )
                db.session.add(invitation)
                db.session.commit()
                invite_link = url_for(
                    "auth.accept_invitation", token=token, _external=True
                )
        elif action == "change_role":
            try:
                user_id = int(request.form["user_id"])
            except (KeyError, TypeError, ValueError):
                abort(400, description="Select a valid user.")
            role = request.form.get("role")
            if role not in {"admin", "user"}:
                abort(400, description="Select a valid access level.")
            target = models.User.query.filter_by(
                id=user_id, workspace_id=current_user.workspace_id
            ).first_or_404()
            if target.id == current_user.id and role != "admin":
                admin_count = models.User.query.filter_by(
                    workspace_id=current_user.workspace_id, role="admin"
                ).count()
                if admin_count <= 1:
                    abort(400, description="A workspace must have at least one admin.")
            target.role = role
            db.session.commit()
            flash(f"Access updated for {target.email}.", "success")
            return redirect(url_for("auth.team"))
        else:
            abort(400, description="Select a valid team action.")

    return render_template(
        "team.html",
        users=models.User.query.filter_by(
            workspace_id=current_user.workspace_id
        ).order_by(models.User.email.asc()).all(),
        invitations=models.UserInvitation.query.filter_by(
            workspace_id=current_user.workspace_id, accepted_at=None
        ).order_by(models.UserInvitation.id.desc()).all(),
        invite_link=invite_link,
    )


@auth_bp.route("/accept-invitation/<token>", methods=["GET", "POST"])
def accept_invitation(token):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    invitation = models.UserInvitation.query.filter_by(token_hash=token_hash).first()
    if (
        invitation is None
        or invitation.accepted_at is not None
        or invitation.expires_at <= datetime.now(timezone.utc).replace(tzinfo=None)
    ):
        abort(404)

    if request.method == "POST":
        password = request.form.get("password", "")
        if len(password) < 12:
            flash("Choose a password of at least 12 characters.", "error")
            return render_template("accept_invitation.html", email=invitation.email), 400
        if models.User.query.filter_by(email=invitation.email).first():
            abort(409, description="An account with this email already exists.")
        user = models.User(
            email=invitation.email,
            password_hash=generate_password_hash(password),
            workspace_id=invitation.workspace_id,
            role=invitation.role,
        )
        invitation.accepted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(_role_home(user))

    return render_template("accept_invitation.html", email=invitation.email)


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(_role_home(current_user))

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
        return redirect(_role_home(user))

    return render_template("signup.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_role_home(current_user))

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
