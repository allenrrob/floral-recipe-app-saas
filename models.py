from flask_login import UserMixin
from sqlalchemy import ForeignKeyConstraint, UniqueConstraint, and_
from extensions import db


class Workspace(db.Model):
    __tablename__ = "workspaces"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    users = db.relationship("User", backref="workspace", cascade="all, delete-orphan", lazy=True)
    subscription = db.relationship(
        "Subscription", backref="workspace", cascade="all, delete-orphan",
        uselist=False, lazy=True
    )
    def __repr__(self):
        return f"<Workspace {self.name}>"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    def __repr__(self):
        return f"<User {self.email}>"


class Subscription(db.Model):
    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(
        db.Integer, db.ForeignKey("workspaces.id"), nullable=False, unique=True
    )
    stripe_customer_id = db.Column(db.String(255), unique=True)
    stripe_subscription_id = db.Column(db.String(255), unique=True)
    status = db.Column(db.String(32), nullable=False, default="incomplete")
    stripe_event_created = db.Column(db.BigInteger)
    updated_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now(), onupdate=db.func.now()
    )

    @property
    def is_active(self):
        return self.status in {"active", "trialing"}


class StripeWebhookEvent(db.Model):
    __tablename__ = "stripe_webhook_events"

    event_id = db.Column(db.String(255), primary_key=True)
    received_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())


class Vendor(db.Model):
    __tablename__ = 'vendors'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)

    __table_args__ = (UniqueConstraint("workspace_id", "id"),)

    ingredients = db.relationship(
        "Ingredient",
        primaryjoin=lambda: and_(
            Vendor.id == Ingredient.vendor_id,
            Vendor.workspace_id == Ingredient.workspace_id,
        ),
        foreign_keys=lambda: [Ingredient.vendor_id],
        back_populates="vendor",
        lazy=True,
    )

    def __repr__(self):
        return f'<Vendor {self.name}>'

class IngredientType(db.Model):
    __tablename__ = 'ingredient_types'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)
    markup = db.Column(db.Float, default=4.0) # Multiplier

    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "name"),
    )

    ingredients = db.relationship(
        "Ingredient",
        primaryjoin=lambda: and_(
            IngredientType.id == Ingredient.ingredient_type_id,
            IngredientType.workspace_id == Ingredient.workspace_id,
        ),
        foreign_keys=lambda: [Ingredient.ingredient_type_id],
        back_populates="type_info",
        lazy=True,
    )

    def __repr__(self):
        return f'<IngredientType {self.name}>'

class DesignType(db.Model):
    __tablename__ = 'design_types'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)
    design_fee_percentage = db.Column(db.Float, default = 20.00)

    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "name"),
    )

    products = db.relationship(
        "Product",
        primaryjoin=lambda: and_(
            DesignType.id == Product.design_type_id,
            DesignType.workspace_id == Product.workspace_id,
        ),
        foreign_keys=lambda: [Product.design_type_id],
        back_populates="design_style",
        lazy=True,
    )

    def __repr__(self): 
        return f'<DesignType {self.name}>'

class Ingredient(db.Model):
    __tablename__ = 'ingredients'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    cost_per_pkg = db.Column(db.Float, nullable=False)
    qty_per_pkg = db.Column(db.Float, nullable=False)

    # Foreign Keys
    ingredient_type_id = db.Column(db.Integer, nullable=False)
    vendor_id = db.Column(db.Integer, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "ingredient_type_id"],
            ["ingredient_types.workspace_id", "ingredient_types.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "vendor_id"],
            ["vendors.workspace_id", "vendors.id"],
        ),
    )

    vendor = db.relationship(
        "Vendor",
        primaryjoin=lambda: and_(
            Vendor.id == Ingredient.vendor_id,
            Vendor.workspace_id == Ingredient.workspace_id,
        ),
        foreign_keys=[vendor_id],
        back_populates="ingredients",
    )
    type_info = db.relationship(
        "IngredientType",
        primaryjoin=lambda: and_(
            IngredientType.id == Ingredient.ingredient_type_id,
            IngredientType.workspace_id == Ingredient.workspace_id,
        ),
        foreign_keys=[ingredient_type_id],
        back_populates="ingredients",
    )
    recipe_rows = db.relationship(
        "ProductIngredient",
        primaryjoin=lambda: and_(
            Ingredient.id == ProductIngredient.ingredient_id,
            Ingredient.workspace_id == ProductIngredient.workspace_id,
        ),
        foreign_keys=lambda: [ProductIngredient.ingredient_id],
        back_populates="ingredient",
        lazy=True,
    )

    def __repr__(self):
        return f'<Ingredient {self.name}>'

