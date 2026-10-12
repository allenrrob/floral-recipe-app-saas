from flask import Blueprint, render_template
from flask_login import current_user

import models

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    return render_template("index.html")


@pages_bp.route("/profit-margins")
def profit_margins():
    products = models.Product.query.filter_by(
        workspace_id=current_user.workspace_id
    ).order_by(models.Product.name.asc()).all()

    total_wholesale = sum(product.raw_wholesale_cost for product in products)
    total_retail = sum(product.suggested_retail_price for product in products)
    avg_margin = (
        sum(product.profit_margin_percentage for product in products) / len(products)
        if products
        else 0.0
    )

    return render_template(
        "profit_margins.html",
        products=products,
        total_wholesale=total_wholesale,
        total_retail=total_retail,
        avg_margin=avg_margin,
    )
