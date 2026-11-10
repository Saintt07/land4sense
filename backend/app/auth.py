
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash

from app import config, db

password_hash = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_access_token(user_id: int) -> str:
    if not config.SECRET_KEY:
        raise RuntimeError("SECRET_KEY is not configured")

    expires = datetime.now(timezone.utc) + timedelta(
        minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "exp": expires,
    }

    return jwt.encode(payload, config.SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn=Depends(db.get_db),
):
    if credentials is None:
        raise HTTPException(401, "Authentication required")

    if not config.SECRET_KEY:
        raise HTTPException(500, "Authentication is not configured")

    try:
        payload = jwt.decode(
            credentials.credentials,
            config.SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise HTTPException(401, "Invalid or expired token")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT user_id, email, created_at FROM users WHERE user_id = %s",
            (user_id,),
        )
        user = cur.fetchone()

    if not user:
        raise HTTPException(401, "User not found")

    return user
