import math

from flask import Blueprint, abort, render_template, request
from flask_login import current_user

import models

quick_calculator_bp = Blueprint('quick_calculator', __name__)

# --- Quick Calculator ---
@quick_calculator_bp.route('/quick-calculator', methods=['GET', 'POST'])
@quick_calculator_bp.route('/designer-calculator', methods=['GET', 'POST'], endpoint='designer_calculator')
def quick_calculator():
    # Fetch available options for the dropdowns
    all_ingredients = models.Ingredient.query.filter_by(
        workspace_id=current_user.workspace_id
    ).order_by(models.Ingredient.name.asc()).all()
    all_design_types = models.DesignType.query.filter_by(
        workspace_id=current_user.workspace_id
    ).order_by(models.DesignType.name.asc()).all()

    # Default results to none and set initial row state
    calculated_results = None
    row_count = 1
    submitted_rows = [('', '1')]
    selected_design_id = None

    if request.method == 'POST':
        action = request.form.get('action')
        current_row_count = int(float(request.form.get('row_count', 1)))

        # Extract selected design style ID and form array inputs
        selected_design_id = request.form.get('design_type_id')
        selected_ing_ids = request.form.getlist('ingredient_id[]')
        quantities = request.form.getlist('quantity[]')

        # Keep track of user entries across re-renders
        submitted_rows = list(zip(selected_ing_ids, quantities))

        # Action: User clicked "+ Add Item"
        if action == 'add_row':
            row_count = current_row_count + 1
            submitted_rows.append(('', '1'))  # Append an empty row pair

        # Action: User clicked a Delete Row button ("delete_row_X")
        elif action and action.startswith('delete_row_'):
            delete_index = int(float(action.split('_')[-1]))
            if 0 <= delete_index < len(submitted_rows):
                submitted_rows.pop(delete_index)
            # Ensure at least 1 row remains visible
            row_count = max(1, len(submitted_rows))

        else:
            row_count = current_row_count

        raw_cost = 0.0
        marked_up_cost = 0.0
        has_items = False

        # Iterate through remaining paired array entries safely
        for ing_id, qty_str in submitted_rows:
            if ing_id and qty_str:
                try:
                    ingredient_id = int(float(ing_id))
                except (TypeError, ValueError):
                    abort(400, description="Select a valid ingredient.")
                ing = models.Ingredient.query.filter_by(
                    id=ingredient_id, workspace_id=current_user.workspace_id
                ).first()
                if ing is None:
                    abort(404)
                has_items = True
                try:
                    qty = float(qty_str)
                except (TypeError, ValueError):
                    abort(400, description="Enter a valid quantity.")
                if not math.isfinite(qty) or qty <= 0:
                    abort(400, description="Quantity must be a finite number greater than zero.")
                if ing.qty_per_pkg > 0:
                    # Calculate single-stem unit cost & markup
                    unit_cost = ing.cost_per_pkg / ing.qty_per_pkg
                    markup = ing.type_info.markup if ing.type_info else 1.0

                    # Accumulate totals across all temporary recipe rows
                    raw_cost += unit_cost * qty
                    marked_up_cost += (unit_cost * qty) * markup

        # Package results if at least one valid item line exists
        if has_items:
            design_style = None
            if selected_design_id:
                try:
                    parsed_design_id = int(float(selected_design_id))
                except (TypeError, ValueError):
                    abort(400, description="Select a valid design style.")
                design_style = models.DesignType.query.filter_by(
                    id=parsed_design_id,
                    workspace_id=current_user.workspace_id,
                ).first()
                if design_style is None:
                    abort(404)
            fee_pct = design_style.design_fee_percentage if design_style else 0.0

            design_fee = marked_up_cost * (fee_pct / 100.0)
            srp = marked_up_cost + design_fee
            profit_margin = ((srp - raw_cost) / srp * 100) if srp > 0 else 0.0

            # Package results in a dictionary to pass directly into the template
            calculated_results = {
                'srp': srp,
            }
            if current_user.is_admin:
                calculated_results.update({
                    'raw_cost': raw_cost,
                    'marked_up_cost': marked_up_cost,
                    'design_fee': design_fee,
                    'margin': profit_margin
                })

    return render_template(
        'quick_calculator.html',
        ingredients=all_ingredients,
        design_types=all_design_types,
        results=calculated_results,
        row_count=row_count,
        submitted_rows=submitted_rows,
        selected_design_id=selected_design_id
    )