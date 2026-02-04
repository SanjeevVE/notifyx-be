"""V1 complete schema update - contacts, templates, tracking

Revision ID: v1_complete_001
Revises: 845b614cb739
Create Date: 2026-02-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'v1_complete_001'
down_revision: Union[str, None] = '845b614cb739'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============= Create new tables =============

    # Email Templates table
    op.create_table('email_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('subject', sa.String(500), nullable=False),
        sa.Column('html_content', sa.Text(), nullable=False),
        sa.Column('text_content', sa.Text(), nullable=True),
        sa.Column('variables', sa.JSON(), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('thumbnail_url', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('is_default', sa.Boolean(), nullable=True, default=False),
        sa.Column('times_used', sa.Integer(), nullable=True, default=0),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_email_templates_id'), 'email_templates', ['id'], unique=False)

    # Contacts table
    op.create_table('contacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('status', sa.Enum('SUBSCRIBED', 'UNSUBSCRIBED', 'BOUNCED', 'COMPLAINED', name='contactstatus'), nullable=True, default='SUBSCRIBED'),
        sa.Column('custom_fields', sa.JSON(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('total_emails_sent', sa.Integer(), nullable=True, default=0),
        sa.Column('total_emails_opened', sa.Integer(), nullable=True, default=0),
        sa.Column('total_emails_clicked', sa.Integer(), nullable=True, default=0),
        sa.Column('last_email_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_email_opened_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_email_clicked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('unsubscribed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('unsubscribe_reason', sa.String(500), nullable=True),
        sa.Column('bounce_count', sa.Integer(), nullable=True, default=0),
        sa.Column('last_bounce_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('bounce_type', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'email', name='uq_contact_org_email')
    )
    op.create_index(op.f('ix_contacts_id'), 'contacts', ['id'], unique=False)
    op.create_index(op.f('ix_contacts_email'), 'contacts', ['email'], unique=False)
    op.create_index(op.f('ix_contacts_status'), 'contacts', ['status'], unique=False)

    # Contact Lists table
    op.create_table('contact_lists',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('contact_count', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'name', name='uq_list_org_name')
    )
    op.create_index(op.f('ix_contact_lists_id'), 'contact_lists', ['id'], unique=False)

    # Contact List Memberships table
    op.create_table('contact_list_memberships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.Column('list_id', sa.Integer(), nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['list_id'], ['contact_lists.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('contact_id', 'list_id', name='uq_contact_list_membership')
    )
    op.create_index(op.f('ix_contact_list_memberships_id'), 'contact_list_memberships', ['id'], unique=False)

    # Unsubscribe Tokens table
    op.create_table('unsubscribe_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(64), nullable=False),
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=True),
        sa.Column('message_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_used', sa.Boolean(), nullable=True, default=False),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_unsubscribe_tokens_id'), 'unsubscribe_tokens', ['id'], unique=False)
    op.create_index(op.f('ix_unsubscribe_tokens_token'), 'unsubscribe_tokens', ['token'], unique=True)

    # Campaign Recipients table
    op.create_table('campaign_recipients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(50), nullable=True, default='pending'),
        sa.Column('message_id', sa.Integer(), nullable=True),
        sa.Column('personalization_data', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True, default=0),
        sa.Column('queued_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_campaign_recipients_id'), 'campaign_recipients', ['id'], unique=False)
    op.create_index(op.f('ix_campaign_recipients_campaign_id'), 'campaign_recipients', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_campaign_recipients_contact_id'), 'campaign_recipients', ['contact_id'], unique=False)
    op.create_index(op.f('ix_campaign_recipients_status'), 'campaign_recipients', ['status'], unique=False)

    # ============= Update existing tables =============

    # Update Organizations table
    op.add_column('organizations', sa.Column('default_from_name', sa.String(255), nullable=True))
    op.add_column('organizations', sa.Column('default_from_email', sa.String(255), nullable=True))
    op.add_column('organizations', sa.Column('default_reply_to', sa.String(255), nullable=True))
    op.add_column('organizations', sa.Column('tracking_domain', sa.String(255), nullable=True))
    op.add_column('organizations', sa.Column('enable_open_tracking', sa.Boolean(), nullable=True, default=True))
    op.add_column('organizations', sa.Column('enable_click_tracking', sa.Boolean(), nullable=True, default=True))
    op.add_column('organizations', sa.Column('daily_send_limit', sa.Integer(), nullable=True, default=10000))
    op.add_column('organizations', sa.Column('hourly_send_limit', sa.Integer(), nullable=True, default=1000))
    op.add_column('organizations', sa.Column('total_emails_sent', sa.Integer(), nullable=True, default=0))
    op.add_column('organizations', sa.Column('total_contacts', sa.Integer(), nullable=True, default=0))

    # Update Users table
    op.add_column('users', sa.Column('timezone', sa.String(50), nullable=True, default='UTC'))
    op.add_column('users', sa.Column('preferences', sa.JSON(), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))

    # Update Campaigns table - need to recreate enum with new values first
    # Add new columns to campaigns
    op.add_column('campaigns', sa.Column('template_id', sa.Integer(), nullable=True))
    op.add_column('campaigns', sa.Column('paused_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('campaigns', sa.Column('queued_count', sa.Integer(), nullable=True, default=0))
    op.add_column('campaigns', sa.Column('sent_count', sa.Integer(), nullable=True, default=0))
    op.add_column('campaigns', sa.Column('failed_count', sa.Integer(), nullable=True, default=0))
    op.add_column('campaigns', sa.Column('delivered_count', sa.Integer(), nullable=True, default=0))
    op.add_column('campaigns', sa.Column('opened_count', sa.Integer(), nullable=True, default=0))
    op.add_column('campaigns', sa.Column('unique_opens', sa.Integer(), nullable=True, default=0))
    op.add_column('campaigns', sa.Column('clicked_count', sa.Integer(), nullable=True, default=0))
    op.add_column('campaigns', sa.Column('unique_clicks', sa.Integer(), nullable=True, default=0))
    op.add_column('campaigns', sa.Column('bounced_count', sa.Integer(), nullable=True, default=0))
    op.add_column('campaigns', sa.Column('complained_count', sa.Integer(), nullable=True, default=0))
    op.add_column('campaigns', sa.Column('unsubscribed_count', sa.Integer(), nullable=True, default=0))
    op.add_column('campaigns', sa.Column('current_batch', sa.Integer(), nullable=True, default=0))
    op.add_column('campaigns', sa.Column('total_batches', sa.Integer(), nullable=True, default=0))
    op.add_column('campaigns', sa.Column('error_message', sa.Text(), nullable=True))
    op.create_foreign_key('fk_campaigns_template_id', 'campaigns', 'email_templates', ['template_id'], ['id'])
    op.create_index(op.f('ix_campaigns_status'), 'campaigns', ['status'], unique=False)

    # Update Messages table
    op.add_column('messages', sa.Column('contact_id', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('tracking_id', sa.String(64), nullable=True))
    op.add_column('messages', sa.Column('retry_count', sa.Integer(), nullable=True, default=0))
    op.add_column('messages', sa.Column('queued_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('messages', sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('messages', sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('messages', sa.Column('clicked_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('messages', sa.Column('bounced_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('messages', sa.Column('bounce_type', sa.String(50), nullable=True))
    op.add_column('messages', sa.Column('bounce_subtype', sa.String(100), nullable=True))
    op.add_column('messages', sa.Column('open_count', sa.Integer(), nullable=True, default=0))
    op.add_column('messages', sa.Column('click_count', sa.Integer(), nullable=True, default=0))
    op.create_foreign_key('fk_messages_contact_id', 'messages', 'contacts', ['contact_id'], ['id'])
    op.create_index(op.f('ix_messages_tracking_id'), 'messages', ['tracking_id'], unique=True)
    op.create_index(op.f('ix_messages_ses_message_id'), 'messages', ['ses_message_id'], unique=False)
    op.create_index(op.f('ix_messages_status'), 'messages', ['status'], unique=False)

    # Make campaign_id nullable in messages (for single emails)
    op.alter_column('messages', 'campaign_id', nullable=True)

    # Update Message Events table
    op.add_column('message_events', sa.Column('event_subtype', sa.String(100), nullable=True))
    op.add_column('message_events', sa.Column('link_url', sa.Text(), nullable=True))
    op.create_index(op.f('ix_message_events_message_id'), 'message_events', ['message_id'], unique=False)

    # Update Logs table
    op.add_column('logs', sa.Column('organization_id', sa.Integer(), nullable=True))
    op.add_column('logs', sa.Column('campaign_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_logs_level'), 'logs', ['level'], unique=False)
    op.create_index(op.f('ix_logs_timestamp'), 'logs', ['timestamp'], unique=False)


def downgrade() -> None:
    # Remove indexes from logs
    op.drop_index(op.f('ix_logs_timestamp'), table_name='logs')
    op.drop_index(op.f('ix_logs_level'), table_name='logs')
    op.drop_column('logs', 'campaign_id')
    op.drop_column('logs', 'organization_id')

    # Remove indexes and columns from message_events
    op.drop_index(op.f('ix_message_events_message_id'), table_name='message_events')
    op.drop_column('message_events', 'link_url')
    op.drop_column('message_events', 'event_subtype')

    # Remove indexes and columns from messages
    op.drop_index(op.f('ix_messages_status'), table_name='messages')
    op.drop_index(op.f('ix_messages_ses_message_id'), table_name='messages')
    op.drop_index(op.f('ix_messages_tracking_id'), table_name='messages')
    op.drop_constraint('fk_messages_contact_id', 'messages', type_='foreignkey')
    op.drop_column('messages', 'click_count')
    op.drop_column('messages', 'open_count')
    op.drop_column('messages', 'bounce_subtype')
    op.drop_column('messages', 'bounce_type')
    op.drop_column('messages', 'bounced_at')
    op.drop_column('messages', 'clicked_at')
    op.drop_column('messages', 'opened_at')
    op.drop_column('messages', 'delivered_at')
    op.drop_column('messages', 'queued_at')
    op.drop_column('messages', 'retry_count')
    op.drop_column('messages', 'tracking_id')
    op.drop_column('messages', 'contact_id')

    # Remove indexes and columns from campaigns
    op.drop_index(op.f('ix_campaigns_status'), table_name='campaigns')
    op.drop_constraint('fk_campaigns_template_id', 'campaigns', type_='foreignkey')
    op.drop_column('campaigns', 'error_message')
    op.drop_column('campaigns', 'total_batches')
    op.drop_column('campaigns', 'current_batch')
    op.drop_column('campaigns', 'unsubscribed_count')
    op.drop_column('campaigns', 'complained_count')
    op.drop_column('campaigns', 'bounced_count')
    op.drop_column('campaigns', 'unique_clicks')
    op.drop_column('campaigns', 'clicked_count')
    op.drop_column('campaigns', 'unique_opens')
    op.drop_column('campaigns', 'opened_count')
    op.drop_column('campaigns', 'delivered_count')
    op.drop_column('campaigns', 'failed_count')
    op.drop_column('campaigns', 'sent_count')
    op.drop_column('campaigns', 'queued_count')
    op.drop_column('campaigns', 'paused_at')
    op.drop_column('campaigns', 'template_id')

    # Remove columns from users
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'preferences')
    op.drop_column('users', 'timezone')

    # Remove columns from organizations
    op.drop_column('organizations', 'total_contacts')
    op.drop_column('organizations', 'total_emails_sent')
    op.drop_column('organizations', 'hourly_send_limit')
    op.drop_column('organizations', 'daily_send_limit')
    op.drop_column('organizations', 'enable_click_tracking')
    op.drop_column('organizations', 'enable_open_tracking')
    op.drop_column('organizations', 'tracking_domain')
    op.drop_column('organizations', 'default_reply_to')
    op.drop_column('organizations', 'default_from_email')
    op.drop_column('organizations', 'default_from_name')

    # Drop new tables
    op.drop_index(op.f('ix_campaign_recipients_status'), table_name='campaign_recipients')
    op.drop_index(op.f('ix_campaign_recipients_contact_id'), table_name='campaign_recipients')
    op.drop_index(op.f('ix_campaign_recipients_campaign_id'), table_name='campaign_recipients')
    op.drop_index(op.f('ix_campaign_recipients_id'), table_name='campaign_recipients')
    op.drop_table('campaign_recipients')

    op.drop_index(op.f('ix_unsubscribe_tokens_token'), table_name='unsubscribe_tokens')
    op.drop_index(op.f('ix_unsubscribe_tokens_id'), table_name='unsubscribe_tokens')
    op.drop_table('unsubscribe_tokens')

    op.drop_index(op.f('ix_contact_list_memberships_id'), table_name='contact_list_memberships')
    op.drop_table('contact_list_memberships')

    op.drop_index(op.f('ix_contact_lists_id'), table_name='contact_lists')
    op.drop_table('contact_lists')

    op.drop_index(op.f('ix_contacts_status'), table_name='contacts')
    op.drop_index(op.f('ix_contacts_email'), table_name='contacts')
    op.drop_index(op.f('ix_contacts_id'), table_name='contacts')
    op.drop_table('contacts')

    op.drop_index(op.f('ix_email_templates_id'), table_name='email_templates')
    op.drop_table('email_templates')
