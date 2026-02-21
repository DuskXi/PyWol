from datetime import datetime

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.models import GroupCreate, GroupResponse, GroupUpdate, MachineResponse
from app.wol import send_wol

router = APIRouter()


def _row_to_group(row) -> GroupResponse:
    return GroupResponse(
        id=row[0],
        name=row[1],
        description=row[2] or "",
        created_at=row[3],
        updated_at=row[4],
        machine_count=row[5] if len(row) > 5 else 0,
    )


@router.get("", response_model=list[GroupResponse])
async def list_groups(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("""
        SELECT g.*, COUNT(m.id) as machine_count
        FROM groups g
        LEFT JOIN machines m ON g.id = m.group_id
        GROUP BY g.id
        ORDER BY g.name
    """) as cursor:
        rows = await cursor.fetchall()
        return [_row_to_group(r) for r in rows]


@router.post("", response_model=GroupResponse)
async def create_group(
    group: GroupCreate, db: aiosqlite.Connection = Depends(get_db)
):
    now = datetime.now().isoformat()
    try:
        async with db.execute(
            "INSERT INTO groups (name, description, created_at, updated_at) VALUES (?,?,?,?)",
            (group.name, group.description, now, now),
        ) as cursor:
            gid = cursor.lastrowid
        await db.commit()
    except aiosqlite.IntegrityError:
        raise HTTPException(status_code=400, detail="分组名称已存在")

    return GroupResponse(
        id=gid,
        name=group.name,
        description=group.description,
        created_at=now,
        updated_at=now,
        machine_count=0,
    )


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(group_id: int, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute(
        """
        SELECT g.*, COUNT(m.id) as machine_count
        FROM groups g
        LEFT JOIN machines m ON g.id = m.group_id
        WHERE g.id = ?
        GROUP BY g.id
        """,
        (group_id,),
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Group not found")
        return _row_to_group(row)


@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: int,
    group: GroupUpdate,
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute(
        "SELECT id FROM groups WHERE id = ?", (group_id,)
    ) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Group not found")

    data = group.model_dump(exclude_unset=True)
    if data:
        fields = [f"{k} = ?" for k in data]
        values = list(data.values())
        fields.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(group_id)
        try:
            await db.execute(
                f"UPDATE groups SET {', '.join(fields)} WHERE id = ?", values
            )
            await db.commit()
        except aiosqlite.IntegrityError:
            raise HTTPException(status_code=400, detail="分组名称已存在")
    return await get_group(group_id, db)


@router.delete("/{group_id}")
async def delete_group(group_id: int, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute(
        "SELECT id FROM groups WHERE id = ?", (group_id,)
    ) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Group not found")
    await db.execute(
        "UPDATE machines SET group_id = NULL WHERE group_id = ?", (group_id,)
    )
    await db.execute("DELETE FROM groups WHERE id = ?", (group_id,))
    await db.commit()
    return {"message": "Group deleted"}


@router.get("/{group_id}/machines", response_model=list[MachineResponse])
async def get_group_machines(
    group_id: int, db: aiosqlite.Connection = Depends(get_db)
):
    async with db.execute(
        "SELECT id FROM groups WHERE id = ?", (group_id,)
    ) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Group not found")
    async with db.execute(
        """SELECT m.*, g.name as group_name FROM machines m
           LEFT JOIN groups g ON m.group_id = g.id
           WHERE m.group_id = ? ORDER BY m.name""",
        (group_id,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [
            MachineResponse(
                id=r[0],
                name=r[1],
                mac_address=r[2],
                ip_address=r[3] or "",
                broadcast_address=r[4],
                port=r[5],
                group_id=r[6],
                created_at=r[7],
                updated_at=r[8],
                group_name=r[9],
            )
            for r in rows
        ]


@router.post("/{group_id}/wake")
async def wake_group(group_id: int, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute(
        "SELECT id, name FROM groups WHERE id = ?", (group_id,)
    ) as cursor:
        group_row = await cursor.fetchone()
        if not group_row:
            raise HTTPException(status_code=404, detail="Group not found")
    async with db.execute(
        "SELECT * FROM machines WHERE group_id = ?", (group_id,)
    ) as cursor:
        machines = await cursor.fetchall()
    if not machines:
        raise HTTPException(status_code=400, detail="该分组中没有设备")

    results = []
    for m in machines:
        try:
            send_wol(m[2], m[4], m[5])
            await db.execute(
                "INSERT INTO wake_history (machine_id, machine_name, mac_address, status, message) VALUES (?,?,?,?,?)",
                (m[0], m[1], m[2], "success", f"分组唤醒: {group_row[1]}"),
            )
            results.append({"machine": m[1], "status": "success"})
        except Exception as e:
            await db.execute(
                "INSERT INTO wake_history (machine_id, machine_name, mac_address, status, message) VALUES (?,?,?,?,?)",
                (m[0], m[1], m[2], "failed", str(e)),
            )
            results.append({"machine": m[1], "status": "failed", "error": str(e)})
    await db.commit()
    return {"message": f"唤醒信号已发送至分组 '{group_row[1]}'", "results": results}
