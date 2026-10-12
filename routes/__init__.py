from routes.auth import auth_bp
from routes.billing import billing_bp
from routes.design_fees import design_fees_bp
from routes.ingredient_types import ingredient_types_bp
from routes.ingredients import ingredients_bp
from routes.pages import pages_bp
from routes.products import products_bp
from routes.quick_calculator import quick_calculator_bp
from routes.vendors import vendors_bp

__all__ = [
    "auth_bp",
    "billing_bp",
    "design_fees_bp",
    "ingredient_types_bp",
    "ingredients_bp",
    "pages_bp",
    "products_bp",
    "quick_calculator_bp",
    "vendors_bp",
]