class ProductIngredient(db.Model):
    __tablename__ = 'product_ingredients'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False, default=1.0)

    product_id = db.Column(db.Integer, nullable=False)
    ingredient_id = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "product_id"],
            ["products.workspace_id", "products.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "ingredient_id"],
            ["ingredients.workspace_id", "ingredients.id"],
        ),
    )

    ingredient = db.relationship(
        "Ingredient",
        primaryjoin=lambda: and_(
            Ingredient.id == ProductIngredient.ingredient_id,
            Ingredient.workspace_id == ProductIngredient.workspace_id,
        ),
        foreign_keys=[ingredient_id],
        back_populates="recipe_rows",
    )
    product = db.relationship(
        "Product",
        primaryjoin=lambda: and_(
            Product.id == ProductIngredient.product_id,
            Product.workspace_id == ProductIngredient.workspace_id,
        ),
        foreign_keys=[product_id],
        back_populates="recipe_items",
    )

    def __repr__(self):
        return f'<ProductIngredient {self.quantity} x {self.ingredient_id}>'


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    product_code = db.Column(db.String(20), nullable=False)
    image_url = db.Column(db.String(255), nullable=True)
    actual_price = db.Column(db.Float, nullable=True)

    # Foreign Keys
    design_type_id = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "product_code"),
        ForeignKeyConstraint(
            ["workspace_id", "design_type_id"],
            ["design_types.workspace_id", "design_types.id"],
        ),
    )

    recipe_items = db.relationship(
        "ProductIngredient",
        primaryjoin=lambda: and_(
            Product.id == ProductIngredient.product_id,
            Product.workspace_id == ProductIngredient.workspace_id,
        ),
        foreign_keys=lambda: [ProductIngredient.product_id],
        back_populates="product",
        cascade="all, delete-orphan",
        lazy=True,
    )
    design_style = db.relationship(
        "DesignType",
        primaryjoin=lambda: and_(
            DesignType.id == Product.design_type_id,
            DesignType.workspace_id == Product.workspace_id,
        ),
        foreign_keys=[design_type_id],
        back_populates="products",
    )

    @property
    def sorted_recipe_items(self):
        return sorted(
            self.recipe_items,
            key=lambda item: (
                item.ingredient.type_info.name.casefold()
                if item.ingredient.type_info
                else "",
                item.ingredient.name.casefold(),
            ),
        )

    def __repr__(self):
        return f'<Product {self.name}>'

    # --- Costing & Pricing Calculations ---
    @property
    def raw_wholesale_cost(self):
        """Calculates total raw/stem unit costs without markups."""
        return sum((item.ingredient.cost_per_pkg / item.ingredient.qty_per_pkg) * item.quantity for item in self.recipe_items)

    @property
    def marked_up_cost(self):
        """Calculates ingredient costs with ingredient-type markkups applied."""
        total = 0.0
        for item in self.recipe_items:
            markup = item.ingredient.type_info.markup if item.ingredient.type_info else 1.0
            total += ((item.ingredient.cost_per_pkg / item.ingredient.qty_per_pkg) * item.quantity) * markup
        return total

    @property
    def design_fee(self):
        """Calculates design fee based on the product's design type percentage."""
        fee_pct = self.design_style.design_fee_percentage if self.design_style else 0.0
        return self.marked_up_cost * (fee_pct / 100.00)

    @property
    def suggested_retail_price(self):
        """Calculates recommended retail price (Marked up cost + Design fee)."""
        return self.marked_up_cost + self.design_fee

    @property
    def profit_margin_percentage(self):
        """Calculates profit margin percentage based on suggested retail price"""
        effective_price = self.actual_price if self.actual_price and self.actual_price > 0 else self.suggested_retail_price

        if not effective_price or effective_price <= 0:
            return 0.0

        margin = ((effective_price - self.raw_wholesale_cost) / effective_price) * 100.0
        return max(margin, 0.0)