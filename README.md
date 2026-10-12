# Floral Recipe & Cost Management App

A Flask-based web application designed for retail florists to manage stem inventory, construct arrangement recipes, automatically calculate wholesale costs, apply category markups and labor fees, and generate suggested retail prices (SRP).

The application supports florist workspaces with separate users, inventory, products, recipes, and subscription status.

---

## 🛠️ Tech Stack

* **Backend:** Python 3.12, Flask, Flask-SQLAlchemy (SQLite locally; PostgreSQL in production)
* **Frontend:** Jinja2 Templates, Vanilla JavaScript, Tom-Select (Searchable Dropdowns)
* **Styling:** SCSS source with checked-in compiled CSS

---

## 🗄️ Database Architecture

Every florist-owned record has a `workspace_id`; database relationships and route queries are scoped to the logged-in user's workspace. Billing belongs to a workspace so staff accounts can be added later without changing ownership. The core models are:

1. **`Workspace`**: One florist business and its owned data.
2. **`User`**: Email and password hash, associated with a workspace.
3. **`Subscription`**: Workspace billing status and Stripe identifiers.
4. **`Vendor`**: Supplier information (`id`, `workspace_id`, `name`).
5. **`IngredientType`**: Category markups (`id`, `workspace_id`, `name`, `markup` multiplier).
6. **`DesignType`**: Labor/design style fees (`id`, `workspace_id`, `name`, `design_fee_percentage`).
7. **`Ingredient`**: Stems and supplies scoped to a workspace, type, and optional vendor.
   * *Calculated:* Unit Cost = `cost_per_pkg / qty_per_pkg`
8. **`Product`**: Arrangement bases scoped to a workspace and design type.
   * *Calculated Metrics:* Raw Wholesale Cost, Marked-Up Cost, Design Fee, Suggested Retail Price (SRP), Profit Margin %.
9. **`ProductIngredient`**: Workspace-scoped product recipe rows.

## Running locally

Use Python 3.12 and install the dependencies:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
flask --app app db upgrade
flask --app app run --debug
```

New accounts start with their own empty workspace and default flower/design categories. Signup uses email and a password (minimum 12 characters); it does not import the removed personal spreadsheets. Run database migrations before starting the server; the app intentionally does not create or alter production tables at startup.

The app serves the checked-in `static/css/main.css` directly; it does not compile SCSS at runtime.

## Stripe subscriptions

Create a recurring Stripe Price, then configure:

```text
STRIPE_SECRET_KEY
STRIPE_PRICE_ID
STRIPE_WEBHOOK_SECRET
```

Set the Stripe webhook endpoint to `https://<your-domain>/billing/webhook` and subscribe to:

* `checkout.session.completed`
* `customer.subscription.created`
* `customer.subscription.updated`
* `customer.subscription.deleted`

Checkout activation and cancellation are driven by signed webhook events, not by the browser's success redirect. The billing portal is used for payment method and cancellation management. Use HTTPS and test-mode Stripe credentials before enabling live billing.

## Deployment checklist

* Set a strong, stable `SECRET_KEY`, `SESSION_COOKIE_SECURE=1`, and PostgreSQL `DATABASE_URL`.
* Keep Stripe credentials in the hosting provider's secret manager.
* Run `flask --app app db upgrade` during deployment and configure database backups.
* Serve behind HTTPS using Gunicorn (for example `gunicorn app:app`).
* Configure Stripe webhook delivery and test signup, payment, cancellation, and tenant isolation before launch.

This is a first subscription foundation: production launch should also include email verification, password reset email delivery, rate limiting, operational monitoring, and a tested data migration/backup plan for any old personal database.

---

## 🏗️ Project Structure

```text
floral-recipe-app/
├── app.py                 # Application factory, configuration, and access guard
├── extensions.py          # SQLAlchemy, login, migration, and CSRF extensions
├── models.py              # Workspace, account, billing, and inventory models
├── migrations/            # Alembic schema migrations
├── static/
│   ├── css/
│   │   └── main.css       # Compiled CSS
│   └── scss/
│   └── main.scss          # SCSS source for the checked-in stylesheet
├── templates/             # Jinja2 template views
│   ├── base.html
│   ├── billing.html
│   ├── login.html
│   ├── signup.html
│   ├── index.html
│   ├── products.html
│   ├── ingredients.html
│   ├── vendors.html
│   ├── ingredient_types.html
│   ├── design_fees.html
│   └── temp_calculator.html
└── routes/                # Modular Flask Blueprints
    ├── __init__.py
    ├── auth.py
    ├── billing.py
    ├── ingredients.py
    ├── products.py
    ├── vendors.py
    ├── ingredient_types.py
    ├── design_fees.py
    └── quick_calculator.py