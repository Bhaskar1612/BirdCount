from fastapi import APIRouter, Depends, HTTPException
from Common.shared_utils import get_db_connection
from .auth import get_current_admin

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/users")
async def list_all_users(
    admin_id: int = Depends(get_current_admin)
):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, email, is_admin, created_at FROM users"
            )
            rows = cur.fetchall()
    return [
        {"id": r[0], "username": r[1], "email": r[2], "is_admin": r[3], "created_at": r[4]}
        for r in rows
    ]
