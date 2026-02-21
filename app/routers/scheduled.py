from datetime import datetime

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.models import ScheduledTaskCreate, ScheduledTaskResponse, ScheduledTaskUpdate
from app.scheduler import add_scheduled_task, remove_scheduled_task

router = APIRouter()


async def _resolve_target_name(db: aiosqlite.Connection, target_type: str, target_id: int) -> str:
    table = "machines" if target_type == "machine" else "groups"
    async with db.execute(f"SELECT name FROM {table} WHERE id = ?", (target_id,)) as c:
        t = await c.fetchone()
        return t[0] if t else "未知"


@router.get("", response_model=list[ScheduledTaskResponse])
async def list_scheduled_tasks(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute(
        "SELECT * FROM scheduled_tasks ORDER BY created_at DESC"
    ) as cursor:
        rows = await cursor.fetchall()

    result = []
    for r in rows:
        target_name = await _resolve_target_name(db, r[4], r[5])
        result.append(
            ScheduledTaskResponse(
                id=r[0],
                name=r[1],
                cron_expression=r[2] or "",
                scheduled_time=r[3] or "",
                target_type=r[4],
                target_id=r[5],
                target_name=target_name,
                enabled=bool(r[6]),
                created_at=r[7],
                updated_at=r[8],
            )
        )
    return result


@router.post("", response_model=ScheduledTaskResponse)
async def create_scheduled_task(
    task: ScheduledTaskCreate, db: aiosqlite.Connection = Depends(get_db)
):
    now = datetime.now().isoformat()
    async with db.execute(
        "INSERT INTO scheduled_tasks (name, cron_expression, scheduled_time, target_type, target_id, enabled, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
        (
            task.name,
            task.cron_expression,
            task.scheduled_time,
            task.target_type,
            task.target_id,
            1 if task.enabled else 0,
            now,
            now,
        ),
    ) as cursor:
        task_id = cursor.lastrowid
    await db.commit()

    if task.enabled:
        await add_scheduled_task(task_id, task)

    target_name = await _resolve_target_name(db, task.target_type, task.target_id)
    return ScheduledTaskResponse(
        id=task_id,
        name=task.name,
        cron_expression=task.cron_expression,
        scheduled_time=task.scheduled_time,
        target_type=task.target_type,
        target_id=task.target_id,
        target_name=target_name,
        enabled=task.enabled,
        created_at=now,
        updated_at=now,
    )


@router.put("/{task_id}", response_model=ScheduledTaskResponse)
async def update_scheduled_task(
    task_id: int,
    task: ScheduledTaskUpdate,
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute(
        "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)
    ) as cursor:
        existing = await cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Task not found")

    data = task.model_dump(exclude_unset=True)
    if data:
        fields = []
        values = []
        for k, v in data.items():
            fields.append(f"{k} = ?")
            values.append((1 if v else 0) if k == "enabled" else v)
        fields.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(task_id)
        await db.execute(
            f"UPDATE scheduled_tasks SET {', '.join(fields)} WHERE id = ?", values
        )
        await db.commit()

    async with db.execute(
        "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)
    ) as cursor:
        row = await cursor.fetchone()

    # Update scheduler
    await remove_scheduled_task(task_id)
    if row[6]:  # enabled
        task_data = ScheduledTaskCreate(
            name=row[1],
            cron_expression=row[2] or "",
            scheduled_time=row[3] or "",
            target_type=row[4],
            target_id=row[5],
            enabled=bool(row[6]),
        )
        await add_scheduled_task(task_id, task_data)

    target_name = await _resolve_target_name(db, row[4], row[5])
    return ScheduledTaskResponse(
        id=row[0],
        name=row[1],
        cron_expression=row[2] or "",
        scheduled_time=row[3] or "",
        target_type=row[4],
        target_id=row[5],
        target_name=target_name,
        enabled=bool(row[6]),
        created_at=row[7],
        updated_at=row[8],
    )


@router.delete("/{task_id}")
async def delete_scheduled_task(
    task_id: int, db: aiosqlite.Connection = Depends(get_db)
):
    async with db.execute(
        "SELECT id FROM scheduled_tasks WHERE id = ?", (task_id,)
    ) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Task not found")
    await remove_scheduled_task(task_id)
    await db.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
    await db.commit()
    return {"message": "定时任务已删除"}
