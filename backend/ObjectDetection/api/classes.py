from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List
from Common.shared_utils import logger, get_db_connection
from Common.api.auth import get_current_user

router = APIRouter(prefix="/classes", tags=["classes"])

@router.get("/", response_model=List[dict])
async def list_classes(user_id: int = Depends(get_current_user)):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM classes ORDER BY id")
            rows = cur.fetchall()
    return [{"id": r["id"], "name": r["name"]} for r in rows]

@router.get("/{class_id}", response_model=dict)
async def get_class(class_id: int, user_id: int = Depends(get_current_user)):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM classes WHERE id=%s", (class_id,))
            row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Class not found")
    return {"id": row["id"], "name": row["name"]}

@router.put("/{class_id}", response_model=dict)
async def update_class(
    class_id: int,
    name: str = Body(..., embed=True),
    user_id: int = Depends(get_current_user),
):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE classes SET name=%s WHERE id=%s", (name, class_id))
            if cur.rowcount == 0:
                raise HTTPException(404, "Class not found")
            conn.commit()
    return {"id": class_id, "name": name}

@router.post("/bulk", response_model=List[dict])
async def bulk_update_classes(
    names: List[str] = Body(...),
    user_id: int = Depends(get_current_user),
):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM classes")
            expected = cur.fetchone()[0]
            if len(names) != expected:
                raise HTTPException(400, f"Expected {expected} names, got {len(names)}")
            for idx, nm in enumerate(names):
                cur.execute(
                  "UPDATE classes SET name=%s WHERE id=%s",
                  (nm, idx)
                )
            conn.commit()

            cur.execute("SELECT id, name FROM classes ORDER BY id")
            rows = cur.fetchall()

    return [{"id": r["id"], "name": r["name"]} for r in rows]