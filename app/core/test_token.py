"""
Test Token Generator for API Testing

This module provides utilities to generate test tokens for API documentation and testing.
DO NOT use these in production!
"""

from datetime import datetime, timedelta
from app.core.security import create_access_token


def generate_test_token(user_id: int = 1, hours: int = 24) -> str:
    """
    Generate a test token for API testing

    Args:
        user_id: The user ID to encode in the token
        hours: How many hours the token should be valid

    Returns:
        A JWT token string
    """
    expires_delta = timedelta(hours=hours)
    token = create_access_token(
        data={"sub": str(user_id)},
        expires_delta=expires_delta
    )
    return token


def print_test_tokens():
    """
    Print test tokens for different scenarios
    Useful for API testing and documentation
    """
    print("\n=== TEST TOKENS FOR API TESTING ===\n")

    # Token for user ID 1 (24 hours)
    token_1 = generate_test_token(user_id=1, hours=24)
    print("User ID 1 (24 hours validity):")
    print(f"Bearer {token_1}\n")

    # Token for user ID 2 (24 hours)
    token_2 = generate_test_token(user_id=2, hours=24)
    print("User ID 2 (24 hours validity):")
    print(f"Bearer {token_2}\n")

    # Long-lived token for testing (30 days)
    token_long = generate_test_token(user_id=1, hours=24*30)
    print("Long-lived token for User ID 1 (30 days validity):")
    print(f"Bearer {token_long}\n")

    print("=== HOW TO USE ===")
    print("1. Copy the entire 'Bearer <token>' string")
    print("2. Go to /docs in your browser")
    print("3. Click the 'Authorize' button (🔓)")
    print("4. Paste the token in the 'Value' field")
    print("5. Click 'Authorize' and then 'Close'\n")
    print("NOTE: Make sure the user exists in your database!\n")


if __name__ == "__main__":
    print_test_tokens()
