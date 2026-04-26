from fastapi import APIRouter, HTTPException
from passlib.context import CryptContext
import database
from auth import create_access_token
from models import RegisterRequest, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/register", response_model=TokenResponse)
def register(data: RegisterRequest):
    if database.get_user_by_email(data.email):
        raise HTTPException(status_code=400, detail="Email already registered.")

    hashed = pwd_context.hash(data.password)
    user   = database.create_user(data.email, hashed)

    token  = create_access_token(user["id"], user["email"])
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest):
    user = database.get_user_by_email(data.email)

    if not user or not pwd_context.verify(data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token(user["id"], user["email"])
    return TokenResponse(access_token=token)