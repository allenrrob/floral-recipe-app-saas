from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import current_user
from extensions import db
import models

design_fees_bp = Blueprint('design_fees', __name__)

# --- Design Fee Manager ---
@design_fees_bp.route('/design-fees', methods=['GET', 'POST'])
def design_fees():
    if request.method == 'POST':
        action = request.form.get('action')

        # Action: Create a new design fee style
        if action == 'create_design_type' or not action:
            name = request.form.get('name')
            fee_pct = request.form.get('design_fee_percentage')
            if name and fee_pct:
                new_fee = models.DesignType(
                    name=name.strip(), 
                    design_fee_percentage=float(fee_pct),
                    workspace_id=current_user.workspace_id,
                )
                db.session.add(new_fee)
                db.session.commit()
                return redirect(url_for('design_fees.design_fees'))

        # Action: Edit an existing design fee style
        elif action == 'edit_design_type':
            dt_id = request.form.get('design_type_id')
            name = request.form.get('name')
            fee_pct = request.form.get('design_fee_percentage')

            if dt_id and name and fee_pct:
                dt = models.DesignType.query.filter_by(
                    id=int(float(dt_id)), workspace_id=current_user.workspace_id
                ).first()
                if dt:
                    dt.name = name.strip()
                    dt.design_fee_percentage = float(fee_pct)
                    db.session.commit()

            return redirect(url_for('design_fees.design_fees'))

    all_fees = models.DesignType.query.filter_by(
        workspace_id=current_user.workspace_id
    ).order_by(models.DesignType.name.asc()).all()
    return render_template('design_fees.html', fees=all_fees)