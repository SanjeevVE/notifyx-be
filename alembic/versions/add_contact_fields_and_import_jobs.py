"""Add contact_fields and import_jobs tables

Revision ID: add_contact_fields_001
Revises: v1_complete_001
Create Date: 2026-02-05 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_contact_fields_001'
down_revision: Union[str, None] = 'v1_complete_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============= Create contact_fields table =============
    op.create_table('contact_fields',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('field_key', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('field_type', sa.Enum('text', 'number', 'date', 'boolean', 'select', 'multi_select', name='fieldtype'), nullable=False),
        sa.Column('is_system_field', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_required', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_unique', sa.Boolean(), nullable=True, default=False),
        sa.Column('default_value', sa.String(500), nullable=True),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('validation_rules', sa.JSON(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=True, default=0),
        sa.Column('display_order', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'field_key', name='uq_contact_field_org_key')
    )
    op.create_index(op.f('ix_contact_fields_id'), 'contact_fields', ['id'], unique=False)
    op.create_index(op.f('ix_contact_fields_organization_id'), 'contact_fields', ['organization_id'], unique=False)
    op.create_index(op.f('ix_contact_fields_field_key'), 'contact_fields', ['field_key'], unique=False)

    # ============= Create import_jobs table =============
    op.create_table('import_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', 'cancelled', name='importjobstatus'), nullable=True, default='pending'),
        sa.Column('column_mapping', sa.JSON(), nullable=True),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('total_rows', sa.Integer(), nullable=True, default=0),
        sa.Column('processed_rows', sa.Integer(), nullable=True, default=0),
        sa.Column('imported_count', sa.Integer(), nullable=True, default=0),
        sa.Column('updated_count', sa.Integer(), nullable=True, default=0),
        sa.Column('skipped_count', sa.Integer(), nullable=True, default=0),
        sa.Column('failed_count', sa.Integer(), nullable=True, default=0),
        sa.Column('errors', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('celery_task_id', sa.String(255), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_import_jobs_id'), 'import_jobs', ['id'], unique=False)
    op.create_index(op.f('ix_import_jobs_organization_id'), 'import_jobs', ['organization_id'], unique=False)
    op.create_index(op.f('ix_import_jobs_status'), 'import_jobs', ['status'], unique=False)

    # ============= Seed system fields for existing organizations =============
    # This will be done via application code after migration runs
    # See: app.api.v1.contact_fields.seed_system_fields()


def downgrade() -> None:
    # Drop import_jobs table
    op.drop_index(op.f('ix_import_jobs_status'), table_name='import_jobs')
    op.drop_index(op.f('ix_import_jobs_organization_id'), table_name='import_jobs')
    op.drop_index(op.f('ix_import_jobs_id'), table_name='import_jobs')
    op.drop_table('import_jobs')

    # Drop contact_fields table
    op.drop_index(op.f('ix_contact_fields_field_key'), table_name='contact_fields')
    op.drop_index(op.f('ix_contact_fields_organization_id'), table_name='contact_fields')
    op.drop_index(op.f('ix_contact_fields_id'), table_name='contact_fields')
    op.drop_table('contact_fields')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS importjobstatus")
    op.execute("DROP TYPE IF EXISTS fieldtype")
