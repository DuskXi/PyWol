import aiosqlite
from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.models import BatchWakeRequest
from app.wol import send_wol

router = APIRouter()


@router.post("/batch")
async def batch_wake(
    request: BatchWakeRequest, db: aiosqlite.Connection = Depends(get_db)
):
    if not request.machine_ids:
        raise HTTPException(status_code=400, detail="未指定设备")

    placeholders = ",".join("?" * len(request.machine_ids))
    async with db.execute(
        f"SELECT * FROM machines WHERE id IN ({placeholders})",
        request.machine_ids,
    ) as cursor:
        machines = await cursor.fetchall()

    if not machines:
        raise HTTPException(status_code=404, detail="未找到设备")

    results = []
    for m in machines:
        try:
            send_wol(m[2], m[4], m[5])
            await db.execute(
                "INSERT INTO wake_history (machine_id, machine_name, mac_address, status, message) VALUES (?,?,?,?,?)",
                (m[0], m[1], m[2], "success", "批量唤醒"),
            )
            results.append({"machine": m[1], "status": "success"})
        except Exception as e:
            await db.execute(
                "INSERT INTO wake_history (machine_id, machine_name, mac_address, status, message) VALUES (?,?,?,?,?)",
                (m[0], m[1], m[2], "failed", str(e)),
            )
            results.append({"machine": m[1], "status": "failed", "error": str(e)})
    await db.commit()
    return {"message": "批量唤醒完成", "results": results}
