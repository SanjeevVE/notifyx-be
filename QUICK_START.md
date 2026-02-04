# Quick Start Guide - API Testing

## 🚀 Start the Server

```bash
cd d:\Own\communication\notifyx-backend
python -m uvicorn app.main:app --reload
```

## 🌐 Access API Documentation

Open your browser and visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **API Root**: http://localhost:8000/

## ✅ CORS Fixed - All Origins Allowed

Your API now accepts requests from:
- ✅ Any localhost port (3000, 5173, 8080, etc.)
- ✅ Any domain
- ✅ Mobile apps
- ✅ Desktop applications
- ✅ Postman, Insomnia, curl

**Configuration:**
- `allow_origins: ["*"]`
- `allow_methods: ["*"]`
- `allow_headers: ["*"]`

## 🔐 Test Authentication in 3 Steps

### Step 1: Create Account
Go to http://localhost:8000/docs and find `POST /api/v1/auth/signup`

```json
{
  "email": "test@example.com",
  "password": "TestPassword123!",
  "full_name": "Test User",
  "organization_name": "My Company"
}
```

### Step 2: Login
Use `POST /api/v1/auth/login`

```
username: test@example.com
password: TestPassword123!
```

Copy the `access_token` from the response.

### Step 3: Authorize
1. Click the **"Authorize"** button (🔓) at the top right of the Swagger UI
2. Enter: `Bearer <paste_your_token_here>`
3. Click **"Authorize"** then **"Close"**

Now all authenticated endpoints will work! Try `GET /api/v1/auth/me`

## 🧪 Automated Testing

Run the test script:

```bash
python test_api.py
```

This will:
- ✅ Test server health
- ✅ Test CORS configuration
- ✅ Create a test user
- ✅ Login and get token
- ✅ Test authenticated endpoints
- ✅ Show you credentials to use in Swagger UI

## 🎫 Generate Test Tokens

```bash
python -m app.core.test_token
```

This generates JWT tokens you can use for testing (requires user to exist in database).

## 📝 Example API Calls

### From JavaScript/Frontend

```javascript
// Login
const loginResponse = await fetch('http://localhost:8000/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: new URLSearchParams({
    username: 'test@example.com',
    password: 'TestPassword123!'
  })
});
const { access_token } = await loginResponse.json();

// Use token for authenticated requests
const meResponse = await fetch('http://localhost:8000/api/v1/auth/me', {
  headers: { 'Authorization': `Bearer ${access_token}` }
});
const userData = await meResponse.json();
```

### From curl

```bash
# Login
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=TestPassword123!"

# Use token (replace YOUR_TOKEN)
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### From Python

```python
import requests

# Login
response = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    data={
        "username": "test@example.com",
        "password": "TestPassword123!"
    }
)
token = response.json()["access_token"]

# Use token
headers = {"Authorization": f"Bearer {token}"}
me_response = requests.get(
    "http://localhost:8000/api/v1/auth/me",
    headers=headers
)
print(me_response.json())
```

## 📚 Available Endpoints

### Public Endpoints (No Auth Required)
- `GET /` - API root
- `GET /health` - Health check
- `POST /api/v1/auth/signup` - Create account
- `POST /api/v1/auth/login` - Get access token

### Protected Endpoints (Auth Required)
- `GET /api/v1/auth/me` - Get current user
- `POST /api/v1/emails/send` - Send email
- `GET /api/v1/emails/messages` - List messages
- `GET /api/v1/campaigns/` - List campaigns
- `POST /api/v1/campaigns/` - Create campaign
- `GET /api/v1/campaigns/{id}` - Get campaign
- `PATCH /api/v1/campaigns/{id}` - Update campaign
- `DELETE /api/v1/campaigns/{id}` - Delete campaign

## 🛠️ Troubleshooting

### "Could not validate credentials"
- Make sure you clicked "Authorize" and entered the token correctly
- Token format: `Bearer YOUR_TOKEN` (the word "Bearer" + space + token)
- Check that token hasn't expired (default: 30 minutes)

### CORS errors
- CORS is configured to allow all origins - should work everywhere
- Check if server is actually running
- Try clearing browser cache

### "Database connection failed"
- Make sure PostgreSQL is running
- Check `.env` file has correct `DATABASE_URL`
- Run: `python init_db.py` to initialize database

### AWS SES errors
- Check `.env` has correct AWS credentials
- Verify sender email in AWS SES
- Check AWS SES sandbox restrictions

## 📁 New Files Created

1. **`API_TESTING.md`** - Comprehensive testing guide
2. **`test_api.py`** - Automated test script
3. **`app/core/test_token.py`** - Token generator utility
4. **`CHANGELOG_CORS_AUTH.md`** - Detailed changes log
5. **`QUICK_START.md`** - This file!

## 🔒 Production Security Notes

Before deploying to production:

1. **Update CORS** in `app/main.py`:
   ```python
   allow_origins=["https://yourdomain.com"],
   allow_credentials=True,
   ```

2. **Set strong secrets** in `.env`:
   ```
   SECRET_KEY=<generate-strong-random-key>
   DEBUG=False
   ```

3. **Use HTTPS** only
4. **Implement rate limiting**
5. **Set up monitoring**
6. **Restrict AWS IAM permissions**

## 🎉 You're All Set!

1. ✅ CORS fixed - accessible from anywhere
2. ✅ Authentication working with clear docs
3. ✅ Swagger UI configured for easy testing
4. ✅ Test scripts available
5. ✅ Token generator ready

**Start testing**: http://localhost:8000/docs

Need more details? Check:
- `API_TESTING.md` - Full testing guide
- `CHANGELOG_CORS_AUTH.md` - What changed and why
