import aiosqlite
from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.models import WakeHistoryResponse

router = APIRouter()


@router.get("", response_model=list[WakeHistoryResponse])
async def list_history(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute(
        "SELECT * FROM wake_history ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ) as cursor:
        rows = await cursor.fetchall()
        return [
            WakeHistoryResponse(
                id=r[0],
                machine_id=r[1],
                machine_name=r[2],
                mac_address=r[3],
                status=r[4],
                message=r[5] or "",
                created_at=r[6],
            )
            for r in rows
        ]


@router.get("/count")
async def history_count(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT COUNT(*) FROM wake_history") as cursor:
        row = await cursor.fetchone()
        return {"count": row[0]}


@router.delete("")
async def clear_history(db: aiosqlite.Connection = Depends(get_db)):
    await db.execute("DELETE FROM wake_history")
    await db.commit()
    return {"message": "历史记录已清除"}
