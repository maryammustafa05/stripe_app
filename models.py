from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# ─── Auth ─────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ─── Payments ─────────────────────────────────────────────────

class SubscribeRequest(BaseModel):
    price_id: str           # Stripe Price ID e.g. price_1ABC123...
    payment_method_id: str  # From Stripe.js on frontend e.g. pm_1ABC123...

class SubscriptionResponse(BaseModel):
    subscription_id: str
    status: str
    current_period_end: Optional[datetime]
    cancel_at_period_end: bool

class CancelRequest(BaseModel):
    # If True: cancels at end of billing period (recommended)
    # If False: cancels immediately
    at_period_end: bool = True