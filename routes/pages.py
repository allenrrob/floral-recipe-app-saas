from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user

import models

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    if current_user.is_authenticated and not current_user.is_admin:
        return redirect(url_for("pages.recipes"))
    return render_template("index.html")


@pages_bp.route("/recipes")
def recipes():
    query = models.Product.query.filter_by(workspace_id=current_user.workspace_id)
    search_query = request.args.get("q", "").strip()
    if search_query:
        query = query.filter(
            models.Product.name.ilike(f"%{search_query}%")
            | models.Product.product_code.ilike(f"%{search_query}%")
        )
    products = query.order_by(models.Product.name.asc()).all()
    return render_template(
        "recipes.html", products=products, search_query=search_query
    )


@pages_bp.route("/profit-margins")
def profit_margins():
    products = models.Product.query.filter_by(
        workspace_id=current_user.workspace_id
    ).order_by(models.Product.name.asc()).all()

    avg_margin = (
        sum(product.profit_margin_percentage for product in products) / len(products)
        if products
        else 0.0
    )

    return render_template(
        "profit_margins.html",
        products=products,
        avg_margin=avg_margin,
    )
