import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "parking_records.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS parking_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_num TEXT NOT NULL,
                entry_time INTEGER NOT NULL,
                exit_time INTEGER,
                fee REAL,
                status TEXT,
                cam_ip_in TEXT,
                cam_ip_out TEXT,
                gate_released INTEGER DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                order_id TEXT PRIMARY KEY,
                record_id INTEGER,
                plate_num TEXT,
                amount REAL,
                status TEXT,
                created_at INTEGER
            )
        ''')
        await db.commit()

async def get_db_connection():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db
