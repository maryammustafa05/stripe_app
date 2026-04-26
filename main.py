from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import payments, webhooks, auth

app = FastAPI(
    title="Stripe Subscriptions API",
    description="FastAPI + Stripe + SqlServer",
)
#for passing frontend url using cors
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace * with your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(payments.router)
app.include_router(webhooks.router)
@app.get("/")
def root():
    return {"message": "Stripe Subscription API is running."}