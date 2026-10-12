import os

from app import app, db
from models import (
    DesignType,
    Ingredient,
    IngredientType,
    Product,
    ProductIngredient,
    Subscription,
    User,
    Vendor,
    Workspace,
)
from werkzeug.security import generate_password_hash

def seed_database():
    with app.app_context():
        email = os.environ.get("SEED_EMAIL", "").strip().casefold()
        password = os.environ.get("SEED_PASSWORD", "")
        if not email or len(password) < 12:
            raise ValueError("Set SEED_EMAIL and a SEED_PASSWORD of at least 12 characters.")

        # Reset tables for clean testing
        db.drop_all()
        db.create_all()

        print("Seeding database...")
        workspace = Workspace(name="Demo Florist")
        db.session.add(workspace)
        db.session.flush()
        workspace_id = workspace.id
        db.session.add_all(
            [
                User(
                    email=email,
                    password_hash=generate_password_hash(password),
                    workspace_id=workspace_id,
                ),
                Subscription(workspace_id=workspace_id, status="active"),
            ]
        )

        # 1. Add Vendors
        v_dutch = Vendor(name="Mayesh Wholesale", workspace_id=workspace_id)
        v_local = Vendor(name="Mello & Co.", workspace_id=workspace_id)
        db.session.add_all([v_dutch, v_local])
        db.session.commit()

        # 2. Add Ingredient Types (with default markup multipliers)
        it_flower = IngredientType(name="Standard Flower", markup=3.5, workspace_id=workspace_id)
        it_premium = IngredientType(name="Premium Flower", markup=4.0, workspace_id=workspace_id)
        it_green = IngredientType(name="Greenery", markup=3.5, workspace_id=workspace_id)
        it_supply = IngredientType(name="Hard Good & Vases", markup=2.0, workspace_id=workspace_id)
        db.session.add_all([it_flower, it_premium, it_green, it_supply])
        db.session.commit()

        # 3. Add Design Types (with labor/design fee percentages)
        dt_everyday = DesignType(name="Everyday Arrangement", design_fee_percentage=20.0, workspace_id=workspace_id)
        dt_wedding = DesignType(name="Wedding / Event Floral", design_fee_percentage=30.0, workspace_id=workspace_id)
        dt_sympathy = DesignType(name="Sympathy / Funeral Spray", design_fee_percentage=25.0, workspace_id=workspace_id)
        db.session.add_all([dt_everyday, dt_wedding, dt_sympathy])
        db.session.commit()

        # 4. Add Ingredients (using cost per package & package quantity)
        i_rose = Ingredient(
            name="Ecuadorian Rose",
            workspace_id=workspace_id,
            cost_per_pkg=35.00,
            qty_per_pkg=25.0,
            ingredient_type_id=it_flower.id,
            vendor_id=v_dutch.id
        )
        i_salal = Ingredient(
            name="Salal",
            workspace_id=workspace_id,
            cost_per_pkg=85.00,
            qty_per_pkg=400.0,
            ingredient_type_id=it_green.id,
            vendor_id=v_local.id
        )
        i_vase = Ingredient(
            name="Ginger Vase",
            workspace_id=workspace_id,
            cost_per_pkg=3.50,
            qty_per_pkg=1.0,
            ingredient_type_id=it_supply.id,
            vendor_id=v_local.id
        )
        db.session.add_all([i_rose, i_salal, i_vase])
        db.session.commit()

        # 5. Add Sample Product Recipe
        product = Product(
            name="Classic Red Rose Arrangement",
            workspace_id=workspace_id,
            product_code="ARR-001",
            design_type_id=dt_everyday.id,
            actual_price=84.99
        )
        db.session.add(product)
        db.session.commit()

        # 6. Add Recipe Items (12 Roses, 3 Eucalyptus, 1 Vase)
        pi1 = ProductIngredient(product_id=product.id, ingredient_id=i_rose.id, quantity=12, workspace_id=workspace_id)
        pi2 = ProductIngredient(product_id=product.id, ingredient_id=i_salal.id, quantity=10, workspace_id=workspace_id)
        pi3 = ProductIngredient(product_id=product.id, ingredient_id=i_vase.id, quantity=1, workspace_id=workspace_id)
        db.session.add_all([pi1, pi2, pi3])
        db.session.commit()

        print("Database seeded successfully!\n")

        # Test calculation printouts
        print(f"--- Calculation Test: '{product.name}' ---")
        print(f"Raw Wholesale Cost:      ${product.raw_wholesale_cost:.2f}")
        print(f"Marked Up Cost:          ${product.marked_up_cost:.2f}")
        print(f"Design Fee (20%):        ${product.design_fee:.2f}")
        print(f"Suggested Retail Price:  ${product.suggested_retail_price:.2f}")
        print(f"Calculated Margin:       {product.profit_margin_percentage:.1f}%")

if __name__ == '__main__':
        seed_database()