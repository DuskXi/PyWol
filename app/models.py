import re
from typing import Optional

from pydantic import BaseModel, field_validator


# ── Machine ──────────────────────────────────────────
class MachineCreate(BaseModel):
    name: str
    mac_address: str
    ip_address: str = ""
    broadcast_address: str = "255.255.255.255"
    port: int = 9
    group_id: Optional[int] = None

    @field_validator("mac_address")
    @classmethod
    def validate_mac(cls, v: str) -> str:
        mac = re.sub(r"[^0-9A-Fa-f]", "", v.strip())
        if len(mac) != 12:
            raise ValueError("Invalid MAC address")
        return ":".join(mac[i : i + 2].upper() for i in range(0, 12, 2))


class MachineUpdate(BaseModel):
    name: Optional[str] = None
    mac_address: Optional[str] = None
    ip_address: Optional[str] = None
    broadcast_address: Optional[str] = None
    port: Optional[int] = None
    group_id: Optional[int] = None

    @field_validator("mac_address")
    @classmethod
    def validate_mac(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        mac = re.sub(r"[^0-9A-Fa-f]", "", v.strip())
        if len(mac) != 12:
            raise ValueError("Invalid MAC address")
        return ":".join(mac[i : i + 2].upper() for i in range(0, 12, 2))


class MachineResponse(BaseModel):
    id: int
    name: str
    mac_address: str
    ip_address: str
    broadcast_address: str
    port: int
    group_id: Optional[int]
    group_name: Optional[str] = None
    online: Optional[bool] = None
    created_at: str
    updated_at: str


# ── Group ────────────────────────────────────────────
class GroupCreate(BaseModel):
    name: str
    description: str = ""


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class GroupResponse(BaseModel):
    id: int
    name: str
    description: str
    machine_count: int = 0
    created_at: str
    updated_at: str


# ── Wake History ─────────────────────────────────────
class WakeHistoryResponse(BaseModel):
    id: int
    machine_id: Optional[int]
    machine_name: str
    mac_address: str
    status: str
    message: str
    created_at: str


# ── Scheduled Task ───────────────────────────────────
class ScheduledTaskCreate(BaseModel):
    name: str
    cron_expression: str = ""
    scheduled_time: str = ""
    target_type: str  # 'machine' or 'group'
    target_id: int
    enabled: bool = True


class ScheduledTaskUpdate(BaseModel):
    name: Optional[str] = None
    cron_expression: Optional[str] = None
    scheduled_time: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    enabled: Optional[bool] = None


class ScheduledTaskResponse(BaseModel):
    id: int
    name: str
    cron_expression: str
    scheduled_time: str
    target_type: str
    target_id: int
    target_name: str = ""
    enabled: bool
    created_at: str
    updated_at: str


# ── Batch Operations ────────────────────────────────
class BatchWakeRequest(BaseModel):
    machine_ids: list[int]
