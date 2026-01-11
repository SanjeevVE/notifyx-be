# Database Seeder Guide

## Quick Start

```powershell
# Run the seeder
python seed.py
```

## What Gets Seeded

### Organizations (3)
- Acme Corporation
- Tech Innovators Inc
- Marketing Pro Agency

### Users (5)
All users have password: `password123`

| Email | Organization | Role | Name |
|-------|-------------|------|------|
| admin@acme.com | Acme Corporation | Admin | John Doe |
| marketing@acme.com | Acme Corporation | User | Jane Smith |
| ceo@techinnovators.io | Tech Innovators Inc | Admin | Alice Johnson |
| sales@techinnovators.io | Tech Innovators Inc | User | Bob Wilson |
| director@marketingpro.com | Marketing Pro Agency | Admin | Carol Martinez |

### Campaigns (6)
- **Completed** campaigns with sent messages
- **Scheduled** campaigns (future)
- **Sending** campaigns (in progress)
- **Draft** campaigns

### Messages (~16)
- Sent messages with tracking
- Failed messages
- Sample recipients

### Message Events (~30)
- Sent events
- Delivered events
- Opened events
- Clicked events
- Bounced events

### Logs (5)
- Info logs
- Warning logs
- Error logs
- With context data

## Commands

### Run Seeder
```powershell
python seed.py
```

### Clear and Reseed
The seeder automatically clears existing data before seeding.

### Use in Code
```python
import asyncio
from app.db.seeder import seed_all

asyncio.run(seed_all())
```

## Sample Data Details

### Campaign Statuses
- `completed`: 3 campaigns (with messages and events)
- `scheduled`: 1 campaign (future)
- `sending`: 1 campaign (in progress)
- `draft`: 1 campaign (not sent)

### Message Statuses
- `sent`: Most messages
- `failed`: 1 message (example of failure)

### Event Types
- `sent`: All sent messages
- `delivered`: 80% of sent
- `opened`: 40% of delivered
- `clicked`: 20% of opened
- `bounced`: 20% of sent

## Login Credentials

After seeding, you can login with:

```
Email: admin@acme.com
Password: password123
```

Or any other seeded user with password: `password123`

## Testing Scenarios

### Test Campaign Management
- Login as `admin@acme.com`
- View existing campaigns
- Create new campaigns
- Edit draft campaigns

### Test Message Tracking
- Check completed campaigns
- View message details
- See event timeline

### Test Multi-Tenant
- Login as different users
- Each organization has isolated data
- Users only see their organization's data

## Customization

Edit `app/db/seeder.py` to:
- Add more organizations
- Create different users
- Modify campaign content
- Change sample data

## Database Reset

```powershell
# Method 1: Drop and recreate database (PostgreSQL)
psql -U postgres -c "DROP DATABASE notifyx_saas;"
psql -U postgres -c "CREATE DATABASE notifyx_saas;"
alembic upgrade head
python seed.py

# Method 2: Rollback migrations
alembic downgrade base
alembic upgrade head
python seed.py
```

## Seeder Functions

```python
from app.db.seeder import (
    seed_organizations,
    seed_users,
    seed_campaigns,
    seed_messages,
    seed_message_events,
    seed_logs,
    clear_all_data
)

# Use individual seeders
async with AsyncSessionLocal() as db:
    organizations = await seed_organizations(db)
    users = await seed_users(db, organizations)
    # ... etc
```

## Production Note

⚠️ **Never run seeders in production!**

This is for development and testing only.

## Sample Output

```
============================================================
🌱 Starting Database Seeding
============================================================

🗑️  Clearing existing data...
✓ All data cleared

📊 Seeding organizations...
✓ Created 3 organizations

👥 Seeding users...
✓ Created 5 users

📧 Sample Login Credentials:
   Email: admin@acme.com
   Password: password123

📨 Seeding campaigns...
✓ Created 6 campaigns

📬 Seeding messages...
✓ Created 16 messages

📊 Seeding message events...
✓ Created 31 message events

📝 Seeding logs...
✓ Created 5 logs

============================================================
✅ Database Seeding Completed Successfully!
============================================================

📊 Summary:
   Organizations: 3
   Users: 5
   Campaigns: 6
   Messages: 16
   Events: 31
   Logs: 5

🔐 Login Credentials:
   Email: admin@acme.com
   Password: password123
```

## Troubleshooting

### "ModuleNotFoundError"
```powershell
# Make sure you're in the backend directory
cd backend
python seed.py
```

### "Database not found"
```powershell
# Run migrations first
alembic upgrade head
python seed.py
```

### "Foreign key constraint"
The seeder clears data in the correct order. If you get this error:
```powershell
# Drop and recreate database
psql -U postgres -c "DROP DATABASE notifyx_saas;"
psql -U postgres -c "CREATE DATABASE notifyx_saas;"
alembic upgrade head
python seed.py
```

---

**Happy testing!** 🚀
