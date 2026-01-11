"""
Database initialization script
Run this to create all database tables
"""
import asyncio
from app.db.database import init_db


async def main():
    print("Initializing database...")
    await init_db()
    print("✓ Database initialized successfully!")
    print("✓ All tables created")


if __name__ == "__main__":
    asyncio.run(main())
