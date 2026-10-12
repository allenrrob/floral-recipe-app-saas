import stripe
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from extensions import csrf, db
import models

billing_bp = Blueprint("billing", __name__, url_prefix="/billing")


def _stripe_ready(require_price=False, require_webhook=False):
    configured = current_app.config.get("STRIPE_SECRET_KEY")
    if require_price:
        configured = configured and current_app.config.get("STRIPE_PRICE_ID")
    if require_webhook:
        configured = configured and current_app.config.get("STRIPE_WEBHOOK_SECRET")
    return bool(configured)


@billing_bp.route("/status")
def status():
    return render_template(
        "billing.html",
        workspace=current_user.workspace,
        subscription=current_user.workspace.subscription,
        checkout_configured=_stripe_ready(require_price=True),
        portal_configured=_stripe_ready(),
    )


@billing_bp.route("/checkout", methods=["POST"])
def checkout():
    subscription = current_user.workspace.subscription
    if subscription and (subscription.is_active or subscription.stripe_customer_id):
        return redirect(url_for("billing.status"))
    if not _stripe_ready(require_price=True):
        flash("Billing is not configured yet. Please try again later.", "error")
        return redirect(url_for("billing.status"))

    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    try:
        checkout_session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": current_app.config["STRIPE_PRICE_ID"], "quantity": 1}],
            customer_email=current_user.email,
            client_reference_id=str(current_user.workspace_id),
            subscription_data={"metadata": {"workspace_id": str(current_user.workspace_id)}},
            success_url=url_for("billing.success", _external=True),
            cancel_url=url_for("billing.status", _external=True),
        )
    except stripe.StripeError:
        current_app.logger.exception("Stripe Checkout session creation failed")
        flash("We couldn't start checkout. Please try again.", "error")
        return redirect(url_for("billing.status"))

    return redirect(checkout_session.url, code=303)


@billing_bp.route("/success")
def success():
    flash("Payment submitted. Your workspace will be available once Stripe confirms your subscription.", "info")
    return redirect(url_for("billing.status"))


@billing_bp.route("/portal", methods=["POST"])
def portal():
    subscription = current_user.workspace.subscription
    if not _stripe_ready() or not subscription or not subscription.stripe_customer_id:
        flash("No billing account is available yet.", "error")
        return redirect(url_for("billing.status"))

    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=url_for("billing.status", _external=True),
        )
    except stripe.StripeError:
        current_app.logger.exception("Stripe billing portal session creation failed")
        flash("We couldn't open billing management. Please try again.", "error")
        return redirect(url_for("billing.status"))

    return redirect(portal_session.url, code=303)


@billing_bp.route("/webhook", methods=["POST"])
@csrf.exempt
def webhook():
    if not _stripe_ready(require_webhook=True):
        abort(503, description="Stripe webhooks are not configured.")

    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    try:
        event = stripe.Webhook.construct_event(
            request.get_data(),
            request.headers.get("Stripe-Signature", ""),
            current_app.config["STRIPE_WEBHOOK_SECRET"],
        )
    except (ValueError, stripe.SignatureVerificationError):
        abort(400, description="Invalid Stripe webhook signature or payload.")

    if db.session.get(models.StripeWebhookEvent, event["id"]):
        return "", 200

    event_type = event["type"]
    data = event["data"]["object"]
    if event_type == "checkout.session.completed":
        workspace_id = data.get("client_reference_id")
        subscription = (
            models.Subscription.query.filter_by(workspace_id=int(workspace_id)).first()
            if workspace_id and str(workspace_id).isdigit()
            else None
        )
        if subscription:
            subscription.stripe_customer_id = data.get("customer")
            subscription.stripe_subscription_id = data.get("subscription")
    elif event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        workspace_id = data.get("metadata", {}).get("workspace_id")
        subscription = (
            models.Subscription.query.filter_by(workspace_id=int(workspace_id)).first()
            if workspace_id and str(workspace_id).isdigit()
            else None
        )
        event_created = int(event["created"])
        if subscription and (
            subscription.stripe_event_created is None
            or event_created >= subscription.stripe_event_created
        ):
            subscription.stripe_customer_id = data.get("customer")
            subscription.stripe_subscription_id = data.get("id")
            subscription.status = data.get("status", "canceled")
            subscription.stripe_event_created = event_created

    db.session.add(models.StripeWebhookEvent(event_id=event["id"]))
    db.session.commit()
    return "", 200
