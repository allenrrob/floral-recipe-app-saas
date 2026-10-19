import os
import uuid

from flask import Blueprint, abort, current_app, render_template, request, redirect, url_for, send_from_directory
from flask_login import current_user
from extensions import db
import models

ingredients_bp = Blueprint('ingredients', __name__)


def _save_ingredient_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    extension = os.path.splitext(file_storage.filename)[1].lower()
    content = file_storage.stream.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        abort(413, description="Ingredient images must be 5 MB or smaller.")
    signatures = {
        ".jpg": content.startswith(b"\xff\xd8\xff"),
        ".jpeg": content.startswith(b"\xff\xd8\xff"),
        ".png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        ".gif": content.startswith((b"GIF87a", b"GIF89a")),
        ".webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
    }
    if extension not in signatures or not signatures[extension]:
        abort(400, description="Upload a valid JPG, PNG, GIF, or WebP image.")

    filename = f"{uuid.uuid4().hex}{extension}"
    directory = os.path.join(
        current_app.instance_path, "ingredient-uploads", str(current_user.workspace_id)
    )
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, filename), "xb") as image_file:
        image_file.write(content)
    return filename


@ingredients_bp.route('/ingredient-images/<int:ingredient_id>')
def ingredient_image(ingredient_id):
    ingredient = models.Ingredient.query.filter_by(
        id=ingredient_id, workspace_id=current_user.workspace_id
    ).first_or_404()
    if not ingredient.image_filename:
        abort(404)
    directory = os.path.join(
        current_app.instance_path, "ingredient-uploads", str(current_user.workspace_id)
    )
    return send_from_directory(directory, ingredient.image_filename, max_age=3600)


# --- Ingredient Manager ---
@ingredients_bp.route('/ingredients', methods=['GET', 'POST'])
def ingredients():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', '').strip()

    if request.method == 'POST':
        action = request.form.get('action')

        # Action: Create a new ingredient
        if action == 'create_ingredient':
            name = request.form.get('name')
            cost_per_pkg = request.form.get('cost_per_pkg')
            qty_per_pkg = request.form.get('qty_per_pkg')
            type_id = request.form.get('ingredient_type_id')
            vendor_id = request.form.get('vendor_id')

            if name and cost_per_pkg and qty_per_pkg and type_id:
                image_filename = _save_ingredient_image(request.files.get('image'))
                new_ingredient = models.Ingredient(
                    workspace_id=current_user.workspace_id,
                    name=name,
                    cost_per_pkg=float(cost_per_pkg),
                    qty_per_pkg=float(qty_per_pkg),
                    ingredient_type_id=int(float(type_id)),
                    vendor_id=int(float(vendor_id)) if vendor_id else None,
                    image_filename=image_filename,
                )
                if not models.IngredientType.query.filter_by(
                    id=new_ingredient.ingredient_type_id,
                    workspace_id=current_user.workspace_id,
                ).first():
                    abort(404)
                if new_ingredient.vendor_id is not None and not models.Vendor.query.filter_by(
                    id=new_ingredient.vendor_id,
                    workspace_id=current_user.workspace_id,
                ).first():
                    abort(404)

                db.session.add(new_ingredient)
                db.session.commit()
                return redirect(url_for('ingredients.ingredients', page=page, q=search_query))

        # Action: Edit ingredient
        elif action == 'edit_ingredient':
            ing_id = request.form.get('ingredient_id')
            name = request.form.get('name')
            cost_per_pkg = request.form.get('cost_per_pkg')
            qty_per_pkg = request.form.get('qty_per_pkg')
            type_id = request.form.get('ingredient_type_id')
            vendor_id = request.form.get('vendor_id')

            if ing_id and name and cost_per_pkg and qty_per_pkg:
                ingredient = models.Ingredient.query.filter_by(
                    id=int(float(ing_id)), workspace_id=current_user.workspace_id
                ).first()
                if ingredient:
                    type_id = int(float(type_id)) if type_id else None
                    vendor_id = int(float(vendor_id)) if vendor_id else None
                    if type_id is None or not models.IngredientType.query.filter_by(
                        id=type_id, workspace_id=current_user.workspace_id
                    ).first():
                        abort(404)
                    if vendor_id is not None and not models.Vendor.query.filter_by(
                        id=vendor_id, workspace_id=current_user.workspace_id
                    ).first():
                        abort(404)
                    image_filename = _save_ingredient_image(request.files.get('image'))
                    ingredient.name = name.strip()
                    ingredient.cost_per_pkg = float(cost_per_pkg)
                    ingredient.qty_per_pkg = float(qty_per_pkg)
                    ingredient.ingredient_type_id = type_id
                    ingredient.vendor_id = vendor_id
                    if image_filename:
                        ingredient.image_filename = image_filename

                    db.session.commit()

            return redirect(url_for('ingredients.ingredients', page=page, q=search_query))

    # GET Request Handling
    per_page = 25
    query = models.Ingredient.query.filter_by(workspace_id=current_user.workspace_id)

    if search_query:
        query=query.filter(models.Ingredient.name.ilike(f'%{search_query}%'))

    pagination = query.order_by(models.Ingredient.name.asc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    return render_template(
        'ingredients.html',
        ingredients=pagination.items,
        pagination=pagination,
        search_query=search_query,
        vendors=models.Vendor.query.filter_by(workspace_id=current_user.workspace_id).order_by(models.Vendor.name.asc()).all(),
        types=models.IngredientType.query.filter_by(workspace_id=current_user.workspace_id).order_by(models.IngredientType.name.asc()).all()
    )