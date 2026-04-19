# app.py - Premium Email Verification API with 24-Hour Expiry
import os
import re
import json
import secrets
import smtplib
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ==========================================
# CONFIGURATION
# ==========================================

class Config:
    """Application configuration"""
    GMAIL_EMAIL = os.getenv('GMAIL_EMAIL', 'sgexploits@gmail.com')
    GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD', 'clraykmizipllrgs')
    VERIFICATION_TOKEN_EXPIRY_HOURS = 24  # Fixed 24 hours expiry
    SMTP_SERVER = 'smtp.gmail.com'
    SMTP_PORT = 587
    COMPANY_NAME = "SG EXPLOITS"
    COMPANY_LOGO_URL = "https://i.ibb.co/wNvw1Fsm/IMG-20260319-205918.jpg"
    JSON_FILE_PATH = '/tmp/users.json'  # Use /tmp for Vercel serverless

config = Config()

# ==========================================
# LOGGING SETUP
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==========================================
# JSON FILE STORAGE
# ==========================================

class JSONStorage:
    """Handle JSON file storage for users data"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Create JSON file if it doesn't exist"""
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                json.dump({}, f, indent=2)
            logger.info(f"Created {self.file_path}")
    
    def _read_data(self) -> Dict:
        """Read data from JSON file"""
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    def _write_data(self, data: Dict):
        """Write data to JSON file"""
        with open(self.file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def get_user(self, email: str) -> Optional[Dict]:
        """Get user data by email"""
        data = self._read_data()
        return data.get(email)
    
    def save_user(self, email: str, user_data: Dict):
        """Save or update user data"""
        data = self._read_data()
        data[email] = user_data
        self._write_data(data)
        logger.info(f"User data saved for {email}")
    
    def delete_user(self, email: str):
        """Delete user data"""
        data = self._read_data()
        if email in data:
            del data[email]
            self._write_data(data)
            logger.info(f"User data deleted for {email}")
    
    def get_all_users(self) -> Dict:
        """Get all users data"""
        return self._read_data()
    
    def cleanup_expired(self):
        """Remove expired verification tokens"""
        data = self._read_data()
        modified = False
        now = datetime.now()
        
        for email, user_data in list(data.items()):
            if 'token' in user_data and 'token_expires_at' in user_data:
                expires_at = datetime.fromisoformat(user_data['token_expires_at'])
                if expires_at < now and not user_data.get('verified', False):
                    user_data['token'] = None
                    user_data['token_expires_at'] = None
                    user_data['token_created_at'] = None
                    modified = True
        
        if modified:
            self._write_data(data)
            logger.info("Cleaned up expired tokens")

# Initialize JSON storage
db = JSONStorage(config.JSON_FILE_PATH)

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def validate_email(email: str) -> Tuple[bool, str]:
    """Validate email format"""
    if not email:
        return False, "Email is required"
    
    email = email.strip().lower()
    
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return False, "Invalid email format"
    
    return True, email

def generate_verification_token() -> str:
    """Generate secure verification token"""
    return secrets.token_urlsafe(32)

def get_base_url() -> str:
    """Automatically get base URL from request"""
    if request.host.startswith('localhost') or request.host.startswith('127.0.0.1'):
        return f"http://{request.host}"
    else:
        return f"https://{request.host}"

def create_premium_email_template(recipient: str, verification_link: str, expiry_hours: int) -> str:
    """Clean, minimal, mobile-optimized email template"""
    
    current_year = datetime.now().year
    recipient_name = recipient.split('@')[0]
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
    <title>Verify Email - {config.COMPANY_NAME}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            margin: 0;
            padding: 0;
            background: #f5f5f5;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.4;
        }}
        .email-container {{
            max-width: 450px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 20px;
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 35px 20px;
            text-align: center;
        }}
        .logo {{
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: white;
            padding: 3px;
            margin-bottom: 12px;
        }}
        .company-name {{
            color: white;
            font-size: 22px;
            font-weight: 700;
            letter-spacing: -0.3px;
        }}
        .content {{
            padding: 30px 24px;
        }}
        .greeting {{
            font-size: 20px;
            font-weight: 600;
            color: #1a202c;
            margin-bottom: 8px;
        }}
        .message {{
            color: #4a5568;
            font-size: 15px;
            margin-bottom: 28px;
            line-height: 1.5;
        }}
        .btn-container {{
            text-align: center;
            margin: 25px 0;
        }}
        .verify-btn {{
            display: inline-block;
            background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
            color: white;
            text-decoration: none;
            padding: 14px 32px;
            border-radius: 50px;
            font-weight: 600;
            font-size: 16px;
            text-align: center;
            box-shadow: 0 6px 20px rgba(220, 38, 38, 0.25);
            width: 100%;
            max-width: 280px;
        }}
        .info-box {{
            background: #f7fafc;
            border-radius: 14px;
            padding: 16px;
            margin: 25px 0;
            border: 1px solid #e2e8f0;
        }}
        .info-row {{
            padding: 8px 0;
            font-size: 13px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
        }}
        .info-label {{
            color: #4a5568;
            font-weight: 500;
        }}
        .info-value {{
            color: #e53e3e;
            font-weight: 600;
        }}
        .footer {{
            text-align: center;
            padding: 20px 24px;
            border-top: 1px solid #e2e8f0;
        }}
        .footer-text {{
            color: #a0aec0;
            font-size: 11px;
            margin: 5px 0;
        }}
        @media only screen and (max-width: 480px) {{
            .content {{
                padding: 24px 20px;
            }}
            .greeting {{
                font-size: 18px;
            }}
            .message {{
                font-size: 14px;
            }}
            .verify-btn {{
                padding: 12px 24px;
                font-size: 15px;
            }}
            .info-row {{
                font-size: 12px;
            }}
        }}
    </style>
