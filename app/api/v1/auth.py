from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta

from app.db.database import get_db
from app.models.user import User, Organization
from app.schemas.user import UserCreate, UserResponse, Token, UserLogin
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
)
from app.core.config import settings

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    description="Enter your JWT token here (the 'Bearer' prefix is added automatically)"
)


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise credentials_exception

    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="""
    Create a new user account and organization.

    - **email**: Valid email address (will be used for login)
    - **password**: Strong password (min 8 characters recommended)
    - **full_name**: User's full name
    - **organization_name**: Optional organization name (auto-generated if not provided)

    Returns the created user object with organization details.
    """,
)
async def signup(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user"""
    # Check if user already exists
    result = await db.execute(select(User).filter(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create organization if provided, otherwise create a default one
    org_name = user_data.organization_name or f"{user_data.email.split('@')[0]}'s Organization"
    organization = Organization(name=org_name)
    db.add(organization)
    await db.flush()

    # Seed system fields for the new organization (lazy import to avoid circular dependency)
    from app.api.v1.contact_fields import seed_system_fields
    await seed_system_fields(db, organization.id)

    # Create user
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        organization_id=organization.id,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)
    await db.refresh(user, ["organization"])

    return user


@router.post(
    "/login",
    response_model=Token,
    summary="Login to get access token",
    description="""
    Authenticate with email and password to receive a JWT access token.

    **Important**: Use your **email** as the username field.

    - **username**: Your email address (e.g., test@example.com)
    - **password**: Your account password

    Returns an access token that can be used to authenticate subsequent requests.

    **How to use the token:**
    1. Copy the `access_token` from the response
    2. Click the "Authorize" button (🔓) at the top right
    3. Enter: `Bearer <your_access_token>`
    4. Click "Authorize" and "Close"
    """,
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
):
    """Login with email and password"""
    # Get user
    result = await db.execute(select(User).filter(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    description="""
    Retrieve the profile information for the currently authenticated user.

    **Requires authentication**: You must be logged in to access this endpoint.

    Returns user details including organization information.
    """,
)
async def get_me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get current user profile"""
    await db.refresh(current_user, ["organization"])
    return current_user
