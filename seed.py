#!/usr/bin/env python
"""
Quick Database Seeder Script
Run this to populate the database with sample data
"""
import asyncio
from app.db.seeder import seed_all

if __name__ == "__main__":
    print("\n🌱 Email Communication Platform - Database Seeder\n")
    asyncio.run(seed_all())
    print("\n✨ Done! You can now login to the application.\n")
