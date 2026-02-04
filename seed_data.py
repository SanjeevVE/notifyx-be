"""
Seed script to populate database with sample data
Run with: python seed_data.py
"""
import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from datetime import datetime, timedelta
import random

from app.core.config import settings
from app.models.user import User, Organization
from app.models.contact import Contact, ContactList, ContactListMembership, ContactStatus
from app.models.template import EmailTemplate
from app.models.campaign import Campaign, CampaignStatus
from app.core.security import get_password_hash


async def seed_database():
    """Seed the database with sample data"""

    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Import Base to create all tables
    from app.db.database import Base

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created.")

    async with async_session() as db:
        # Check if data already exists
        result = await db.execute(select(User))
        existing_users = result.scalars().first()

        if existing_users:
            print("Database already has data. Skipping seed.")
            return

        print("Seeding database with sample data...")

        # 1. Create Organization
        org = Organization(
            name="Demo Company",
            default_from_name="Demo Company",
            default_from_email="noreply@democompany.com",
        )
        db.add(org)
        await db.flush()
        print(f"Created organization: {org.name}")

        # 2. Create User
        user = User(
            email="demo@notifyx.com",
            hashed_password=get_password_hash("demo123"),
            full_name="Demo User",
            organization_id=org.id,
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        await db.flush()
        print(f"Created user: {user.email} (password: demo123)")

        # 3. Create Contact Lists
        lists_data = [
            ("Newsletter Subscribers", "Main newsletter subscriber list"),
            ("Premium Customers", "Paying customers with premium plans"),
            ("Trial Users", "Users currently in trial period"),
            ("Inactive Users", "Users who haven't engaged in 30+ days"),
        ]

        contact_lists = []
        for name, desc in lists_data:
            cl = ContactList(
                organization_id=org.id,
                name=name,
                description=desc,
            )
            db.add(cl)
            contact_lists.append(cl)
        await db.flush()
        print(f"Created {len(contact_lists)} contact lists")

        # 4. Create Contacts
        contacts_data = [
            ("john.doe@example.com", "John Doe", "Acme Corp"),
            ("jane.smith@example.com", "Jane Smith", "Tech Solutions"),
            ("mike.johnson@example.com", "Mike Johnson", "Global Industries"),
            ("sarah.williams@example.com", "Sarah Williams", "StartupX"),
            ("david.brown@example.com", "David Brown", "Enterprise LLC"),
            ("emily.davis@example.com", "Emily Davis", "Innovation Inc"),
            ("chris.wilson@example.com", "Chris Wilson", "Digital Agency"),
            ("lisa.anderson@example.com", "Lisa Anderson", "Cloud Systems"),
            ("james.taylor@example.com", "James Taylor", "Marketing Pro"),
            ("amanda.martinez@example.com", "Amanda Martinez", "Sales Force"),
            ("robert.garcia@example.com", "Robert Garcia", "Data Insights"),
            ("jennifer.lee@example.com", "Jennifer Lee", "Web Services"),
            ("michael.harris@example.com", "Michael Harris", "App Developers"),
            ("jessica.clark@example.com", "Jessica Clark", "Design Studio"),
            ("william.lewis@example.com", "William Lewis", "Consulting Co"),
            ("ashley.robinson@example.com", "Ashley Robinson", "Finance Plus"),
            ("daniel.walker@example.com", "Daniel Walker", "HR Solutions"),
            ("stephanie.hall@example.com", "Stephanie Hall", "Legal Services"),
            ("matthew.allen@example.com", "Matthew Allen", "Real Estate Pro"),
            ("nicole.young@example.com", "Nicole Young", "Healthcare Inc"),
        ]

        contacts = []
        for email, name, company in contacts_data:
            contact = Contact(
                organization_id=org.id,
                email=email,
                full_name=name,
                company=company,
                status=ContactStatus.SUBSCRIBED,
                total_emails_sent=random.randint(0, 50),
                total_emails_opened=random.randint(0, 30),
                total_emails_clicked=random.randint(0, 15),
            )
            db.add(contact)
            contacts.append(contact)
        await db.flush()
        print(f"Created {len(contacts)} contacts")

        # 5. Add contacts to lists
        for i, contact in enumerate(contacts):
            # Add to newsletter (all contacts)
            membership = ContactListMembership(
                contact_id=contact.id,
                list_id=contact_lists[0].id,
            )
            db.add(membership)

            # Add some to other lists randomly
            if i % 3 == 0:
                membership = ContactListMembership(
                    contact_id=contact.id,
                    list_id=contact_lists[1].id,
                )
                db.add(membership)
            if i % 4 == 0:
                membership = ContactListMembership(
                    contact_id=contact.id,
                    list_id=contact_lists[2].id,
                )
                db.add(membership)

        # Update list counts
        contact_lists[0].contact_count = len(contacts)
        contact_lists[1].contact_count = len([c for i, c in enumerate(contacts) if i % 3 == 0])
        contact_lists[2].contact_count = len([c for i, c in enumerate(contacts) if i % 4 == 0])

        print("Added contacts to lists")

        # 6. Create Email Templates
        templates_data = [
            (
                "Welcome Email",
                "Welcome to {{company_name}}!",
                """<h1>Welcome, {{first_name}}!</h1>
<p>We're excited to have you on board at {{company_name}}.</p>
<p>Here are some things you can do to get started:</p>
<ul>
    <li>Complete your profile</li>
    <li>Explore our features</li>
    <li>Join our community</li>
</ul>
<p>If you have any questions, just reply to this email.</p>
<p>Best regards,<br>The {{company_name}} Team</p>""",
                ["first_name", "company_name"]
            ),
            (
                "Monthly Newsletter",
                "{{company_name}} Monthly Update - {{month}}",
                """<h1>Monthly Newsletter</h1>
<p>Hi {{first_name}},</p>
<p>Here's what's new this month at {{company_name}}:</p>
<h2>New Features</h2>
<p>We've launched several exciting features this month...</p>
<h2>Tips & Tricks</h2>
<p>Get the most out of our platform with these tips...</p>
<h2>Upcoming Events</h2>
<p>Don't miss our upcoming webinars and events...</p>
<p>Thanks for being part of our community!</p>
<p>Best,<br>The {{company_name}} Team</p>""",
                ["first_name", "company_name", "month"]
            ),
            (
                "Special Offer",
                "Exclusive Offer Just for You, {{first_name}}!",
                """<h1>Special Offer!</h1>
<p>Hi {{first_name}},</p>
<p>As a valued customer at {{company_name}}, we have an exclusive offer just for you!</p>
<div style="background: #f0f0f0; padding: 20px; border-radius: 8px; margin: 20px 0;">
    <h2 style="color: #e74c3c;">{{discount_percent}}% OFF</h2>
    <p>Use code: <strong>{{promo_code}}</strong></p>
    <p>Valid until: {{expiry_date}}</p>
</div>
<p><a href="{{shop_url}}" style="background: #3498db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px;">Shop Now</a></p>
<p>Don't miss out!</p>""",
                ["first_name", "company_name", "discount_percent", "promo_code", "expiry_date", "shop_url"]
            ),
            (
                "Re-engagement",
                "We miss you, {{first_name}}!",
                """<h1>We Miss You!</h1>
<p>Hi {{first_name}},</p>
<p>It's been a while since we've seen you at {{company_name}}. We wanted to check in and see how you're doing!</p>
<p>A lot has changed since your last visit:</p>
<ul>
    <li>New features and improvements</li>
    <li>Better performance</li>
    <li>Enhanced user experience</li>
</ul>
<p><a href="{{login_url}}" style="background: #27ae60; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px;">Come Back and Explore</a></p>
<p>We'd love to have you back!</p>""",
                ["first_name", "company_name", "login_url"]
            ),
        ]

        templates = []
        for name, subject, html_content, variables in templates_data:
            template = EmailTemplate(
                organization_id=org.id,
                name=name,
                subject=subject,
                html_content=html_content,
                text_content=html_content.replace('<h1>', '').replace('</h1>', '\n').replace('<p>', '').replace('</p>', '\n'),
                variables=variables,
            )
            db.add(template)
            templates.append(template)
        await db.flush()
        print(f"Created {len(templates)} email templates")

        # 7. Create Campaigns
        campaigns_data = [
            ("Welcome Campaign", CampaignStatus.COMPLETED, 150, 120, 45, 5),
            ("January Newsletter", CampaignStatus.COMPLETED, 500, 350, 125, 12),
            ("Product Launch", CampaignStatus.COMPLETED, 1000, 680, 230, 25),
            ("Flash Sale Alert", CampaignStatus.COMPLETED, 750, 520, 180, 18),
            ("Q1 Recap", CampaignStatus.SCHEDULED, 0, 0, 0, 0),
            ("Feature Announcement", CampaignStatus.DRAFT, 0, 0, 0, 0),
        ]

        for i, (name, status, sent, opened, clicked, bounced) in enumerate(campaigns_data):
            campaign = Campaign(
                organization_id=org.id,
                name=name,
                subject=f"{name} - Check it out!",
                from_name="NotifyX Team",
                from_email="noreply@notifyx.com",
                html_content=templates[i % len(templates)].html_content,
                status=status,
                sent_count=sent,
                opened_count=opened,
                clicked_count=clicked,
                bounced_count=bounced,
                template_id=templates[i % len(templates)].id,
                scheduled_at=datetime.utcnow() + timedelta(days=7) if status == CampaignStatus.SCHEDULED else None,
                completed_at=datetime.utcnow() - timedelta(days=random.randint(1, 30)) if status == CampaignStatus.COMPLETED else None,
            )
            db.add(campaign)
        print(f"Created {len(campaigns_data)} campaigns")

        # Commit all changes
        await db.commit()
        print("\nDatabase seeded successfully!")
        print("\n--- Login Credentials ---")
        print(f"Email: demo@notifyx.com")
        print(f"Password: demo123")
        print("-------------------------")


if __name__ == "__main__":
    asyncio.run(seed_database())
