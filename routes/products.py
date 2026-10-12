import math

from flask import Blueprint, abort, render_template, request, redirect, url_for
from flask_login import current_user
from extensions import db
from sqlalchemy import or_
import models

products_bp = Blueprint('products', __name__)

# --- Product Manager ---
@products_bp.route('/products', methods=['GET','POST'])
def products():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', '').strip()

    if request.method == 'POST':
        action = request.form.get('action')

        # Action: Create a new product base
        if action == 'create_product':
            name = request.form.get('name')
            code = request.form.get('product_code')
            image_url = request.form.get('image_url')
            actual_price = request.form.get('actual_price')
            design_id = request.form.get('design_type_id')

            if name and code and design_id:
                new_product = models.Product(
                    workspace_id=current_user.workspace_id,
                    name=name,
                    product_code=code,
                    image_url=image_url if image_url else None,
                    actual_price=float(actual_price) if actual_price else None,
                    design_type_id=int(float(design_id))
                )
                if not models.DesignType.query.filter_by(
                    id=new_product.design_type_id, workspace_id=current_user.workspace_id
                ).first():
                    abort(404)
                db.session.add(new_product)
                db.session.commit()
                return redirect(url_for('products.products', page=page, q=search_query))

        # Action: Add an ingredient stem & quantity to product's recipe
        elif action == 'add_ingredient':
            product_id = request.form.get('product_id')
            ingredient_id = request.form.get('ingredient_id')
            try:
                parsed_product_id = int(float(product_id))
                parsed_ingredient_id = int(float(ingredient_id))
                quantity = float(request.form['quantity'])
            except (KeyError, TypeError, ValueError):
                abort(400, description="Valid product, ingredient, and quantity values are required.")
            if not math.isfinite(quantity) or quantity <= 0:
                abort(400, description="Recipe quantity must be a finite number greater than zero.")

            recipe_item = models.ProductIngredient(
                workspace_id=current_user.workspace_id,
                product_id=parsed_product_id,
                ingredient_id=parsed_ingredient_id,
                quantity=quantity,
            )
            if not models.Product.query.filter_by(
                id=parsed_product_id, workspace_id=current_user.workspace_id
            ).first():
                abort(404)
            if not models.Ingredient.query.filter_by(
                id=parsed_ingredient_id, workspace_id=current_user.workspace_id
            ).first():
                abort(404)
            db.session.add(recipe_item)
            db.session.commit()
            # Retain search and page params on redirect
            page = request.args.get('page', 1, type=int)
            q = request.args.get('q', '')
            return redirect(url_for('products.products', page=page, q=q))

        # Action: Delete a recipe item from an arrangement
        elif action == 'delete_recipe_item':
            item_id = request.form.get('recipe_item_id')
            if item_id:
                item=models.ProductIngredient.query.filter_by(
                    id=int(float(item_id)), workspace_id=current_user.workspace_id
                ).first()
                if item:
                    db.session.delete(item)
                    db.session.commit()
                    page = request.args.get('page', 1, type=int)
                    q = request.args.get('q', '')
                    return redirect(url_for('products.products', page=page, q=q))

        elif action == 'edit_product':
            product_id = request.form.get('product_id')
            name = request.form.get('name')
            code = request.form.get('product_code')
            actual_price = request.form.get('actual_price')
            image_url = request.form.get('image_url')
            design_id = request.form.get('design_type_id')

            if product_id and name and code and design_id:
                product = models.Product.query.filter_by(
                    id=int(float(product_id)), workspace_id=current_user.workspace_id
                ).first()
                if product: 
                    parsed_design_id = int(float(design_id))
                    if not models.DesignType.query.filter_by(
                        id=parsed_design_id, workspace_id=current_user.workspace_id
                    ).first():
                        abort(404)
                    product.name = name.strip()
                    product.product_code = code
                    product.actual_price = float(actual_price) if actual_price else None
                    product.image_url = image_url if image_url else None
                    product.design_type_id = parsed_design_id
                    db.session.commit()
            return redirect(url_for('products.products', page=page, q=search_query))

    # GET Request handling (Search + Pagination)
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 25 # Limits display to 25 products per page

    # Base query
    query = models.Product.query.filter_by(workspace_id=current_user.workspace_id)
    
    # Apply search filter if query string is present
    if search_query:
        query = query.filter(
            or_(
                models.Product.name.ilike(f'%{search_query}%'),
                models.Product.product_code.ilike(f'%{search_query}%')
            )
        )

    # Execute pagination (returns a Pagination object)
    pagination = query.order_by(models.Product.name.asc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    # Query products on page, all ingredients, and design fee styles
    products_on_page = pagination.items
    all_ingredients = models.Ingredient.query.filter_by(workspace_id=current_user.workspace_id).order_by(models.Ingredient.name.asc()).all()
    all_design_types = models.DesignType.query.filter_by(workspace_id=current_user.workspace_id).order_by(models.DesignType.name.asc()).all()

    return render_template(
        'products.html',
        products=products_on_page,
        pagination=pagination,
        search_query=search_query,
        ingredients=all_ingredients,
        design_types=all_design_types
    )
