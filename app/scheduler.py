import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from loguru import logger

from app.database import DB_PATH
from app.wol import send_wol

scheduler = AsyncIOScheduler()


async def execute_wake_task(task_id: int):
    """Execute a scheduled wake task."""
    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            async with db.execute(
                "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)
            ) as cursor:
                task = await cursor.fetchone()

            if not task:
                logger.warning(f"Scheduled task {task_id} not found")
                return

            target_type = task[4]
            target_id = task[5]

            if target_type == "machine":
                async with db.execute(
                    "SELECT * FROM machines WHERE id = ?", (target_id,)
                ) as cursor:
                    machine = await cursor.fetchone()
                if machine:
                    try:
                        send_wol(machine[2], machine[4], machine[5])
                        await db.execute(
                            "INSERT INTO wake_history (machine_id, machine_name, mac_address, status, message) VALUES (?, ?, ?, ?, ?)",
                            (machine[0], machine[1], machine[2], "success", f"定时任务: {task[1]}"),
                        )
                    except Exception as e:
                        await db.execute(
                            "INSERT INTO wake_history (machine_id, machine_name, mac_address, status, message) VALUES (?, ?, ?, ?, ?)",
                            (machine[0], machine[1], machine[2], "failed", f"定时任务: {task[1]} - {e}"),
                        )

            elif target_type == "group":
                async with db.execute(
                    "SELECT * FROM machines WHERE group_id = ?", (target_id,)
                ) as cursor:
                    machines = await cursor.fetchall()
                for machine in machines:
                    try:
                        send_wol(machine[2], machine[4], machine[5])
                        await db.execute(
                            "INSERT INTO wake_history (machine_id, machine_name, mac_address, status, message) VALUES (?, ?, ?, ?, ?)",
                            (machine[0], machine[1], machine[2], "success", f"定时任务: {task[1]}"),
                        )
                    except Exception as e:
                        await db.execute(
                            "INSERT INTO wake_history (machine_id, machine_name, mac_address, status, message) VALUES (?, ?, ?, ?, ?)",
                            (machine[0], machine[1], machine[2], "failed", f"定时任务: {task[1]} - {e}"),
                        )

            await db.commit()
            logger.info(f"Scheduled task '{task[1]}' executed successfully")
    except Exception as e:
        logger.error(f"Error executing scheduled task {task_id}: {e}")


async def add_scheduled_task(task_id: int, task) -> None:
    """Add a task to the scheduler."""
    try:
        if task.cron_expression:
            parts = task.cron_expression.strip().split()
            if len(parts) == 5:
                trigger = CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4],
                )
            else:
                logger.error(f"Invalid cron expression: {task.cron_expression}")
                return
        elif task.scheduled_time:
            trigger = DateTrigger(run_date=task.scheduled_time)
        else:
            logger.error(f"No schedule specified for task {task_id}")
            return

        scheduler.add_job(
            execute_wake_task,
            trigger=trigger,
            args=[task_id],
            id=f"wake_task_{task_id}",
            replace_existing=True,
        )
        logger.info(f"Scheduled task {task_id} added to scheduler")
    except Exception as e:
        logger.error(f"Error adding scheduled task {task_id}: {e}")


async def remove_scheduled_task(task_id: int) -> None:
    """Remove a task from the scheduler."""
    try:
        scheduler.remove_job(f"wake_task_{task_id}")
        logger.info(f"Scheduled task {task_id} removed")
    except Exception:
        pass


async def init_scheduler():
    """Initialize the scheduler and load existing tasks."""
    scheduler.start()
    logger.info("Scheduler started")
    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            async with db.execute(
                "SELECT * FROM scheduled_tasks WHERE enabled = 1"
            ) as cursor:
                tasks = await cursor.fetchall()
            for task in tasks:
                from app.models import ScheduledTaskCreate

                task_data = ScheduledTaskCreate(
                    name=task[1],
                    cron_expression=task[2] or "",
                    scheduled_time=task[3] or "",
                    target_type=task[4],
                    target_id=task[5],
                    enabled=bool(task[6]),
                )
                await add_scheduled_task(task[0], task_data)
    except Exception as e:
        logger.error(f"Error loading scheduled tasks: {e}")


async def shutdown_scheduler():
    """Shutdown the scheduler."""
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
