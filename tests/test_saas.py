import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "test-only-secret")

from app import create_app
from extensions import db
import models


class SaaSTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-only-secret",
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "WTF_CSRF_ENABLED": False,
                "STRIPE_SECRET_KEY": "sk_test",
                "STRIPE_PRICE_ID": "price_test",
                "STRIPE_WEBHOOK_SECRET": "whsec_test",
            }
        )
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def create_account(self, client, email, workspace):
        response = client.post(
            "/signup",
            data={
                "workspace_name": workspace,
                "email": email,
                "password": "a-long-test-password",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/billing/status")
        with self.app.app_context():
            user = models.User.query.filter_by(email=email).one()
            subscription = user.workspace.subscription
            self.assertEqual(subscription.status, "incomplete")
            subscription.status = "active"
            db.session.commit()
            return user.workspace_id

    def test_signup_creates_independent_workspace_and_login(self):
        workspace_id = self.create_account(self.client, "owner@example.test", "Petal Studio")
        with self.app.app_context():
            user = models.User.query.filter_by(email="owner@example.test").one()
            self.assertEqual(user.workspace_id, workspace_id)
            self.assertNotEqual(user.password_hash, "a-long-test-password")
            self.assertEqual(
                models.IngredientType.query.filter_by(workspace_id=workspace_id).count(),
                4,
            )
            type_id = models.IngredientType.query.filter_by(
                workspace_id=workspace_id
            ).first().id
        self.client.post(
            "/ingredients",
            data={
                "action": "create_ingredient",
                "name": "Test Rose",
                "cost_per_pkg": "32",
                "qty_per_pkg": "25",
                "ingredient_type_id": str(type_id),
                "vendor_id": "",
            },
        )

        response = self.client.get("/ingredients")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"ingredient-edit-form", response.data)
        css = self.client.get("/static/css/main.css")
        self.assertIn(b"grid-column-end: -1", css.get_data())
        css.close()

        self.client.post("/logout")
        response = self.client.post(
            "/login",
            data={"email": "owner@example.test", "password": "a-long-test-password"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/billing/status")

    def test_unpaid_workspace_is_redirected_to_billing(self):
        response = self.client.post(
            "/signup",
            data={
                "workspace_name": "New Florist",
                "email": "new@example.test",
                "password": "a-long-test-password",
            },
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/billing/status")

    def test_mutating_requests_require_csrf_tokens(self):
        self.app.config["WTF_CSRF_ENABLED"] = True
        response = self.client.post(
            "/signup",
            data={
                "workspace_name": "Missing Token Florist",
                "email": "missing-token@example.test",
                "password": "a-long-test-password",
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_workspace_records_cannot_be_read_or_edited_by_another_workspace(self):
        first_workspace = self.create_account(
            self.client, "first@example.test", "First Florist"
        )
        with self.app.app_context():
            first_type_id = models.IngredientType.query.filter_by(
                workspace_id=first_workspace
            ).first().id
        self.client.post("/vendors", data={"action": "create_vendor", "name": "First Vendor"})
        with self.app.app_context():
            first_vendor = models.Vendor.query.filter_by(
                workspace_id=first_workspace
            ).one()
            first_vendor_id = first_vendor.id

        self.client.post("/logout")
        second_client = self.app.test_client()
        second_workspace = self.create_account(
            second_client, "second@example.test", "Second Florist"
        )
        self.assertNotEqual(first_workspace, second_workspace)

        response = second_client.get(f"/vendors/{first_vendor_id}/inventory")
        self.assertEqual(response.status_code, 404)

        second_client.post(
            "/vendors",
            data={
                "action": "edit_vendor",
                "vendor_id": str(first_vendor_id),
                "name": "Hijacked Vendor",
            },
        )
        response = second_client.post(
            "/ingredients",
            data={
                "action": "create_ingredient",
                "name": "Foreign Rose",
                "cost_per_pkg": "20",
                "qty_per_pkg": "10",
                "ingredient_type_id": str(first_type_id),
                "vendor_id": "",
            },
        )
        self.assertEqual(response.status_code, 404)

        with self.app.app_context():
            first_vendor = db.session.get(models.Vendor, first_vendor_id)
            self.assertEqual(first_vendor.name, "First Vendor")
            self.assertEqual(
                models.Ingredient.query.filter_by(workspace_id=second_workspace).count(),
                0,
            )

    def test_signed_stripe_webhook_updates_subscription_idempotently(self):
        workspace_id = self.create_account(
            self.client, "billing@example.test", "Billing Florist"
        )
        event = {
            "id": "evt_subscription_change",
            "created": 100,
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_123",
                    "customer": "cus_123",
                    "status": "active",
                    "metadata": {"workspace_id": str(workspace_id)},
                }
            },
        }
        with patch("routes.billing.stripe.Webhook.construct_event", return_value=event):
            response = self.client.post(
                "/billing/webhook",
                data=b"signed-event",
                headers={"Stripe-Signature": "test-signature"},
            )
        self.assertEqual(response.status_code, 200)

        duplicate = {
            **event,
            "data": {
                "object": {
                    **event["data"]["object"],
                    "status": "canceled",
                }
            },
        }
        with patch("routes.billing.stripe.Webhook.construct_event", return_value=duplicate):
            response = self.client.post(
                "/billing/webhook",
                data=b"same-event",
                headers={"Stripe-Signature": "test-signature"},
            )
        self.assertEqual(response.status_code, 200)
        stale_event = {
            **event,
            "id": "evt_stale_subscription_change",
            "created": 99,
            "data": {
                "object": {
                    **event["data"]["object"],
                    "status": "canceled",
                }
            },
        }
        with patch("routes.billing.stripe.Webhook.construct_event", return_value=stale_event):
            response = self.client.post(
                "/billing/webhook",
                data=b"stale-event",
                headers={"Stripe-Signature": "test-signature"},
            )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            subscription = models.Subscription.query.filter_by(
                workspace_id=workspace_id
            ).one()
            self.assertEqual(subscription.status, "active")
            self.assertEqual(subscription.stripe_subscription_id, "sub_123")


if __name__ == "__main__":
    unittest.main()
