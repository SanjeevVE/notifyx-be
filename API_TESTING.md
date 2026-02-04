# API Testing Guide

This guide will help you test the Email Communication Platform API using the interactive documentation.

## Quick Start

1. **Start the server**
   ```bash
   python -m uvicorn app.main:app --reload
   ```

2. **Access the API documentation**
   - Open your browser and go to: `http://localhost:8000/docs`
   - Alternative ReDoc format: `http://localhost:8000/redoc`

## Authentication Testing

### Method 1: Using Real Credentials (Recommended)

1. **Create a new account**
   - Go to `/docs` in your browser
   - Find the `POST /api/v1/auth/signup` endpoint
   - Click "Try it out"
   - Fill in the request body:
     ```json
     {
       "email": "test@example.com",
       "password": "TestPassword123!",
       "full_name": "Test User",
       "organization_name": "Test Organization"
     }
     ```
   - Click "Execute"

2. **Login to get a token**
   - Find the `POST /api/v1/auth/login` endpoint
   - Click "Try it out"
   - Fill in the form:
     - username: `test@example.com` (use email as username)
     - password: `TestPassword123!`
   - Click "Execute"
   - Copy the `access_token` from the response

3. **Authorize in Swagger UI**
   - Click the "Authorize" button (🔓) at the top right
   - In the "Value" field, enter: `Bearer YOUR_ACCESS_TOKEN`
     (Replace `YOUR_ACCESS_TOKEN` with the token from step 2)
   - Click "Authorize" and then "Close"

4. **Test protected endpoints**
   - Now you can test any endpoint that requires authentication
   - Try `GET /api/v1/auth/me` to verify it works

### Method 2: Using Generated Test Tokens (For Development)

1. **Generate a test token**
   ```bash
   cd d:\Own\communication\notifyx-backend
   python -m app.core.test_token
   ```
   This will print test tokens you can use.

2. **Use the token**
   - Copy one of the generated tokens (including "Bearer")
   - Click the "Authorize" button (🔓) in the Swagger UI
   - Paste the entire string
   - Click "Authorize" and then "Close"

   **Note**: The user ID in the token must exist in your database!

## Testing Different Endpoints

### Authentication Endpoints
- `POST /api/v1/auth/signup` - Create a new user (no auth required)
- `POST /api/v1/auth/login` - Login and get token (no auth required)
- `GET /api/v1/auth/me` - Get current user info (auth required)

### Email Endpoints
- `POST /api/v1/emails/send` - Send a single email (auth required)
- `GET /api/v1/emails/verify/{email}` - Verify email identity in AWS SES (auth required)
- `GET /api/v1/emails/verify-status/{email}` - Check verification status (auth required)
- `GET /api/v1/emails/messages` - Get all sent messages (auth required)
- `GET /api/v1/emails/messages/{message_id}` - Get specific message (auth required)

### Campaign Endpoints
- `POST /api/v1/campaigns/` - Create a new campaign (auth required)
- `GET /api/v1/campaigns/` - Get all campaigns (auth required)
- `GET /api/v1/campaigns/{campaign_id}` - Get specific campaign (auth required)
- `PATCH /api/v1/campaigns/{campaign_id}` - Update campaign (auth required)
- `DELETE /api/v1/campaigns/{campaign_id}` - Delete campaign (auth required)

## CORS Configuration

The API is configured to accept requests from **any origin** for development purposes.

**CORS Settings:**
- ✅ Allow all origins (`*`)
- ✅ Allow all methods (GET, POST, PUT, DELETE, etc.)
- ✅ Allow all headers
- ✅ Expose all headers
- ⚠️ Credentials disabled (required when allowing all origins)

**For Production:**
Update `app/core/config.py` to restrict origins:
```python
BACKEND_CORS_ORIGINS: list = [
    "https://yourdomain.com",
    "https://app.yourdomain.com"
]
```

## Common Issues

### Issue: "Could not validate credentials"
**Solution**:
- Make sure you've authorized with a valid token
- Check that the token hasn't expired
- Verify the user exists in the database

### Issue: "CORS error in browser"
**Solution**:
- The server is configured to allow all origins
- Make sure the server is running
- Check browser console for specific CORS errors

### Issue: "Email sending fails"
**Solution**:
- Verify AWS credentials in `.env` file
- Check that the sender email is verified in AWS SES
- Review AWS SES sandbox restrictions

## Sample Request Bodies

### Send Email
```json
{
  "to_email": "recipient@example.com",
  "to_name": "Recipient Name",
  "subject": "Test Email",
  "html_content": "<h1>Hello!</h1><p>This is a test email.</p>",
  "text_content": "Hello! This is a test email.",
  "from_email": "sender@yourdomain.com",
  "from_name": "Your Name",
  "reply_to": "reply@yourdomain.com"
}
```

### Create Campaign
```json
{
  "name": "Newsletter Campaign",
  "subject": "Monthly Newsletter",
  "from_name": "Your Company",
  "from_email": "newsletter@yourdomain.com",
  "reply_to": "support@yourdomain.com",
  "html_content": "<h1>Newsletter</h1><p>Content here</p>",
  "text_content": "Newsletter - Content here",
  "scheduled_at": "2024-12-31T10:00:00Z"
}
```

## Environment Variables

Make sure your `.env` file contains:
```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost/dbname
SECRET_KEY=your-secret-key-here
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_REGION=us-east-1
SES_SENDER_EMAIL=verified@yourdomain.com
REDIS_URL=redis://localhost:6379/0
DEBUG=True
```

## Useful Commands

```bash
# Run the server
python -m uvicorn app.main:app --reload

# Generate test tokens
python -m app.core.test_token

# Initialize the database
python init_db.py

# Seed test data
python seed.py
```

## Security Notes

⚠️ **Important for Production:**
1. Change `allow_origins=["*"]` to specific domains
2. Enable `allow_credentials=True` after restricting origins
3. Use strong `SECRET_KEY` in production
4. Never commit `.env` file to version control
5. Rotate tokens regularly
6. Implement rate limiting
7. Use HTTPS in production

## Additional Resources

- FastAPI Documentation: https://fastapi.tiangolo.com/
- Swagger UI Guide: https://swagger.io/docs/open-source-tools/swagger-ui/
- OAuth2 Password Flow: https://fastapi.tiangolo.com/tutorial/security/first-steps/
