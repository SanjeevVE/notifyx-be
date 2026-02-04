"""
Quick API Test Script

This script demonstrates how to interact with the Email Communication Platform API.
It tests signup, login, and authenticated endpoints.
"""

import requests
import json
from datetime import datetime

# API Base URL
BASE_URL = "http://localhost:8000/api/v1"

def print_response(title, response):
    """Pretty print API response"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Status Code: {response.status_code}")
    print(f"Response:")
    try:
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text)
    print(f"{'='*60}\n")


def test_health():
    """Test health endpoint (no auth required)"""
    print("\n🔍 Testing Health Endpoint...")
    response = requests.get("http://localhost:8000/health")
    print_response("Health Check", response)
    return response.status_code == 200


def test_signup():
    """Test user signup"""
    print("\n📝 Testing User Signup...")

    # Generate unique email with timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    email = f"test_{timestamp}@example.com"

    data = {
        "email": email,
        "password": "TestPassword123!",
        "full_name": "Test User",
        "organization_name": "Test Organization"
    }

    response = requests.post(f"{BASE_URL}/auth/signup", json=data)
    print_response("User Signup", response)

    if response.status_code == 201:
        print(f"✅ User created successfully!")
        return email, data["password"]
    else:
        print(f"❌ Signup failed")
        return None, None


def test_login(email, password):
    """Test user login"""
    print("\n🔐 Testing User Login...")

    data = {
        "username": email,  # OAuth2 uses 'username' field
        "password": password
    }

    response = requests.post(
        f"{BASE_URL}/auth/login",
        data=data,  # OAuth2 uses form data, not JSON
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    print_response("User Login", response)

    if response.status_code == 200:
        token = response.json()["access_token"]
        print(f"✅ Login successful!")
        print(f"🎫 Token: {token[:50]}...")
        return token
    else:
        print(f"❌ Login failed")
        return None


def test_get_me(token):
    """Test getting current user profile"""
    print("\n👤 Testing Get Current User...")

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    print_response("Get Current User", response)

    return response.status_code == 200


def test_get_campaigns(token):
    """Test getting campaigns"""
    print("\n📧 Testing Get Campaigns...")

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.get(f"{BASE_URL}/campaigns/", headers=headers)
    print_response("Get Campaigns", response)

    return response.status_code == 200


def test_cors():
    """Test CORS headers"""
    print("\n🌐 Testing CORS Configuration...")

    headers = {
        "Origin": "http://example.com"
    }

    response = requests.get("http://localhost:8000/health", headers=headers)

    print(f"Status Code: {response.status_code}")
    print("\nCORS Headers:")
    print(f"  Access-Control-Allow-Origin: {response.headers.get('access-control-allow-origin', 'Not present')}")
    print(f"  Access-Control-Allow-Methods: {response.headers.get('access-control-allow-methods', 'Not present')}")
    print(f"  Access-Control-Allow-Headers: {response.headers.get('access-control-allow-headers', 'Not present')}")

    if response.headers.get('access-control-allow-origin') == '*':
        print("\n✅ CORS is configured to allow all origins")
        return True
    else:
        print("\n⚠️  CORS might be restricted")
        return False


def main():
    """Run all tests"""
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║                                                            ║
    ║     Email Communication Platform API Test Suite           ║
    ║                                                            ║
    ╚════════════════════════════════════════════════════════════╝
    """)

    print("📍 Testing API at:", BASE_URL)
    print("\nMake sure the server is running:")
    print("  python -m uvicorn app.main:app --reload\n")

    try:
        # Test 1: Health check
        if not test_health():
            print("\n❌ Server is not running or health check failed!")
            print("Start the server with: python -m uvicorn app.main:app --reload")
            return

        # Test 2: CORS
        test_cors()

        # Test 3: Signup
        email, password = test_signup()
        if not email:
            print("\n❌ Cannot continue without successful signup")
            return

        # Test 4: Login
        token = test_login(email, password)
        if not token:
            print("\n❌ Cannot continue without successful login")
            return

        # Test 5: Get current user
        test_get_me(token)

        # Test 6: Get campaigns
        test_get_campaigns(token)

        print("\n" + "="*60)
        print("✅ ALL TESTS COMPLETED!")
        print("="*60)
        print("\nYou can now use these credentials to test in Swagger UI:")
        print(f"  📧 Email: {email}")
        print(f"  🔑 Password: {password}")
        print(f"  🎫 Token: Bearer {token[:50]}...")
        print("\n🌐 Open API Docs: http://localhost:8000/docs")
        print("\n" + "="*60)

    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Cannot connect to the API server!")
        print("Make sure the server is running on http://localhost:8000")
        print("Start it with: python -m uvicorn app.main:app --reload")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()
