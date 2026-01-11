# Database Migrations Guide

Complete guide for managing database migrations with Poetry and Alembic.

## 🚀 All Commands (Copy & Paste)

### Complete Setup with Poetry

```bash
# Navigate to backend
cd backend

# Install all dependencies with Poetry
poetry install

# Create initial migration
poetry run alembic revision --autogenerate -m "Initial migration"

# Apply migrations
poetry run alembic upgrade head

# Run the backend
poetry run python -m app.main
```

---

## Step-by-Step Guide

### 1. Install Poetry (One-time setup)

**Windows PowerShell:**
```bash
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
```

**Or with pip:**
```bash
pip install poetry
```

**Verify installation:**
```bash
poetry --version
```

### 2. Install Dependencies

```bash
cd backend

# Install all dependencies from pyproject.toml
poetry install

# This creates a virtual environment automatically
```

### 3. Create Initial Migration

```bash
# Generate migration from models
poetry run alembic revision --autogenerate -m "Initial migration"
```

This creates a file like: `alembic/versions/xxxx_initial_migration.py`

### 4. Apply Migration

```bash
# Apply all pending migrations
poetry run alembic upgrade head
```

### 5. Run Backend

```bash
# Run with Poetry
poetry run python -m app.main

# Or activate Poetry shell first
poetry shell
python -m app.main
```

---

## Common Migration Commands

### Create New Migration

```bash
# After changing models, create a new migration
poetry run alembic revision --autogenerate -m "Add new column to users"
```

### Apply Migrations

```bash
# Apply all pending migrations
poetry run alembic upgrade head

# Apply specific number of migrations
poetry run alembic upgrade +1

# Upgrade to specific revision
poetry run alembic upgrade <revision_id>
```

### Rollback Migrations

```bash
# Rollback last migration
poetry run alembic downgrade -1

# Rollback all migrations
poetry run alembic downgrade base

# Downgrade to specific revision
poetry run alembic downgrade <revision_id>
```

### View Migration Status

```bash
# Show current database version
poetry run alembic current

# Show migration history
poetry run alembic history

# Show migration history with details
poetry run alembic history --verbose
```

### Create Empty Migration (Manual)

```bash
# Create migration file without autogenerate
poetry run alembic revision -m "Custom migration"
```

---

## Migration Workflow

### When You Change Models

1. **Modify your model** (e.g., `app/models/user.py`)
   ```python
   # Add new column
   phone_number = Column(String, nullable=True)
   ```

2. **Create migration**
   ```bash
   poetry run alembic revision --autogenerate -m "Add phone number to users"
   ```

3. **Review the migration file**
   ```bash
   # Check: alembic/versions/xxxx_add_phone_number_to_users.py
   ```

4. **Apply migration**
   ```bash
   poetry run alembic upgrade head
   ```

5. **Verify in database**
   ```bash
   sqlite3 email_platform.db
   .schema users
   .quit
   ```

---

## Poetry Commands Reference

### Installation & Setup

```bash
# Install dependencies
poetry install

# Add new package
poetry add package-name

# Add dev dependency
poetry add --group dev package-name

# Update dependencies
poetry update

# Show installed packages
poetry show

# Show dependency tree
poetry show --tree
```

### Running Commands

```bash
# Run single command with Poetry
poetry run python script.py

# Activate Poetry shell
poetry shell

# Now you can run commands directly
python -m app.main
alembic upgrade head
exit  # to exit shell
```

### Environment Management

```bash
# Show virtual environment info
poetry env info

# List virtual environments
poetry env list

# Remove virtual environment
poetry env remove python

# Use specific Python version
poetry env use python3.11
```

---

## Project Structure

```
backend/
├── alembic/
│   ├── versions/              # Migration files
│   │   └── xxxx_initial_migration.py
│   ├── env.py                 # Alembic environment
│   ├── script.py.mako         # Template for migrations
│   └── README
├── app/
│   ├── models/               # Your SQLAlchemy models
│   │   ├── user.py
│   │   └── campaign.py
│   └── ...
├── alembic.ini               # Alembic configuration
├── pyproject.toml            # Poetry configuration
└── MIGRATIONS.md             # This file
```

---

## Migration File Example

After running `alembic revision --autogenerate`, you get:

```python
# alembic/versions/001_initial_migration.py

def upgrade() -> None:
    # Create organizations table
    op.create_table('organizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('domain', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_superuser', sa.Boolean(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_table('organizations')
```

---

## Troubleshooting

### "No such table" Error

```bash
# Make sure migrations are applied
poetry run alembic upgrade head
```

### "Can't locate revision" Error

```bash
# Reset Alembic version table
poetry run alembic stamp head
```

### "Target database is not up to date" Error

```bash
# Check current version
poetry run alembic current

# Apply pending migrations
poetry run alembic upgrade head
```

### Clear Database and Start Over

```bash
# Delete database
rm email_platform.db

# Delete all migration files
rm alembic/versions/*.py

# Create new migration
poetry run alembic revision --autogenerate -m "Initial migration"

# Apply migration
poetry run alembic upgrade head
```

### Poetry Virtual Environment Issues

```bash
# Remove and recreate environment
poetry env remove python
poetry install
```

---

## Best Practices

### 1. Always Review Generated Migrations

```bash
# After generating, check the file
poetry run alembic revision --autogenerate -m "Add column"

# Review: alembic/versions/xxxx_add_column.py
# Make sure the changes are correct
```

### 2. Test Migrations

```bash
# Apply migration
poetry run alembic upgrade head

# Test your app
poetry run python -m app.main

# If issues, rollback
poetry run alembic downgrade -1
```

### 3. Never Edit Applied Migrations

- Don't modify migration files that have been applied
- Create a new migration instead
- Use `alembic downgrade` to rollback if needed

### 4. Commit Migrations to Git

```bash
git add alembic/versions/
git commit -m "Add migration for user phone number"
```

### 5. Use Descriptive Messages

```bash
# Good
poetry run alembic revision --autogenerate -m "Add phone_number to users table"

# Bad
poetry run alembic revision --autogenerate -m "Update"
```

---

## Quick Command Reference

```bash
# Setup (one-time)
poetry install

# Create migration
poetry run alembic revision --autogenerate -m "Description"

# Apply migrations
poetry run alembic upgrade head

# Rollback
poetry run alembic downgrade -1

# Check status
poetry run alembic current

# Show history
poetry run alembic history

# Run app
poetry run python -m app.main

# Enter shell
poetry shell
```

---

## Integration with Main App

The main app (`app/main.py`) can still use auto-create for development:

```python
# For development (auto-create tables)
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# For production (use migrations)
# Just run: alembic upgrade head
```

---

## Migration vs Auto-Create

### Use Auto-Create (Current)
- ✅ Development
- ✅ Quick prototyping
- ✅ Simple changes

### Use Migrations (Alembic)
- ✅ Production
- ✅ Team collaboration
- ✅ Version control
- ✅ Complex schema changes
- ✅ Data migrations
- ✅ Rollback support

---

**You're all set!** 🚀

Run this to get started:
```bash
cd backend
poetry install
poetry run alembic revision --autogenerate -m "Initial migration"
poetry run alembic upgrade head
poetry run python -m app.main
```
