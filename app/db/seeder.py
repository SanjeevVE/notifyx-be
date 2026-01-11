"""
Database Seeder for Email Communication Platform
Creates sample data for testing and development
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.database import AsyncSessionLocal
from app.models.user import User, Organization
from app.models.campaign import Campaign, Message, MessageEvent, Log, CampaignStatus
from app.core.security import get_password_hash
from datetime import datetime, timedelta


async def clear_all_data(db: AsyncSession):
    """Clear all existing data from database"""
    print("🗑️  Clearing existing data...")

    # Delete in correct order (respecting foreign keys)
    await db.execute(text("DELETE FROM message_events"))
    await db.execute(text("DELETE FROM messages"))
    await db.execute(text("DELETE FROM campaigns"))
    await db.execute(text("DELETE FROM users"))
    await db.execute(text("DELETE FROM organizations"))
    await db.execute(text("DELETE FROM logs"))
    await db.commit()

    print("✓ All data cleared")


async def seed_organizations(db: AsyncSession):
    """Seed organizations"""
    print("\n📊 Seeding organizations...")

    orgs = [
        Organization(
            name="Acme Corporation",
            domain="acme.com",
            is_active=True,
        ),
        Organization(
            name="Tech Innovators Inc",
            domain="techinnovators.io",
            is_active=True,
        ),
        Organization(
            name="Marketing Pro Agency",
            domain="marketingpro.com",
            is_active=True,
        ),
    ]

    db.add_all(orgs)
    await db.commit()

    for org in orgs:
        await db.refresh(org)

    print(f"✓ Created {len(orgs)} organizations")
    return orgs


async def seed_users(db: AsyncSession, organizations: list):
    """Seed users"""
    print("\n👥 Seeding users...")

    users = [
        # Acme Corporation users
        User(
            email="admin@acme.com",
            hashed_password=get_password_hash("password123"),
            full_name="John Doe",
            is_active=True,
            is_superuser=True,
            organization_id=organizations[0].id,
        ),
        User(
            email="marketing@acme.com",
            hashed_password=get_password_hash("password123"),
            full_name="Jane Smith",
            is_active=True,
            is_superuser=False,
            organization_id=organizations[0].id,
        ),
        # Tech Innovators users
        User(
            email="ceo@techinnovators.io",
            hashed_password=get_password_hash("password123"),
            full_name="Alice Johnson",
            is_active=True,
            is_superuser=True,
            organization_id=organizations[1].id,
        ),
        User(
            email="sales@techinnovators.io",
            hashed_password=get_password_hash("password123"),
            full_name="Bob Wilson",
            is_active=True,
            is_superuser=False,
            organization_id=organizations[1].id,
        ),
        # Marketing Pro users
        User(
            email="director@marketingpro.com",
            hashed_password=get_password_hash("password123"),
            full_name="Carol Martinez",
            is_active=True,
            is_superuser=True,
            organization_id=organizations[2].id,
        ),
    ]

    db.add_all(users)
    await db.commit()

    for user in users:
        await db.refresh(user)

    print(f"✓ Created {len(users)} users")
    print("\n📧 Sample Login Credentials:")
    print("   Email: admin@acme.com")
    print("   Password: password123")
    print("\n   (All users have password: password123)")

    return users


async def seed_campaigns(db: AsyncSession, organizations: list):
    """Seed campaigns"""
    print("\n📨 Seeding campaigns...")

    campaigns = [
        # Acme Corporation campaigns
        Campaign(
            organization_id=organizations[0].id,
            name="Welcome Email Series",
            subject="Welcome to Acme Corporation!",
            from_name="Acme Team",
            from_email="noreply@acme.com",
            reply_to="support@acme.com",
            html_content="<h1>Welcome!</h1><p>Thank you for joining Acme Corporation.</p>",
            text_content="Welcome! Thank you for joining Acme Corporation.",
            status=CampaignStatus.COMPLETED,
            scheduled_at=datetime.utcnow() - timedelta(days=7),
            started_at=datetime.utcnow() - timedelta(days=7),
            completed_at=datetime.utcnow() - timedelta(days=7, hours=2),
            total_recipients=150,
        ),
        Campaign(
            organization_id=organizations[0].id,
            name="Monthly Newsletter - January",
            subject="Acme January Newsletter",
            from_name="Acme Marketing",
            from_email="newsletter@acme.com",
            reply_to="marketing@acme.com",
            html_content="<h1>January Updates</h1><p>Here's what's new this month...</p>",
            text_content="January Updates: Here's what's new this month...",
            status=CampaignStatus.COMPLETED,
            scheduled_at=datetime.utcnow() - timedelta(days=3),
            started_at=datetime.utcnow() - timedelta(days=3),
            completed_at=datetime.utcnow() - timedelta(days=3, hours=1),
            total_recipients=500,
        ),
        Campaign(
            organization_id=organizations[0].id,
            name="Product Launch Announcement",
            subject="Introducing Our New Product!",
            from_name="Acme Team",
            from_email="news@acme.com",
            html_content="<h1>New Product Launch</h1><p>We're excited to announce...</p>",
            text_content="New Product Launch: We're excited to announce...",
            status=CampaignStatus.SCHEDULED,
            scheduled_at=datetime.utcnow() + timedelta(days=2),
            total_recipients=0,
        ),
        # Tech Innovators campaigns
        Campaign(
            organization_id=organizations[1].id,
            name="Tech Conference Invitation",
            subject="You're Invited to TechCon 2026",
            from_name="Tech Innovators",
            from_email="events@techinnovators.io",
            reply_to="rsvp@techinnovators.io",
            html_content="<h1>TechCon 2026</h1><p>Join us for the biggest tech event of the year!</p>",
            text_content="TechCon 2026: Join us for the biggest tech event of the year!",
            status=CampaignStatus.SENDING,
            scheduled_at=datetime.utcnow() - timedelta(hours=1),
            started_at=datetime.utcnow() - timedelta(hours=1),
            total_recipients=1000,
        ),
        Campaign(
            organization_id=organizations[1].id,
            name="Weekly Tech Tips",
            subject="This Week's Tech Tips",
            from_name="Tech Innovators Team",
            from_email="tips@techinnovators.io",
            html_content="<h1>Weekly Tips</h1><p>Here are this week's top tech tips...</p>",
            text_content="Weekly Tips: Here are this week's top tech tips...",
            status=CampaignStatus.DRAFT,
            total_recipients=0,
        ),
        # Marketing Pro campaigns
        Campaign(
            organization_id=organizations[2].id,
            name="Client Success Stories",
            subject="How Our Clients Achieved 10x Growth",
            from_name="Marketing Pro",
            from_email="success@marketingpro.com",
            html_content="<h1>Success Stories</h1><p>Read how our clients achieved amazing results...</p>",
            text_content="Success Stories: Read how our clients achieved amazing results...",
            status=CampaignStatus.COMPLETED,
            scheduled_at=datetime.utcnow() - timedelta(days=5),
            started_at=datetime.utcnow() - timedelta(days=5),
            completed_at=datetime.utcnow() - timedelta(days=5, hours=3),
            total_recipients=250,
        ),
    ]

    db.add_all(campaigns)
    await db.commit()

    for campaign in campaigns:
        await db.refresh(campaign)

    print(f"✓ Created {len(campaigns)} campaigns")
    return campaigns


async def seed_messages(db: AsyncSession, campaigns: list):
    """Seed messages"""
    print("\n📬 Seeding messages...")

    messages = []

    # Messages for completed campaigns
    completed_campaigns = [c for c in campaigns if c.status == CampaignStatus.COMPLETED]

    sample_recipients = [
        ("customer1@example.com", "Customer One"),
        ("customer2@example.com", "Customer Two"),
        ("customer3@example.com", "Customer Three"),
        ("subscriber@example.com", "Subscriber Name"),
        ("user@domain.com", "User Name"),
    ]

    for campaign in completed_campaigns[:3]:  # First 3 completed campaigns
        for i, (email, name) in enumerate(sample_recipients):
            message = Message(
                campaign_id=campaign.id,
                recipient_email=email,
                recipient_name=name,
                subject=campaign.subject,
                html_content=campaign.html_content,
                text_content=campaign.text_content,
                message_id=f"msg-{campaign.id}-{i}@email.platform",
                ses_message_id=f"ses-{campaign.id}-{i}-abcd1234",
                status="sent",
                sent_at=campaign.started_at + timedelta(minutes=i*2),
            )
            messages.append(message)

    # Add some failed messages
    failed_message = Message(
        campaign_id=completed_campaigns[0].id,
        recipient_email="invalid@nonexistent-domain-xyz.com",
        recipient_name="Failed User",
        subject=completed_campaigns[0].subject,
        html_content=completed_campaigns[0].html_content,
        status="failed",
        error_message="Email address does not exist",
        sent_at=None,
    )
    messages.append(failed_message)

    db.add_all(messages)
    await db.commit()

    for message in messages:
        await db.refresh(message)

    print(f"✓ Created {len(messages)} messages")
    return messages


async def seed_message_events(db: AsyncSession, messages: list):
    """Seed message events"""
    print("\n📊 Seeding message events...")

    events = []

    # Only create events for sent messages
    sent_messages = [m for m in messages if m.status == "sent"]

    for message in sent_messages[:10]:  # First 10 sent messages
        # Sent event
        events.append(MessageEvent(
            message_id=message.id,
            event_type="sent",
            event_data={"message_id": message.ses_message_id},
            timestamp=message.sent_at,
        ))

        # Delivered event (80% of messages)
        if hash(message.id) % 10 < 8:
            events.append(MessageEvent(
                message_id=message.id,
                event_type="delivered",
                event_data={"message_id": message.ses_message_id},
                timestamp=message.sent_at + timedelta(seconds=30),
            ))

            # Opened event (40% of delivered)
            if hash(message.id) % 10 < 4:
                events.append(MessageEvent(
                    message_id=message.id,
                    event_type="opened",
                    event_data={"message_id": message.ses_message_id},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    ip_address="192.168.1.100",
                    timestamp=message.sent_at + timedelta(hours=1),
                ))

                # Clicked event (20% of opened)
                if hash(message.id) % 10 < 2:
                    events.append(MessageEvent(
                        message_id=message.id,
                        event_type="clicked",
                        event_data={"url": "https://example.com/product", "message_id": message.ses_message_id},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                        ip_address="192.168.1.100",
                        timestamp=message.sent_at + timedelta(hours=2),
                    ))
        else:
            # Bounced event (remaining 20%)
            events.append(MessageEvent(
                message_id=message.id,
                event_type="bounced",
                event_data={"bounce_type": "permanent", "message_id": message.ses_message_id},
                timestamp=message.sent_at + timedelta(minutes=5),
            ))

    db.add_all(events)
    await db.commit()

    print(f"✓ Created {len(events)} message events")
    return events


async def seed_logs(db: AsyncSession):
    """Seed logs"""
    print("\n📝 Seeding logs...")

    logs = [
        Log(
            level="info",
            module="auth",
            message="User login successful",
            context_data={"user_id": 1, "ip": "192.168.1.100"},
            timestamp=datetime.utcnow() - timedelta(hours=1),
        ),
        Log(
            level="info",
            module="campaign",
            message="Campaign created",
            context_data={"campaign_id": 1, "user_id": 1},
            timestamp=datetime.utcnow() - timedelta(hours=2),
        ),
        Log(
            level="warning",
            module="email",
            message="Email delivery delayed",
            context_data={"message_id": 5, "delay_seconds": 30},
            timestamp=datetime.utcnow() - timedelta(hours=3),
        ),
        Log(
            level="error",
            module="email",
            message="Failed to send email",
            context_data={"recipient": "invalid@example.com", "error": "Invalid address"},
            timestamp=datetime.utcnow() - timedelta(hours=4),
        ),
        Log(
            level="info",
            module="campaign",
            message="Campaign completed",
            context_data={"campaign_id": 1, "total_sent": 150, "total_opened": 60},
            timestamp=datetime.utcnow() - timedelta(hours=5),
        ),
    ]

    db.add_all(logs)
    await db.commit()

    print(f"✓ Created {len(logs)} logs")
    return logs


async def seed_all():
    """Run all seeders"""
    print("\n" + "="*60)
    print("🌱 Starting Database Seeding")
    print("="*60)

    async with AsyncSessionLocal() as db:
        try:
            # Clear existing data
            await clear_all_data(db)

            # Seed in order (respecting foreign keys)
            organizations = await seed_organizations(db)
            users = await seed_users(db, organizations)
            campaigns = await seed_campaigns(db, organizations)
            messages = await seed_messages(db, campaigns)
            events = await seed_message_events(db, messages)
            logs = await seed_logs(db)

            print("\n" + "="*60)
            print("✅ Database Seeding Completed Successfully!")
            print("="*60)

            print("\n📊 Summary:")
            print(f"   Organizations: {len(organizations)}")
            print(f"   Users: {len(users)}")
            print(f"   Campaigns: {len(campaigns)}")
            print(f"   Messages: {len(messages)}")
            print(f"   Events: {len(events)}")
            print(f"   Logs: {len(logs)}")

            print("\n🔐 Login Credentials:")
            print("   Email: admin@acme.com")
            print("   Password: password123")
            print("\n   Or try any other seeded user with password: password123")

        except Exception as e:
            print(f"\n❌ Error during seeding: {str(e)}")
            raise


if __name__ == "__main__":
    asyncio.run(seed_all())
