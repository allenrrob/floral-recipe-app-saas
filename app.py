import os

from flask import Flask, redirect, request, url_for
from flask_login import current_user
from extensions import csrf, db, login_manager, migrate
import models
from routes import (
    auth_bp,
    billing_bp,
    design_fees_bp,
    ingredient_types_bp,
    ingredients_bp,
    pages_bp,
    products_bp,
    quick_calculator_bp,
    vendors_bp,
)


def create_app(test_config=None):
    app = Flask(__name__)

    database_url = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    secret_key = os.environ.get("SECRET_KEY") or (test_config or {}).get("SECRET_KEY")
    if not secret_key:
        raise RuntimeError("Set SECRET_KEY to a unique, random value before starting the app.")

    app.config.from_mapping(
        SECRET_KEY=secret_key,
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE") == "1",
        STRIPE_SECRET_KEY=os.environ.get("STRIPE_SECRET_KEY"),
        STRIPE_PRICE_ID=os.environ.get("STRIPE_PRICE_ID"),
        STRIPE_WEBHOOK_SECRET=os.environ.get("STRIPE_WEBHOOK_SECRET"),
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"
    login_manager.session_protection = "strong"
    migrate.init_app(app, db)
    csrf.init_app(app)
    for blueprint in (
        auth_bp,
        billing_bp,
        pages_bp,
        ingredients_bp,
        products_bp,
        quick_calculator_bp,
        vendors_bp,
        ingredient_types_bp,
        design_fees_bp,
    ):
        app.register_blueprint(blueprint)

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(models.User, int(user_id))
        except (TypeError, ValueError):
            return None

    @app.before_request
    def enforce_authentication_and_subscription():
        if request.endpoint is None or request.endpoint == "static":
            return None
        if request.endpoint in {"auth.login", "auth.signup", "billing.webhook"}:
            return None
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if request.endpoint not in {
            "auth.logout",
            "billing.checkout",
            "billing.success",
            "billing.portal",
            "billing.status",
        }:
            subscription = current_user.workspace.subscription
            if subscription is None or not subscription.is_active:
                return redirect(url_for("billing.status"))
        return None

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
