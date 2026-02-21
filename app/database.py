from pathlib import Path

import aiosqlite
from loguru import logger

DB_PATH = Path(__file__).parent.parent / "data" / "pywol.db"


async def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Initializing database at {DB_PATH}")
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS machines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                mac_address TEXT NOT NULL,
                ip_address TEXT DEFAULT '',
                broadcast_address TEXT DEFAULT '255.255.255.255',
                port INTEGER DEFAULT 9,
                group_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS wake_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id INTEGER,
                machine_name TEXT NOT NULL,
                mac_address TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (machine_id) REFERENCES machines(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                cron_expression TEXT DEFAULT '',
                scheduled_time TEXT DEFAULT '',
                target_type TEXT NOT NULL,
                target_id INTEGER NOT NULL,
                enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await db.commit()
    logger.info("Database initialized successfully")
