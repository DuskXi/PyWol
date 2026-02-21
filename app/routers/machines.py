import asyncio
from datetime import datetime

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.models import MachineCreate, MachineResponse, MachineUpdate
from app.monitor import wake_monitor
from app.wol import check_host_online, send_wol

router = APIRouter()


def _row_to_machine(row) -> MachineResponse:
    return MachineResponse(
        id=row[0],
        name=row[1],
        mac_address=row[2],
        ip_address=row[3] or "",
        broadcast_address=row[4],
        port=row[5],
        group_id=row[6],
        created_at=row[7],
        updated_at=row[8],
        group_name=row[9] if len(row) > 9 else None,
    )


@router.get("/status/all")
async def check_all_status(db: aiosqlite.Connection = Depends(get_db)):
    """Check online status of all machines in parallel."""
    async with db.execute("SELECT id, ip_address FROM machines") as cursor:
        rows = await cursor.fetchall()

    async def _check(mid: int, ip: str):
        if not ip:
            return mid, None
        return mid, await check_host_online(ip)

    tasks = [_check(r[0], r[1]) for r in rows]
    results = await asyncio.gather(*tasks)
    return {str(mid): status for mid, status in results}


@router.get("", response_model=list[MachineResponse])
async def list_machines(
    group_id: int | None = None,
    db: aiosqlite.Connection = Depends(get_db),
):
    query = """
        SELECT m.*, g.name as group_name
        FROM machines m
        LEFT JOIN groups g ON m.group_id = g.id
    """
    params: list = []
    if group_id is not None:
        query += " WHERE m.group_id = ?"
        params.append(group_id)
    query += " ORDER BY m.name"
    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
        return [_row_to_machine(r) for r in rows]


@router.post("", response_model=MachineResponse)
async def create_machine(
    machine: MachineCreate,
    db: aiosqlite.Connection = Depends(get_db),
):
    now = datetime.now().isoformat()
    async with db.execute(
        "INSERT INTO machines (name, mac_address, ip_address, broadcast_address, port, group_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
        (
            machine.name,
            machine.mac_address,
            machine.ip_address,
            machine.broadcast_address,
            machine.port,
            machine.group_id,
            now,
            now,
        ),
    ) as cursor:
        machine_id = cursor.lastrowid
    await db.commit()

    async with db.execute(
        "SELECT m.*, g.name as group_name FROM machines m LEFT JOIN groups g ON m.group_id = g.id WHERE m.id = ?",
        (machine_id,),
    ) as cursor:
        row = await cursor.fetchone()
        return _row_to_machine(row)


@router.get("/{machine_id}", response_model=MachineResponse)
async def get_machine(machine_id: int, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute(
        "SELECT m.*, g.name as group_name FROM machines m LEFT JOIN groups g ON m.group_id = g.id WHERE m.id = ?",
        (machine_id,),
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Machine not found")
        return _row_to_machine(row)


@router.put("/{machine_id}", response_model=MachineResponse)
async def update_machine(
    machine_id: int,
    machine: MachineUpdate,
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute(
        "SELECT id FROM machines WHERE id = ?", (machine_id,)
    ) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Machine not found")

    data = machine.model_dump(exclude_unset=True)
    if data:
        fields = [f"{k} = ?" for k in data]
        values = list(data.values())
        fields.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(machine_id)
        await db.execute(
            f"UPDATE machines SET {', '.join(fields)} WHERE id = ?", values
        )
        await db.commit()
    return await get_machine(machine_id, db)


@router.delete("/{machine_id}")
async def delete_machine(machine_id: int, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute(
        "SELECT id FROM machines WHERE id = ?", (machine_id,)
    ) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Machine not found")
    await db.execute("DELETE FROM machines WHERE id = ?", (machine_id,))
    await db.commit()
    return {"message": "Machine deleted"}


@router.post("/{machine_id}/wake")
async def wake_machine(machine_id: int, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute(
        "SELECT * FROM machines WHERE id = ?", (machine_id,)
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Machine not found")
    try:
        send_wol(row[2], row[4], row[5])
        await db.execute(
            "INSERT INTO wake_history (machine_id, machine_name, mac_address, status, message) VALUES (?,?,?,?,?)",
            (machine_id, row[1], row[2], "success", "WOL 魔术包发送成功"),
        )
        await db.commit()

        # Start background monitor (auto-cancels any existing monitor for this machine)
        monitor_state = await wake_monitor.start(
            machine_id=machine_id,
            machine_name=row[1],
            ip_address=row[3] or "",
        )

        return {
            "message": f"WOL 魔术包已发送至 {row[1]} ({row[2]})",
            "monitor": monitor_state.to_dict(),
        }
    except Exception as e:
        await db.execute(
            "INSERT INTO wake_history (machine_id, machine_name, mac_address, status, message) VALUES (?,?,?,?,?)",
            (machine_id, row[1], row[2], "failed", str(e)),
        )
        await db.commit()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{machine_id}/status")
async def check_machine_status(
    machine_id: int, db: aiosqlite.Connection = Depends(get_db)
):
    async with db.execute(
        "SELECT ip_address FROM machines WHERE id = ?", (machine_id,)
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Machine not found")
    ip = row[0]
    if not ip:
        return {"online": None, "message": "未配置 IP 地址"}
    online = await check_host_online(ip)
    return {"online": online, "ip_address": ip}