</head>
<body style="margin: 0; padding: 20px 12px; background: #f5f5f5;">
    <div class="email-container" style="max-width: 450px; margin: 0 auto; background: #ffffff; border-radius: 20px; overflow: hidden;">
        
        <div class="header" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 35px 20px; text-align: center;">
            <img src="{config.COMPANY_LOGO_URL}" alt="{config.COMPANY_NAME}" class="logo" style="width: 60px; height: 60px; border-radius: 50%; background: white; padding: 3px; margin-bottom: 12px;">
            <div class="company-name" style="color: white; font-size: 22px; font-weight: 700;">{config.COMPANY_NAME}</div>
        </div>
        
        <div class="content" style="padding: 30px 24px;">
            <div class="greeting" style="font-size: 20px; font-weight: 600; color: #1a202c; margin-bottom: 8px;">Hi {recipient_name}!</div>
            <div class="message" style="color: #4a5568; font-size: 15px; margin-bottom: 28px;">Verify your email to get started.</div>
            
            <div class="btn-container" style="text-align: center; margin: 25px 0;">
                <a href="{verification_link}" class="verify-btn" style="display: inline-block; background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%); color: white; text-decoration: none; padding: 14px 32px; border-radius: 50px; font-weight: 600; font-size: 16px; box-shadow: 0 6px 20px rgba(220, 38, 38, 0.25); width: 100%; max-width: 280px; text-align: center;">Verify Email</a>
            </div>
            
            <div class="info-box" style="background: #f7fafc; border-radius: 14px; padding: 16px; margin: 25px 0; border: 1px solid #e2e8f0;">
                <div class="info-row" style="padding: 6px 0; font-size: 13px; display: flex; justify-content: space-between;">
                    <span class="info-label" style="color: #4a5568;">⏰ Expires in</span>
                    <span class="info-value" style="color: #e53e3e; font-weight: 600;">{expiry_hours} hours</span>
                </div>
                <div class="info-row" style="padding: 6px 0; font-size: 13px; display: flex; justify-content: space-between;">
                    <span class="info-label" style="color: #4a5568;">🔒 Security</span>
                    <span class="info-value" style="color: #2d3748;">One-time use</span>
                </div>
            </div>
        </div>
        
        <div class="footer" style="text-align: center; padding: 20px 24px; border-top: 1px solid #e2e8f0;">
            <div class="footer-text" style="color: #a0aec0; font-size: 11px;">© {current_year} {config.COMPANY_NAME}</div>
            <div class="footer-text" style="color: #a0aec0; font-size: 10px;">Sent to {recipient}</div>
        </div>
        
    </div>
</body>
</html>"""

def send_verification_email(recipient: str, verification_link: str) -> Tuple[bool, str]:
    """Send premium verification email via Gmail SMTP"""
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{config.COMPANY_NAME} <{config.GMAIL_EMAIL}>"
        msg['To'] = recipient
        msg['Subject'] = f"Verify Your Email - {config.COMPANY_NAME}"
        msg['X-MC-GoogleAnalytics'] = 'no'
        msg['X-Entity-Ref-ID'] = secrets.token_urlsafe(16)
        msg['Auto-Submitted'] = 'auto-generated'
        msg['Precedence'] = 'bulk'
        
        plain_text = f"""{config.COMPANY_NAME} - Email Verification

