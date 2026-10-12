from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import current_user
from extensions import db
import models

vendors_bp = Blueprint('vendors', __name__)

# --- Vendor Manager ---
@vendors_bp.route('/vendors', methods=['GET', 'POST'])
def vendors():
    if request.method == 'POST':
        action = request.form.get('action')

        # Action: Create a new vendor
        if action == 'create_vendor':
            name = request.form.get('name')
            if name:
                new_vendor = models.Vendor(name=name, workspace_id=current_user.workspace_id)
                db.session.add(new_vendor)
                db.session.commit()
                return redirect(url_for('vendors.vendors'))

        elif action == 'edit_vendor':
            vendor_id = request.form.get('vendor_id')
            name = request.form.get('name')

            if vendor_id and name:
                vendor = models.Vendor.query.filter_by(
                    id=int(float(vendor_id)), workspace_id=current_user.workspace_id
                ).first()
                if vendor:
                    vendor.name = name.strip()

                    db.session.commit()
            return redirect(url_for('vendors.vendors'))


    all_vendors = models.Vendor.query.filter_by(
        workspace_id=current_user.workspace_id
    ).order_by(models.Vendor.name.asc()).all()
    return render_template('vendors.html', vendors=all_vendors)


@vendors_bp.route('/vendors/<int:vendor_id>/inventory')
def vendor_inventory(vendor_id):
    vendor = models.Vendor.query.filter_by(
        id=vendor_id, workspace_id=current_user.workspace_id
    ).first_or_404()
    ingredients = (
        models.Ingredient.query
        .filter_by(vendor_id=vendor.id, workspace_id=current_user.workspace_id)
        .join(models.IngredientType)
        .order_by(models.IngredientType.name.asc(), models.Ingredient.name.asc())
        .all()
    )
    return render_template(
        'vendor_inventory.html',
        vendor=vendor,
        ingredients=ingredients,
    )