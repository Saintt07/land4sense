
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import auth, db, security

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class AuthRequest(BaseModel):
    email: str
    password: str


@router.post("/register", dependencies=[Depends(security.rate_limit)])
def register(data: AuthRequest, conn=Depends(db.get_db)):
    email = data.email.strip().lower()

    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, "Invalid email address")

    if len(data.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    with conn.cursor() as cur:
        cur.execute("SELECT user_id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            raise HTTPException(409, "Email is already registered")

        cur.execute(
            "INSERT INTO users (email, password_hash) VALUES (%s, %s)",
            (email, auth.hash_password(data.password)),
        )
        user_id = cur.lastrowid

    return {"status": "success", "message": "Account created", "user_id": user_id}


@router.post("/login", dependencies=[Depends(security.rate_limit)])
def login(data: AuthRequest, conn=Depends(db.get_db)):
    email = data.email.strip().lower()

    with conn.cursor() as cur:
        cur.execute(
            "SELECT user_id, email, password_hash FROM users WHERE email = %s",
            (email,),
        )
        user = cur.fetchone()

    if not user or not auth.verify_password(data.password, user["password_hash"]):
        raise HTTPException(401, "Incorrect email or password")

    token = auth.create_access_token(user["user_id"])

    return {
        "status": "success",
        "access_token": token,
        "token_type": "bearer",
    }


@router.get("/me")
def me(current_user=Depends(auth.get_current_user)):
    return {"status": "success", "user": current_user}
