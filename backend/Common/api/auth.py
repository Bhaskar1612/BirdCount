import re
import datetime
import os
import jwt
import asyncio
import random
import string
from fastapi import APIRouter, HTTPException, Depends, Response, Request, Form
from fastapi.security import OAuth2PasswordRequestForm
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN
from fastapi.responses import JSONResponse
from Common.shared_utils import logger, get_db_connection
import bcrypt
import httpx
from typing import Optional
import coolname

router = APIRouter()
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise Exception("JWT_SECRET_KEY not found in environment variables.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")

def generate_guest_username():
    try:
        name_parts = coolname.generate_slug(2)
        base_name = name_parts.replace('-', '_')

        num = random.randint(1000, 9999)
        return f"{base_name}_{num}"
    except Exception as e:
        logger.error(f"Error generating guest username with coolname: {e}")
        word1 = "guest"
        word2 = "user"
        num = random.randint(1000, 9999)
        return f"{word1}_{word2}_{num}"

def generate_random_password(length=12):
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choice(characters) for i in range(length))
    return password

def create_access_token(data: dict, expires_delta: datetime.timedelta = None):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + (
        expires_delta if expires_delta else datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def verify_recaptcha(captcha_value: str):
    url = "https://www.google.com/recaptcha/api/siteverify"
    payload = {
        "secret": RECAPTCHA_SECRET_KEY,
        "response": captcha_value,
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=payload)
        response_json = response.json()
        return response_json.get("success", False)

@router.post("/token")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    captcha_value: str = Form(...),
):
    username = form_data.username
    password = form_data.password

    is_valid_captcha = await verify_recaptcha(captcha_value)
    if not is_valid_captcha:
        raise HTTPException(status_code=400, detail="Invalid reCAPTCHA")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, password_hash, is_admin FROM users WHERE username = %s",
                    (username,)
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
                user_id, hashed_password, is_admin = row
                if not bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8')):
                    raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
                access_token_data = {"sub": str(user_id), "admin": is_admin}
                access_token = create_access_token(data=access_token_data)
                response = Response(content="Login successful")
                response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", path="/")
                schedule_cleanup(user_id)
                return response
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


def get_current_user(
    request: Request
):
    token = request.cookies.get("access_token")
    if token is None:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return int(user_id)
    except jwt.PyJWTError as e:
        logger.error(f"JWT error: {e}")
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid token")

@router.post("/logout")
async def logout(
    request: Request,
    user_id: int = Depends(get_current_user)
):
    try:
        schedule_cleanup(user_id)

        try:
            from ReID.api.auto_truncate_utils import cleanup_non_consented_reid_data
            cleanup_non_consented_reid_data()
            logger.info(f"Cleaned up non-consented ReID data for user {user_id} during logout.")
        except ImportError:
            logger.warning("ReID cleanup module (auto_truncate_utils) not found. Skipping ReID cleanup.")
        except Exception as e:
            logger.error(f"Error during ReID data cleanup for user {user_id}: {e}")

    except Exception as e:
        logger.error(f"General error during logout cleanup phase for user {user_id}: {e}")

    response = Response(status_code=204)
    response.delete_cookie("access_token", path="/")
    return response

@router.get("/protected")
async def protected(
    user_id: int = Depends(get_current_user)
):
    return {"message": f"Hello user {user_id}"}

@router.post("/guest")
async def login_guest(
    request: Request,
    captcha_value: str = Form(...)
):
    is_valid_captcha = await verify_recaptcha(captcha_value)
    if not is_valid_captcha:
        raise HTTPException(status_code=400, detail="Invalid reCAPTCHA")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                while True:
                    guest_username = generate_guest_username()
                    cur.execute("SELECT id FROM users WHERE username = %s", (guest_username,))
                    if cur.fetchone() is None:
                        break

                guest_password = generate_random_password()
                hashed_password = bcrypt.hashpw(guest_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

                cur.execute('''INSERT INTO users
                            (username, is_guest, password_hash)
                            VALUES (%s, %s, %s)
                            RETURNING id''', (guest_username, True, hashed_password))
                user_id = cur.fetchone()[0]
                conn.commit()

                access_token_data = {"sub": str(user_id)}
                access_token = create_access_token(data=access_token_data)

                schedule_cleanup(user_id)

                response_body = {
                    "message": "Guest login successful. Save your credentials.",
                    "username": guest_username,
                    "password": guest_password
                }
                json_response = JSONResponse(content=response_body)
                json_response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", path="/")
                return json_response

    except Exception as e:
        logger.error(f"Guest login error: {e}")
        conn.rollback()
        raise HTTPException(status_code=500, detail="Internal server error during guest login.")

async def delayed_cleanup(user_id: int):
    await asyncio.sleep(ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    try:
        from ObjectDetection.api.cleanup import perform_cleanup  
        perform_cleanup(user_id)
        logger.info(f"Scheduled cleanup for user {user_id} completed successfully.")
    except Exception as e:
        logger.error(f"Error during scheduled cleanup for user {user_id}: {e}")

def schedule_cleanup(user_id: int):
    asyncio.create_task(delayed_cleanup(user_id))

@router.post("/signup")
async def signup(
    username: str = Form(...),
    email: Optional[str] = Form(None),
    password: str = Form(...),
    captcha_value: str = Form(...)
):
    is_valid_captcha = await verify_recaptcha(captcha_value)
    if not is_valid_captcha:
        raise HTTPException(status_code=400, detail="Invalid reCAPTCHA")

    username_regex = re.compile(r'^[A-Za-z0-9_]{3,20}$')
    if not username_regex.fullmatch(username):
        raise HTTPException(
            status_code=400,
            detail="Username must be 3-20 characters and contain only letters, numbers, and underscores."
        )

    if len(password) < 8 or len(password) > 20:
        raise HTTPException(status_code=400, detail="Password must be between 8 and 20 characters.")

    try:
        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    except Exception as e:
        logger.error(f"Password hashing failed: {e}")
        raise HTTPException(status_code=500, detail="Error processing password.")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (email, username, password_hash, is_guest) VALUES (%s, %s, %s, %s) RETURNING id",
                    (email, username, hashed_password, False)
                )
                new_user_id = cur.fetchone()[0]
                conn.commit()
    except Exception as e:
        logger.error(f"Signup error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during signup.")

    return {"message": "Signup successful. Please login."}

def get_current_admin(
    request: Request,
    user_id: int = Depends(get_current_user)
):
    token = request.cookies.get("access_token")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if not payload.get("admin", False):
            raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Admin privileges required")
    except jwt.PyJWTError:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user_id

@router.get("/me")
async def read_current_user(
    request: Request, 
    user_id: int = Depends(get_current_user)
):
    token = request.cookies.get("access_token")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"user_id": user_id, "is_admin": payload.get("admin", False)}
    except jwt.PyJWTError:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid token")