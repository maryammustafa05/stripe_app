from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
import stripe
import os
from dotenv import load_dotenv

import database
from auth import get_current_user
from models import SubscribeRequest, SubscriptionResponse, CancelRequest

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

router = APIRouter(prefix="/payments", tags=["Payments"])


def get_or_create_stripe_customer(user: dict) -> str:
    if user.get("stripe_customer_id"):
        return user["stripe_customer_id"]
    customer = stripe.Customer.create(email=user["email"])
    database.update_user_stripe_customer(user["id"], customer.id)
    return customer.id


def unix_to_dt(timestamp):
    """Convert Unix timestamp to datetime for response"""
    if not timestamp:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


@router.post("/subscribe", response_model=SubscriptionResponse)
def subscribe(data: SubscribeRequest, user=Depends(get_current_user)):

    existing = database.get_subscription_by_user(user["id"])
    if existing and existing["status"] in ("active", "trialing"):
        raise HTTPException(status_code=400, detail="You already have an active subscription.")

    try:
        customer_id = get_or_create_stripe_customer(user)

        stripe.PaymentMethod.attach(data.payment_method_id, customer=customer_id)
        stripe.Customer.modify(
            customer_id,
            invoice_settings={"default_payment_method": data.payment_method_id}
        )

        # Create subscription
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": data.price_id}],
            payment_behavior="allow_incomplete",
            expand=["latest_invoice.payment_intent"],
        )

        # Retrieve full object to guarantee all fields exist
        full_sub = stripe.Subscription.retrieve(subscription.id)
        sub_dict = full_sub.to_dict()

        period_start = sub_dict.get("current_period_start")
        period_end   = sub_dict.get("current_period_end")

        print(">>> period_start:", period_start)
        print(">>> period_end:", period_end)

        database.create_subscription(
            user_id=user["id"],
            stripe_subscription_id=subscription.id,
            stripe_customer_id=customer_id,
            price_id=data.price_id,
            status=full_sub.status,
            current_period_start=period_start,
            current_period_end=period_end,
        )

        return SubscriptionResponse(
            subscription_id=subscription.id,
            status=full_sub.status,
            current_period_end=unix_to_dt(period_end),
            cancel_at_period_end=sub_dict.get("cancel_at_period_end", False),
        )

    except stripe.error.CardError as e:
        raise HTTPException(status_code=402, detail=str(e.user_message))
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")


@router.get("/subscription", response_model=SubscriptionResponse)
def get_subscription(user=Depends(get_current_user)):
    sub = database.get_subscription_by_user(user["id"])
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription found.")

    return SubscriptionResponse(
        subscription_id=sub["stripe_subscription_id"],
        status=sub["status"],
        current_period_end=sub["current_period_end"],
        cancel_at_period_end=bool(sub["cancel_at_period_end"]),
    )


@router.post("/cancel")
def cancel_subscription(data: CancelRequest, user=Depends(get_current_user)):
    sub = database.get_subscription_by_user(user["id"])
    if not sub or sub["status"] == "canceled":
        raise HTTPException(status_code=404, detail="No active subscription found.")

    try:
        if data.at_period_end:
            updated = stripe.Subscription.modify(
                sub["stripe_subscription_id"],
                cancel_at_period_end=True
            )
            database.update_subscription_status(
                sub["stripe_subscription_id"],
                status=updated.status,
                cancel_at_period_end=True
            )
            return {"message": "Subscription will cancel at period end."}
        else:
            stripe.Subscription.delete(sub["stripe_subscription_id"])
            database.update_subscription_status(
                sub["stripe_subscription_id"],
                status="canceled"
            )
            return {"message": "Subscription canceled immediately."}

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")


@router.post("/resume")
def resume_subscription(user=Depends(get_current_user)):
    sub = database.get_subscription_by_user(user["id"])
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription found.")

    if not sub["cancel_at_period_end"]:
        raise HTTPException(status_code=400, detail="Subscription is not scheduled for cancellation.")

    try:
        updated = stripe.Subscription.modify(
            sub["stripe_subscription_id"],
            cancel_at_period_end=False
        )
        database.update_subscription_status(
            sub["stripe_subscription_id"],
            status=updated.status,
            cancel_at_period_end=False
        )
        return {"message": "Subscription resumed successfully."}

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")