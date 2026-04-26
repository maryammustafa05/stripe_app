from fastapi import APIRouter, Request, HTTPException
import stripe
import os
from dotenv import load_dotenv
import database

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

router = APIRouter(tags=["Webhook"])


@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    event_type = event["type"]
    data_obj   = event["data"]["object"]

    def safe_get(obj, key, default=None):
        try:
            return obj[key]
        except (KeyError, TypeError):
            return default

    if event_type == "invoice.payment_succeeded":
        subscription_id = safe_get(data_obj, "subscription")
        if subscription_id:
            sub = stripe.Subscription.retrieve(subscription_id)
            database.update_subscription_status(
                stripe_subscription_id=subscription_id,
                status=sub.status,
                current_period_start=sub.current_period_start,
                current_period_end=sub.current_period_end,
                cancel_at_period_end=sub.cancel_at_period_end,
            )

    elif event_type == "invoice.payment_failed":
        subscription_id = safe_get(data_obj, "subscription")
        if subscription_id:
            database.update_subscription_status(
                stripe_subscription_id=subscription_id,
                status="past_due",
            )

    elif event_type == "customer.subscription.deleted":
        database.update_subscription_status(
            stripe_subscription_id=safe_get(data_obj, "id"),
            status="canceled",
        )

    elif event_type == "customer.subscription.updated":
        database.update_subscription_status(
            stripe_subscription_id=safe_get(data_obj, "id"),
            status=safe_get(data_obj, "status"),
            current_period_start=safe_get(data_obj, "current_period_start"),
            current_period_end=safe_get(data_obj, "current_period_end"),
            cancel_at_period_end=safe_get(data_obj, "cancel_at_period_end", False),
        )

    elif event_type == "customer.subscription.trial_will_end":
        pass

    return {"status": "ok"}