Hi {recipient.split('@')[0]}!

Verify your email to get started.

Click this link to verify:
{verification_link}

This link expires in {config.VERIFICATION_TOKEN_EXPIRY_HOURS} hours and can only be used once.

© {datetime.now().year} {config.COMPANY_NAME}"""
        
        html_content = create_premium_email_template(recipient, verification_link, config.VERIFICATION_TOKEN_EXPIRY_HOURS)
        
        msg.attach(MIMEText(plain_text, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))
        
        server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
        server.starttls()
        server.login(config.GMAIL_EMAIL, config.GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Premium verification email sent to {recipient}")
        return True, "Verification email sent successfully"
        
    except Exception as e:
        logger.error(f"Email sending failed: {str(e)}")
        return False, f"Failed to send email: {str(e)}"

# ==========================================
# FLASK APPLICATION
# ==========================================

app = Flask(__name__)
CORS(app)

@app.before_request
def cleanup():
    db.cleanup_expired()

# ==========================================
# API ENDPOINTS
# ==========================================

@app.route('/send=<email>', methods=['GET'])
def send_verification_link(email):
    valid, result = validate_email(email)
    if not valid:
        return jsonify({
            'success': False,
            'message': result,
            'timestamp': datetime.now().isoformat()
        }), 400
    
    email = result
    user_data = db.get_user(email)
    
    if user_data and user_data.get('verified', False):
        return jsonify({
            'success': False,
            'message': 'Email already verified',
            'data': {
                'email': email,
                'verified': True,
                'verified_at': user_data.get('verified_at')
            },
            'timestamp': datetime.now().isoformat()
        }), 400
    
    token = generate_verification_token()
    expires_at = datetime.now() + timedelta(hours=24)
    base_url = get_base_url()
    verification_link = f"{base_url}/verify/confirm/{token}"
    
    if not user_data:
        user_data = {
            'email': email,
            'verified': False,
            'created_at': datetime.now().isoformat(),
            'token': token,
            'token_created_at': datetime.now().isoformat(),
            'token_expires_at': expires_at.isoformat(),
            'verification_link_sent_count': 1,
            'last_verification_sent': datetime.now().isoformat()
        }
    else:
        user_data['token'] = token
        user_data['token_created_at'] = datetime.now().isoformat()
        user_data['token_expires_at'] = expires_at.isoformat()
        user_data['verification_link_sent_count'] = user_data.get('verification_link_sent_count', 0) + 1
        user_data['last_verification_sent'] = datetime.now().isoformat()
    
    db.save_user(email, user_data)
    success, message = send_verification_email(email, verification_link)
    
    if success:
        return jsonify({
            'success': True,
            'message': f'Verification link sent to {email}',
            'data': {
                'email': email,
                'expires_in_hours': 24,
                'expires_at': expires_at.isoformat(),
                'verification_link': verification_link
            },
            'timestamp': datetime.now().isoformat()
        }), 200
    else:
        user_data['token'] = None
        db.save_user(email, user_data)
        return jsonify({
            'success': False,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/verify/confirm/<token>', methods=['GET'])
def confirm_verification(token):
    all_users = db.get_all_users()
    email = None
    user_data = None
    
    for user_email, data in all_users.items():
        if data.get('token') == token:
            email = user_email
            user_data = data
            break
    
    if not email or not user_data:
        return jsonify({
            'success': False,
            'message': 'Invalid or expired verification link',
            'timestamp': datetime.now().isoformat()
        }), 404
    
    if user_data.get('verified', False):
        return jsonify({
            'success': False,
            'message': 'Email already verified',
            'data': {
                'email': email,
                'verified': True,
                'verified_at': user_data.get('verified_at')
            },
            'timestamp': datetime.now().isoformat()
        }), 400
    
    if 'token_expires_at' in user_data:
        expires_at = datetime.fromisoformat(user_data['token_expires_at'])
        if datetime.now() > expires_at:
            return jsonify({
                'success': False,
                'message': 'Verification link has expired (24 hours). Please request a new one',
                'timestamp': datetime.now().isoformat()
            }), 410
    
    user_data['verified'] = True
    user_data['verified_at'] = datetime.now().isoformat()
    user_data['token'] = None
    db.save_user(email, user_data)
    
    return jsonify({
        'success': True,
        'message': 'Email verified successfully!',
        'data': {
            'email': email,
            'verified': True,
            'verified_at': user_data['verified_at']
        },
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/verified/check=<email>', methods=['GET'])
def check_verification(email):
    valid, result = validate_email(email)
    if not valid:
        return jsonify({
            'success': False,
            'message': result,
            'timestamp': datetime.now().isoformat()
        }), 400
    
    email = result
    user_data = db.get_user(email)
    
    if not user_data:
        return jsonify({
            'success': True,
            'verified': False,
            'message': 'Email not found in system',
            'data': {
                'email': email,
                'verified': False,
                'exists': False
            },
            'timestamp': datetime.now().isoformat()
        }), 200
    
    is_verified = user_data.get('verified', False)
    
    if is_verified:
        return jsonify({
            'success': True,
            'verified': True,
            'message': 'Email is verified',
            'data': {
                'email': email,
                'verified': True,
                'verified_at': user_data.get('verified_at'),
                'created_at': user_data.get('created_at')
            },
            'timestamp': datetime.now().isoformat()
        }), 200
    else:
        has_valid_token = False
        expires_in_hours = None
        
        if 'token_expires_at' in user_data and user_data.get('token'):
            expires_at = datetime.fromisoformat(user_data['token_expires_at'])
            if datetime.now() < expires_at:
                has_valid_token = True
                remaining = (expires_at - datetime.now()).total_seconds() / 3600
                expires_in_hours = round(remaining, 1)
        
        return jsonify({
            'success': True,
            'verified': False,
            'message': 'Email not verified yet',
            'data': {
                'email': email,
                'verified': False,
                'has_pending_verification': has_valid_token,
                'expires_in_hours': expires_in_hours,
                'verification_sent_count': user_data.get('verification_link_sent_count', 0),
                'last_verification_sent': user_data.get('last_verification_sent'),
                'created_at': user_data.get('created_at')
            },
            'timestamp': datetime.now().isoformat()
        }), 200

@app.route('/users', methods=['GET'])
def get_all_users():
    all_users = db.get_all_users()
    
    for email, user_data in all_users.items():
        if 'token' in user_data:
            user_data['token'] = '***HIDDEN***'
    
    return jsonify({
        'success': True,
        'total_users': len(all_users),
        'users': all_users,
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/', methods=['GET'])
def home():
    base_url = get_base_url()
    return jsonify({
        'name': f'{config.COMPANY_NAME} - Premium Email Verification API',
        'version': '6.0.0',
        'description': 'Clean, mobile-optimized email verification with 24-hour expiry',
        'base_url': base_url,
        'verification_expiry': '24 hours',
        'endpoints': {
            'send_verification_link': {
                'url': f'{base_url}/send={{email}}',
                'method': 'GET',
                'example': f'{base_url}/send=user@gmail.com',
                'description': 'Send verification link to email'
            },
            'check_verification_status': {
                'url': f'{base_url}/verified/check={{email}}',
                'method': 'GET',
                'example': f'{base_url}/verified/check=user@gmail.com',
                'description': 'Check if email is verified'
            },
            'get_all_users': {
                'url': f'{base_url}/users',
                'method': 'GET',
                'description': 'Get all users data'
            }
        },
        'email_template_features': {
            'design': 'Clean & Minimal',
            'mobile_optimized': True,
            'max_width': '450px',
            'red_verification_button': True,
            'no_quoted_text': True,
            'no_security_warning': True,
            'responsive': True,
            'auto_base_url': True
        },
        'timestamp': datetime.now().isoformat()
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'message': 'Endpoint not found. Use /send={email} or /verified/check={email}',
        'timestamp': datetime.now().isoformat()
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'message': 'Internal server error',
        'timestamp': datetime.now().isoformat()
    }), 500

# For Vercel serverless deployment
app.debug = False

# ==========================================
# MAIN ENTRY POINT
# ==========================================

if __name__ == '__main__':
    print("\n" + "="*70)
    print(f"✨ {config.COMPANY_NAME} - PREMIUM EMAIL VERIFICATION API")
    print("="*70)
    print(f"\n✅ Server running on: http://localhost:5000")
    print(f"✅ Verification Expiry: 24 HOURS")
    print(f"✅ JSON Storage: {config.JSON_FILE_PATH}")
    print(f"✅ AUTO BASE URL DETECTION: ENABLED")
    print("\n" + "="*70 + "\n")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True
    )