import urllib.request
import urllib.error
import time
import threading
import json
import os
import sys
from datetime import datetime, timedelta
import ssl
from queue import Queue
import hashlib
import uuid

# ========== CONFIGURATION ==========
TELEGRAM_BOT_TOKEN = "8576884721:AAGav9gpADYPwVjyXC0CEMEoQ99jV2qP4WI"
ADMIN_USER_IDS = [7643067854]

# Data files
URL_DATA_FILE = "url_data.json"
USER_DATA_FILE = "user_data.json"
PREMIUM_PLANS_FILE = "premium_plans.json"
SETTINGS_FILE = "user_settings.json"

# Updated Premium settings - ALL USERS SAME INTERVAL
PREMIUM_FEATURES = {
    'max_urls': {
        'free': 1,      # FREE: Only 1 URL
        'premium': 100  # PREMIUM: 100 URLs
    },
    'ping_interval': {
        'free': 300,    # 5 minutes for ALL users
        'premium': 300  # 5 minutes for ALL users (NOT 1 minute)
    },
    'concurrent_pings': {
        'free': 1,
        'premium': 5
    },
    'features': {
        'free': ['Basic monitoring', '1 URL max', '5 min interval'],
        'premium': ['Priority monitoring', '100 URLs max', '5 min interval', 'Concurrent pings', 'Advanced alerts']
    }
}

# Premium plans (days, price)
PREMIUM_PLANS = {
    '7': {'days': 7, 'price': 2.99},
    '30': {'days': 30, 'price': 9.99},
    '90': {'days': 90, 'price': 24.99},
    '365': {'days': 365, 'price': 79.99}
}

# ========== LOGGING SETUP ==========
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ========== DATA MANAGEMENT ==========
def load_urls():
    """Load all URLs from JSON file"""
    if os.path.exists(URL_DATA_FILE):
        try:
            with open(URL_DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                converted = {}
                for user_id_str, urls in data.items():
                    converted[int(user_id_str)] = urls
                return converted
        except Exception as e:
            logger.error(f"Error loading URLs: {e}")
            return {}
    return {}

def save_urls(all_urls):
    """Save all URLs to JSON file"""
    try:
        converted = {str(k): v for k, v in all_urls.items()}
        with open(URL_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(converted, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving URLs: {e}")
        return False

def load_user_data():
    """Load user data"""
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                converted = {}
                for user_id_str, user_info in data.items():
                    converted[int(user_id_str)] = user_info
                return converted
        except Exception as e:
            logger.error(f"Error loading user data: {e}")
            return {}
    return {}

def save_user_data(user_data):
    """Save user data"""
    try:
        converted = {str(k): v for k, v in user_data.items()}
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(converted, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving user data: {e}")
        return False

def load_user_settings():
    """Load user settings"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                converted = {}
                for user_id_str, settings in data.items():
                    converted[int(user_id_str)] = settings
                return converted
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            return {}
    return {}

def save_user_settings(settings_data):
    """Save user settings"""
    try:
        converted = {str(k): v for k, v in settings_data.items()}
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(converted, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return False

def get_user_settings(user_id):
    """Get user settings"""
    settings_data = load_user_settings()
    if user_id not in settings_data:
        settings_data[user_id] = {
            'notifications': True,  # Default: notifications ON
            'auto_ping': True,      # Default: auto ping ON
            'compact_view': False   # Default: detailed view
        }
        save_user_settings(settings_data)
    return settings_data[user_id]

def update_user_settings(user_id, key, value):
    """Update user setting"""
    settings_data = load_user_settings()
    if user_id not in settings_data:
        settings_data[user_id] = {}
    settings_data[user_id][key] = value
    save_user_settings(settings_data)

def get_user_urls(user_id):
    """Get URLs for specific user"""
    all_urls = load_urls()
    return all_urls.get(user_id, {})

def save_user_urls(user_id, urls):
    """Save URLs for specific user"""
    all_urls = load_urls()
    all_urls[user_id] = urls
    return save_urls(all_urls)

def get_user_info(user_id):
    """Get user information"""
    user_data = load_user_data()
    if user_id not in user_data:
        user_data[user_id] = {
            'is_premium': False,
            'join_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'last_active': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'premium_until': None,
            'premium_history': []
        }
        save_user_data(user_data)
    return user_data[user_id]

def update_user_active(user_id):
    """Update user's last active time"""
    user_data = load_user_data()
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['last_active'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_user_data(user_data)

def set_user_premium(user_id, days=30, admin_id=None):
    """Set user premium status with expiration"""
    user_data = load_user_data()
    if user_id not in user_data:
        user_data[user_id] = {}
    
    now = datetime.now()
    if 'premium_until' in user_data[user_id] and user_data[user_id]['premium_until']:
        try:
            current_until = datetime.strptime(user_data[user_id]['premium_until'], "%Y-%m-%d %H:%M:%S")
            if current_until > now:
                # Extend existing premium
                new_until = current_until + timedelta(days=days)
            else:
                # Start new premium
                new_until = now + timedelta(days=days)
        except:
            new_until = now + timedelta(days=days)
    else:
        new_until = now + timedelta(days=days)
    
    user_data[user_id]['is_premium'] = True
    user_data[user_id]['premium_until'] = new_until.strftime("%Y-%m-%d %H:%M:%S")
    user_data[user_id]['premium_since'] = now.strftime("%Y-%m-%d %H:%M:%S")
    
    # Add to history
    if 'premium_history' not in user_data[user_id]:
        user_data[user_id]['premium_history'] = []
    
    user_data[user_id]['premium_history'].append({
        'activated_by': admin_id,
        'days': days,
        'activated_at': now.strftime("%Y-%m-%d %H:%M:%S"),
        'expires_at': new_until.strftime("%Y-%m-%d %H:%M:%S")
    })
    
    save_user_data(user_data)
    return new_until

def remove_user_premium(user_id):
    """Remove premium from user"""
    user_data = load_user_data()
    if user_id in user_data:
        user_data[user_id]['is_premium'] = False
        user_data[user_id]['premium_until'] = None
        save_user_data(user_data)
    return True

def check_premium_expiry():
    """Check and expire premium users"""
    user_data = load_user_data()
    now = datetime.now()
    expired_users = []
    
    for user_id, info in user_data.items():
        if info.get('is_premium', False) and info.get('premium_until'):
            try:
                expiry_date = datetime.strptime(info['premium_until'], "%Y-%m-%d %H:%M:%S")
                if expiry_date < now:
                    info['is_premium'] = False
                    info['premium_expired_at'] = now.strftime("%Y-%m-%d %H:%M:%S")
                    expired_users.append(user_id)
            except:
                pass
    
    if expired_users:
        save_user_data(user_data)
        logger.info(f"Expired premium for users: {expired_users}")
    
    return expired_users

# ========== URL PINGING FUNCTION ==========
def ping_url_advanced(url, url_name, user_id=None):
    """Advanced ping function"""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Cache-Control': 'max-age=0'
        }
        
        req = urllib.request.Request(url, headers=headers)
        start_time = time.time()
        
        try:
            with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                response_time = time.time() - start_time
                status_code = response.getcode()
                
                return {
                    "success": True,
                    "status_code": status_code,
                    "response_time": response_time,
                    "response_time_str": f"{response_time:.2f}s",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "url": url,
                    "name": url_name
                }
        except:
            with urllib.request.urlopen(req, timeout=10) as response:
                response_time = time.time() - start_time
                status_code = response.getcode()
                
                return {
                    "success": True,
                    "status_code": status_code,
                    "response_time": response_time,
                    "response_time_str": f"{response_time:.2f}s",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "url": url,
                    "name": url_name
                }
                
    except urllib.error.HTTPError as e:
        return {
            "success": False,
            "error": f"HTTP Error {e.code}",
            "status_code": e.code,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "url": url,
            "name": url_name
        }
    except urllib.error.URLError as e:
        return {
            "success": False,
            "error": str(e.reason),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "url": url,
            "name": url_name
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "url": url,
            "name": url_name
        }

# ========== TELEGRAM FUNCTIONS ==========
def send_telegram_message(bot_token, chat_id, text, parse_mode='HTML', reply_markup=None):
    """Send message using Telegram Bot API"""
    try:
        import urllib.parse
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        data_dict = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }
        
        if reply_markup:
            data_dict['reply_markup'] = json.dumps(reply_markup)
        
        data = urllib.parse.urlencode(data_dict).encode('utf-8')
        req = urllib.request.Request(url, data=data)
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
            return json.loads(response.read().decode('utf-8'))
            
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {str(e)}")
        return None

def edit_telegram_message(bot_token, chat_id, message_id, text, parse_mode='HTML', reply_markup=None):
    """Edit existing Telegram message"""
    try:
        import urllib.parse
        
        url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
        
        data_dict = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }
        
        if reply_markup:
            data_dict['reply_markup'] = json.dumps(reply_markup)
        
        data = urllib.parse.urlencode(data_dict).encode('utf-8')
        req = urllib.request.Request(url, data=data)
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
            return json.loads(response.read().decode('utf-8'))
            
    except Exception as e:
        logger.error(f"Failed to edit Telegram message: {str(e)}")
        return None

def get_telegram_updates(bot_token, offset=None):
    """Get updates from Telegram"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        if offset:
            url += f"?offset={offset}"
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(url)
        
        with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
            return json.loads(response.read().decode('utf-8'))
            
    except Exception as e:
        logger.error(f"Failed to get Telegram updates: {str(e)}")
        return None

# ========== PERMANENT KEYBOARDS ==========
def get_main_menu_keyboard(user_id):
    """Get main menu permanent keyboard"""
    user_info = get_user_info(user_id)
    is_premium = user_info.get('is_premium', False)
    
    keyboard = [
        ["➕ ADD URL", "🗑️ DELETE URL"],
        ["📋 MY URLs", "🏓 PING NOW"],
        ["⚙️ SETTINGS", "⭐ PREMIUM" if not is_premium else "👑 PREMIUM"],
        ["📊 STATS", "🆘 HELP"]
    ]
    
    if user_id in ADMIN_USER_IDS:
        keyboard.append(["👑 ADMIN PANEL"])
    
    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def get_settings_keyboard(user_id):
    """Get settings keyboard"""
    settings = get_user_settings(user_id)
    notifications = settings.get('notifications', True)
    auto_ping = settings.get('auto_ping', True)
    
    keyboard = [
        [f"🔔 NOTIFICATIONS: {'ON' if notifications else 'OFF'}"],
        [f"🤖 AUTO PING: {'ON' if auto_ping else 'OFF'}"],
        ["🔙 MAIN MENU"]
    ]
    
    if user_id in ADMIN_USER_IDS:
        keyboard.append(["👑 ADMIN"])
    
    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def get_admin_keyboard():
    """Get admin permanent keyboard"""
    keyboard = [
        ["👥 ALL USERS", "⭐ PREMIUM USERS"],
        ["📊 SYSTEM STATS", "🔄 CHECK EXPIRY"],
        ["➕ ADD PREMIUM", "🗑️ REMOVE PREMIUM"],
        ["🔙 MAIN MENU"]
    ]
    
    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def get_add_premium_keyboard():
    """Get add premium keyboard for admin"""
    keyboard = [
        ["7 DAYS", "30 DAYS"],
        ["90 DAYS", "365 DAYS"],
        ["🔙 BACK TO ADMIN"]
    ]
    
    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def get_cancel_keyboard(user_id):
    """Get cancel operation keyboard"""
    keyboard = [
        ["❌ CANCEL"]
    ]
    
    if user_id in ADMIN_USER_IDS:
        keyboard.append(["👑 ADMIN"])
    
    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

# ========== INLINE KEYBOARDS FOR PREMIUM ==========
def get_premium_plans_inline_keyboard(user_id):
    """Get premium plans inline keyboard"""
    uuid_str = str(uuid.uuid4())[:8]
    
    keyboard = [
        [
            {"text": f"7 Days - ${PREMIUM_PLANS['7']['price']}", "callback_data": f"buy_premium:7:{uuid_str}"},
            {"text": f"30 Days - ${PREMIUM_PLANS['30']['price']}", "callback_data": f"buy_premium:30:{uuid_str}"}
        ],
        [
            {"text": f"90 Days - ${PREMIUM_PLANS['90']['price']}", "callback_data": f"buy_premium:90:{uuid_str}"},
            {"text": f"365 Days - ${PREMIUM_PLANS['365']['price']}", "callback_data": f"buy_premium:365:{uuid_str}"}
        ],
        [
            {"text": "🔙 MAIN MENU", "callback_data": f"main_menu:{uuid_str}"}
        ]
    ]
    
    return {"inline_keyboard": keyboard}

def get_admin_premium_inline_keyboard(target_user_id):
    """Get admin premium inline keyboard"""
    uuid_str = str(uuid.uuid4())[:8]
    
    keyboard = [
        [
            {"text": f"7 Days", "callback_data": f"admin_premium:{target_user_id}:7:{uuid_str}"},
            {"text": f"30 Days", "callback_data": f"admin_premium:{target_user_id}:30:{uuid_str}"}
        ],
        [
            {"text": f"90 Days", "callback_data": f"admin_premium:{target_user_id}:90:{uuid_str}"},
            {"text": f"365 Days", "callback_data": f"admin_premium:{target_user_id}:365:{uuid_str}"}
        ],
        [
            {"text": "🔙 BACK", "callback_data": f"admin_user:{target_user_id}:{uuid_str}"}
        ]
    ]
    
    return {"inline_keyboard": keyboard}

def get_admin_user_inline_keyboard(user_id):
    """Get admin user management inline keyboard"""
    uuid_str = str(uuid.uuid4())[:8]
    
    keyboard = [
        [
            {"text": "⭐ ADD PREMIUM", "callback_data": f"admin_add_premium:{user_id}:{uuid_str}"},
            {"text": "🗑️ REMOVE PREMIUM", "callback_data": f"admin_remove_premium:{user_id}:{uuid_str}"}
        ],
        [
            {"text": "👀 VIEW URLs", "callback_data": f"admin_view_urls:{user_id}:{uuid_str}"},
            {"text": "📊 USER INFO", "callback_data": f"admin_user_info:{user_id}:{uuid_str}"}
        ],
        [
            {"text": "🔙 BACK", "callback_data": f"admin_users:{uuid_str}"}
        ]
    ]
    
    return {"inline_keyboard": keyboard}

# ========== BOT CLASS ==========
class PremiumURLPingBot:
    def __init__(self, token, admin_ids):
        self.token = token
        self.admin_ids = admin_ids
        self.running = True
        self.last_update_id = 0
        self.user_states = {}
        self.ping_queue = Queue()
        self.active_pings = {}
        self.ping_results = {}
        
        # Start worker threads
        self.start_workers()
        
    def start_workers(self):
        """Start background worker threads"""
        # Ping worker thread
        self.ping_worker_thread = threading.Thread(target=self.ping_worker)
        self.ping_worker_thread.daemon = True
        self.ping_worker_thread.start()
        
        # Scheduler thread - ONLY 5 MINUTE INTERVAL FOR ALL
        self.scheduler_thread = threading.Thread(target=self.scheduled_ping_scheduler)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        
        # Expiry checker thread
        self.expiry_thread = threading.Thread(target=self.premium_expiry_checker)
        self.expiry_thread.daemon = True
        self.expiry_thread.start()
        
        logger.info("✅ All worker threads started")
    
    def start(self):
        """Start the bot"""
        logger.info("🤖 Starting Premium URL Ping Bot...")
        
        # Check premium expiry on startup
        expired = check_premium_expiry()
        if expired:
            logger.info(f"✅ Checked premium expiry: {len(expired)} users expired")
        
        all_urls = load_urls()
        user_data = load_user_data()
        
        total_users = len(all_urls)
        total_urls = sum(len(urls) for urls in all_urls.values())
        premium_users = sum(1 for user in user_data.values() if user.get('is_premium', False))
        
        logger.info(f"📊 System Stats: {total_users} users, {total_urls} URLs, {premium_users} premium")
        
        # Start bot message handler
        bot_thread = threading.Thread(target=self.bot_loop)
        bot_thread.daemon = True
        bot_thread.start()
        
        logger.info("✅ Bot started successfully!")
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("🛑 Bot stopped by user")
            self.running = False
            self.send_shutdown_message()
    
    def scheduled_ping_scheduler(self):
        """Schedule pings for all users - ONLY 5 MINUTE INTERVAL"""
        logger.info("⏰ Starting scheduled ping scheduler (5-minute interval for ALL)...")
        
        last_ping_minute = -1
        
        while self.running:
            try:
                current_time = datetime.now()
                current_minute = current_time.minute
                
                # Only run once per 5 minutes (minute divisible by 5)
                if current_minute % 5 == 0 and current_minute != last_ping_minute:
                    last_ping_minute = current_minute
                    
                    all_urls = load_urls()
                    
                    for user_id, urls in all_urls.items():
                        if not urls:
                            continue
                        
                        # Check user settings for auto ping
                        settings = get_user_settings(user_id)
                        if not settings.get('auto_ping', True):
                            continue  # Skip if auto ping is OFF
                        
                        # EVERYONE gets 5-minute interval - NO 1-minute for premium
                        should_ping = True  # Always ping at 5-minute intervals
                        
                        if should_ping:
                            # Add to ping queue
                            for name, url in urls.items():
                                self.ping_queue.put({
                                    'user_id': user_id,
                                    'name': name,
                                    'url': url,
                                    'priority': 1,
                                    'scheduled': True,
                                    'ping_time': current_time.strftime("%H:%M:%S")
                                })
                    
                    # Send queued pings
                    self.process_ping_queue()
                
                # Sleep for 1 minute
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"❌ Error in scheduler: {str(e)}")
                time.sleep(30)
    
    def process_ping_queue(self):
        """Process ping queue immediately"""
        try:
            temp_results = {}
            
            while not self.ping_queue.empty():
                task = self.ping_queue.get()
                user_id = task['user_id']
                name = task['name']
                url = task['url']
                
                # Check user settings for notifications
                settings = get_user_settings(user_id)
                if not settings.get('notifications', True):
                    continue  # Skip if notifications are OFF
                
                # Perform ping
                result = ping_url_advanced(url, name, user_id)
                
                # Store results by user
                if user_id not in temp_results:
                    temp_results[user_id] = []
                temp_results[user_id].append(result)
            
            # Send notifications with INDIAN TIME
            for user_id, results in temp_results.items():
                if results:
                    self.send_ping_notification(user_id, results)
                    
        except Exception as e:
            logger.error(f"❌ Error processing ping queue: {str(e)}")
    
    def ping_worker(self):
        """Worker thread for manual pings"""
        while self.running:
            try:
                # This worker handles manual pings triggered by users
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"❌ Error in ping worker: {str(e)}")
                time.sleep(1)
    
    def premium_expiry_checker(self):
        """Check premium expiry periodically"""
        logger.info("⏳ Starting premium expiry checker...")
        
        while self.running:
            try:
                # Check every hour
                expired = check_premium_expiry()
                if expired:
                    for user_id in expired:
                        try:
                            send_telegram_message(
                                self.token,
                                user_id,
                                f"⚠️ <b>PREMIUM EXPIRED</b>\n\n"
                                f"Your premium subscription has expired.\n"
                                f"Please renew to continue enjoying premium features.\n\n"
                                f"Use PREMIUM button to upgrade again!",
                                reply_markup=get_main_menu_keyboard(user_id)
                            )
                        except:
                            pass
                
                # Sleep for 1 hour
                time.sleep(3600)
                
            except Exception as e:
                logger.error(f"❌ Error in expiry checker: {str(e)}")
                time.sleep(60)
    
    def send_ping_notification(self, user_id, results):
        """Send ping notification to user with INDIAN TIME"""
        try:
            # Check if notifications are enabled
            settings = get_user_settings(user_id)
            if not settings.get('notifications', True):
                return
            
            successful = [r for r in results if r["success"]]
            failed = [r for r in results if not r["success"]]
            
            # Get current Indian time (IST = UTC+5:30)
            utc_now = datetime.utcnow()
            ist_now = utc_now + timedelta(hours=5, minutes=30)
            indian_time = ist_now.strftime("%H:%M:%S")
            indian_date = ist_now.strftime("%d-%m-%Y")
            
            notification_text = f"<b>🔔 URL MONITORING UPDATE</b>\n\n"
            notification_text += f"👤 User ID: <code>{user_id}</code>\n"
            notification_text += f"🕐 Indian Time: {indian_time}\n"
            notification_text += f"📅 Date: {indian_date}\n"
            notification_text += "─" * 35 + "\n"
            
            for result in results:
                status = "✅" if result["success"] else "❌"
                if result["success"]:
                    notification_text += f"{status} {result['name']} - {result['status_code']} ({result['response_time_str']})\n"
                else:
                    notification_text += f"{status} {result['name']} - {result['error']}\n"
            
            notification_text += "─" * 35 + "\n"
            notification_text += f"📊 Results: {len(successful)}✅ {len(failed)}❌\n"
            
            # Add premium reminder if free user
            user_info = get_user_info(user_id)
            if not user_info.get('is_premium', False):
                notification_text += f"\n⭐ <b>Upgrade to Premium for 100 URLs limit!</b>"
            
            send_telegram_message(self.token, user_id, notification_text)
            
        except Exception as e:
            logger.error(f"Failed to send notification to user {user_id}: {str(e)}")
    
    def bot_loop(self):
        """Handle bot messages and callbacks"""
        logger.info("📱 Starting bot message handler...")
        
        while self.running:
            try:
                updates = get_telegram_updates(self.token, self.last_update_id + 1)
                
                if updates and updates.get('ok'):
                    for update in updates.get('result', []):
                        self.last_update_id = update['update_id']
                        
                        if 'message' in update:
                            message = update['message']
                            chat_id = message['chat']['id']
                            text = message.get('text', '').strip()
                            
                            update_user_active(chat_id)
                            self.handle_message(chat_id, text)
                        
                        elif 'callback_query' in update:
                            callback = update['callback_query']
                            chat_id = callback['message']['chat']['id']
                            message_id = callback['message']['message_id']
                            data = callback['data']
                            
                            update_user_active(chat_id)
                            self.handle_callback(chat_id, message_id, data)
                
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in bot loop: {str(e)}")
                time.sleep(1)
    
    def handle_message(self, chat_id, text):
        """Handle incoming text messages"""
        try:
            if not text:
                return
            
            # Handle button clicks
            if text == "➕ ADD URL":
                self.start_add_url(chat_id)
            elif text == "🗑️ DELETE URL":
                self.start_delete_url(chat_id)
            elif text == "📋 MY URLs":
                self.list_urls(chat_id)
            elif text == "🏓 PING NOW":
                self.manual_ping(chat_id)
            elif text == "⭐ PREMIUM" or text == "👑 PREMIUM":
                self.show_premium_plans(chat_id)
            elif text == "⚙️ SETTINGS":
                self.show_settings(chat_id)
            elif text == "📊 STATS":
                self.show_stats(chat_id)
            elif text == "🆘 HELP":
                self.send_help(chat_id)
            elif text == "👑 ADMIN PANEL" and chat_id in self.admin_ids:
                self.admin_panel(chat_id)
            elif text == "🔙 MAIN MENU":
                self.send_welcome(chat_id)
            elif text == "❌ CANCEL":
                self.cancel_operation(chat_id)
            
            # Settings buttons
            elif text.startswith("🔔 NOTIFICATIONS:"):
                self.toggle_notifications(chat_id)
            elif text.startswith("🤖 AUTO PING:"):
                self.toggle_auto_ping(chat_id)
            
            # Admin buttons
            elif text == "👥 ALL USERS" and chat_id in self.admin_ids:
                self.admin_users_list(chat_id)
            elif text == "⭐ PREMIUM USERS" and chat_id in self.admin_ids:
                self.admin_premium_users(chat_id)
            elif text == "📊 SYSTEM STATS" and chat_id in self.admin_ids:
                self.admin_stats(chat_id)
            elif text == "🔄 CHECK EXPIRY" and chat_id in self.admin_ids:
                self.admin_check_expiry(chat_id)
            elif text == "➕ ADD PREMIUM" and chat_id in self.admin_ids:
                self.start_admin_add_premium(chat_id)
            elif text == "🗑️ REMOVE PREMIUM" and chat_id in self.admin_ids:
                self.start_admin_remove_premium(chat_id)
            
            # Add premium duration buttons
            elif text == "7 DAYS" and chat_id in self.admin_ids:
                self.handle_admin_add_premium_duration(chat_id, 7)
            elif text == "30 DAYS" and chat_id in self.admin_ids:
                self.handle_admin_add_premium_duration(chat_id, 30)
            elif text == "90 DAYS" and chat_id in self.admin_ids:
                self.handle_admin_add_premium_duration(chat_id, 90)
            elif text == "365 DAYS" and chat_id in self.admin_ids:
                self.handle_admin_add_premium_duration(chat_id, 365)
            elif text == "🔙 BACK TO ADMIN" and chat_id in self.admin_ids:
                self.admin_panel(chat_id)
            
            elif text.startswith('/'):
                parts = text.split()
                command = parts[0].lower()
                
                if command == '/start':
                    self.send_welcome(chat_id)
                elif command == '/add':
                    self.start_add_url(chat_id)
                elif command == '/delete':
                    self.start_delete_url(chat_id)
                elif command == '/list':
                    self.list_urls(chat_id)
                elif command == '/ping':
                    self.manual_ping(chat_id)
                elif command == '/premium':
                    self.show_premium_plans(chat_id)
                elif command == '/settings':
                    self.show_settings(chat_id)
                elif command == '/stats':
                    self.show_stats(chat_id)
                elif command == '/help':
                    self.send_help(chat_id)
                elif command == '/admin' and chat_id in self.admin_ids:
                    self.admin_panel(chat_id)
                elif command == '/addpremium' and chat_id in self.admin_ids:
                    self.start_admin_add_premium(chat_id)
                elif command == '/removepremium' and chat_id in self.admin_ids:
                    self.start_admin_remove_premium(chat_id)
                elif command == '/cancel':
                    self.cancel_operation(chat_id)
                else:
                    self.send_unknown(chat_id)
            
            elif chat_id in self.user_states:
                state = self.user_states[chat_id]
                
                if state['action'] == 'add_name':
                    self.handle_add_name(chat_id, text)
                elif state['action'] == 'add_url':
                    self.handle_add_url(chat_id, text)
                elif state['action'] == 'delete':
                    self.handle_delete_url(chat_id, text)
                elif state['action'] == 'admin_add_premium':
                    self.handle_admin_add_premium(chat_id, text)
                elif state['action'] == 'admin_remove_premium':
                    self.handle_admin_remove_premium(chat_id, text)
                    
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
    
    def handle_callback(self, chat_id, message_id, data):
        """Handle inline keyboard callbacks"""
        try:
            # Extract callback data parts
            parts = data.split(':')
            action = parts[0]
            
            if action == 'main_menu':
                self.send_welcome(chat_id)
            elif action == 'buy_premium':
                if len(parts) >= 2:
                    days = parts[1]
                    self.buy_premium(chat_id, message_id, days)
            
            # Admin actions
            elif chat_id in self.admin_ids:
                if action == 'admin_users':
                    self.admin_users_list(chat_id, True, message_id)
                elif action == 'admin_premium_users':
                    self.admin_premium_users(chat_id, True, message_id)
                elif action == 'admin_stats':
                    self.admin_stats(chat_id, True, message_id)
                elif action == 'admin_check_expiry':
                    self.admin_check_expiry(chat_id, True, message_id)
                elif action == 'admin_user':
                    if len(parts) >= 2:
                        target_user_id = int(parts[1])
                        self.admin_user_details(chat_id, message_id, target_user_id)
                elif action == 'admin_add_premium':
                    if len(parts) >= 2:
                        target_user_id = int(parts[1])
                        self.start_admin_add_premium_user(chat_id, message_id, target_user_id)
                elif action == 'admin_premium':
                    if len(parts) >= 3:
                        target_user_id = int(parts[1])
                        days = parts[2]
                        self.admin_activate_premium(chat_id, message_id, target_user_id, days)
                elif action == 'admin_remove_premium':
                    if len(parts) >= 2:
                        target_user_id = int(parts[1])
                        self.admin_remove_premium(chat_id, message_id, target_user_id)
                elif action == 'admin_view_urls':
                    if len(parts) >= 2:
                        target_user_id = int(parts[1])
                        self.admin_view_urls(chat_id, message_id, target_user_id)
                elif action == 'admin_user_info':
                    if len(parts) >= 2:
                        target_user_id = int(parts[1])
                        self.admin_user_info(chat_id, message_id, target_user_id)
                
        except Exception as e:
            logger.error(f"Error handling callback {data}: {str(e)}")
            send_telegram_message(self.token, chat_id, f"❌ Error: {str(e)[:100]}")
    
    def send_welcome(self, chat_id):
        """Send welcome message with Indian Time"""
        user_urls = get_user_urls(chat_id)
        user_info = get_user_info(chat_id)
        is_premium = user_info.get('is_premium', False)
        premium_until = user_info.get('premium_until', 'Not premium')
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        indian_date = ist_now.strftime("%d-%m-%Y")
        
        welcome_text = f"""
<b>🤖 PREMIUM URL PING BOT</b>

<b>👤 YOUR ACCOUNT:</b>
• User ID: <code>{chat_id}</code>
• Status: {"⭐ PREMIUM USER" if is_premium else "🆓 FREE USER"}
• Your URLs: {len(user_urls)}/{"100" if is_premium else "1"}
• {"Premium until: " + premium_until if is_premium else "Upgrade for 100 URLs!"}

<b>⚡ FEATURES:</b>
• Automatic URL monitoring
• Real-time notifications
• Ping Interval: 5 minutes (for ALL users)
• 24/7 service

<b>📊 SYSTEM:</b>
• Service: ✅ ACTIVE
• Indian Time: {indian_time}
• Date: {indian_date}
        """
        
        keyboard = get_main_menu_keyboard(chat_id)
        send_telegram_message(self.token, chat_id, welcome_text, reply_markup=keyboard)
    
    def show_settings(self, chat_id):
        """Show user settings with Indian Time"""
        settings = get_user_settings(chat_id)
        notifications = settings.get('notifications', True)
        auto_ping = settings.get('auto_ping', True)
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        settings_text = f"""
<b>⚙️ SETTINGS</b>

<b>Current Settings:</b>
• 🔔 Notifications: {'✅ ON' if notifications else '❌ OFF'}
• 🤖 Auto Ping: {'✅ ON' if auto_ping else '❌ OFF'}

<b>Notifications:</b>
Turn ON/OFF ping notifications

<b>Auto Ping:</b>
Enable/disable automatic pinging

<b>Indian Time: {indian_time}</b>
        """
        
        keyboard = get_settings_keyboard(chat_id)
        send_telegram_message(self.token, chat_id, settings_text, reply_markup=keyboard)
    
    def toggle_notifications(self, chat_id):
        """Toggle notifications setting with Indian Time"""
        settings = get_user_settings(chat_id)
        current = settings.get('notifications', True)
        new_value = not current
        
        update_user_settings(chat_id, 'notifications', new_value)
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        response = f"""
<b>🔔 NOTIFICATIONS</b>

Notifications are now {'✅ ON' if new_value else '❌ OFF'}

You will {'receive' if new_value else 'NOT receive'} ping notifications.

<b>Indian Time: {indian_time}</b>
        """
        
        keyboard = get_settings_keyboard(chat_id)
        send_telegram_message(self.token, chat_id, response, reply_markup=keyboard)
    
    def toggle_auto_ping(self, chat_id):
        """Toggle auto ping setting with Indian Time"""
        settings = get_user_settings(chat_id)
        current = settings.get('auto_ping', True)
        new_value = not current
        
        update_user_settings(chat_id, 'auto_ping', new_value)
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        response = f"""
<b>🤖 AUTO PING</b>

Auto ping is now {'✅ ON' if new_value else '❌ OFF'}

Your URLs will {'be automatically pinged every 5 minutes' if new_value else 'NOT be automatically pinged'}.

<b>Indian Time: {indian_time}</b>
        """
        
        keyboard = get_settings_keyboard(chat_id)
        send_telegram_message(self.token, chat_id, response, reply_markup=keyboard)
    
    def start_add_url(self, chat_id):
        """Start add URL process - FREE: 1 URL ONLY"""
        user_urls = get_user_urls(chat_id)
        user_info = get_user_info(chat_id)
        is_premium = user_info.get('is_premium', False)
        max_urls = PREMIUM_FEATURES['max_urls']['premium' if is_premium else 'free']
        
        if len(user_urls) >= max_urls:
            limit_text = f"""
<b>❌ URL LIMIT REACHED</b>

You have {len(user_urls)}/{max_urls} URLs.

{"⭐ Upgrade to Premium for 100 URLs!" if not is_premium else "You have reached the maximum limit of 100 URLs"}
            """
            
            send_telegram_message(self.token, chat_id, limit_text, reply_markup=get_main_menu_keyboard(chat_id))
            return
        
        self.user_states[chat_id] = {
            'action': 'add_name',
            'data': {}
        }
        
        add_text = f"""
<b>➕ ADD NEW URL</b>

Enter a name for your URL:
Example: MyWebsite, API, Blog

<b>Your URLs: {len(user_urls)}/{max_urls}</b>
{"⚠️ Free users can add only 1 URL!" if not is_premium else "⭐ Premium users can add up to 100 URLs!"}
        """
        
        keyboard = get_cancel_keyboard(chat_id)
        send_telegram_message(self.token, chat_id, add_text, reply_markup=keyboard)
    
    def handle_add_name(self, chat_id, name):
        """Handle URL name input"""
        name = name.strip()
        
        if not name:
            send_telegram_message(self.token, chat_id, "❌ Name cannot be empty.", reply_markup=get_cancel_keyboard(chat_id))
            return
        
        user_urls = get_user_urls(chat_id)
        if name in user_urls:
            send_telegram_message(self.token, chat_id, f"❌ Name '{name}' already exists.", reply_markup=get_cancel_keyboard(chat_id))
            return
        
        self.user_states[chat_id]['data']['name'] = name
        self.user_states[chat_id]['action'] = 'add_url'
        
        add_url_text = f"""
✅ Name saved: <b>{name}</b>

Enter the full URL:
Must start with http:// or https://

Example:
https://example.com
http://192.168.1.1
        """
        
        send_telegram_message(self.token, chat_id, add_url_text, reply_markup=get_cancel_keyboard(chat_id))
    
    def handle_add_url(self, chat_id, url):
        """Handle URL input and save"""
        url = url.strip()
        
        if not url.startswith(('http://', 'https://')):
            send_telegram_message(
                self.token,
                chat_id,
                "❌ URL must start with http:// or https://",
                reply_markup=get_cancel_keyboard(chat_id)
            )
            return
        
        state_data = self.user_states[chat_id]['data']
        name = state_data['name']
        
        # Save URL
        user_urls = get_user_urls(chat_id)
        user_urls[name] = url
        save_user_urls(chat_id, user_urls)
        
        # Clear user state
        if chat_id in self.user_states:
            del self.user_states[chat_id]
        
        # Test ping
        result = ping_url_advanced(url, name, chat_id)
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        # Send success message
        if result["success"]:
            status_msg = f"✅ Test successful! Status: {result['status_code']}, Time: {result['response_time_str']}"
        else:
            status_msg = f"⚠️ Test failed: {result['error']}"
        
        user_info = get_user_info(chat_id)
        is_premium = user_info.get('is_premium', False)
        max_urls = PREMIUM_FEATURES['max_urls']['premium' if is_premium else 'free']
        
        success_text = f"""
🎉 <b>URL ADDED SUCCESSFULLY!</b>

<b>📝 Details:</b>
Name: <code>{name}</code>
URL: <code>{url}</code>
Test: {status_msg}

<b>✅ Service Activated:</b>
• Added to monitoring queue
• Will be pinged every 5 minutes
• Real-time notifications

<b>📊 Your URLs: {len(user_urls)}/{max_urls}</b>
<b>🕐 Indian Time: {indian_time}</b>
        """
        
        send_telegram_message(self.token, chat_id, success_text, reply_markup=get_main_menu_keyboard(chat_id))
    
    def start_delete_url(self, chat_id):
        """Start delete URL process"""
        user_urls = get_user_urls(chat_id)
        
        if not user_urls:
            no_urls_text = """
<b>📭 NO URLs FOUND</b>

You haven't added any URLs yet.
            """
            
            send_telegram_message(self.token, chat_id, no_urls_text, reply_markup=get_main_menu_keyboard(chat_id))
            return
        
        url_list = "\n".join([f"• <code>{name}</code>" for name in user_urls.keys()])
        
        self.user_states[chat_id] = {
            'action': 'delete',
            'data': {}
        }
        
        delete_text = f"""
<b>🗑️ DELETE URL</b>

Your URLs:
{url_list}

Enter the name of URL to delete:
        """
        
        keyboard = get_cancel_keyboard(chat_id)
        send_telegram_message(self.token, chat_id, delete_text, reply_markup=keyboard)
    
    def handle_delete_url(self, chat_id, name):
        """Handle URL deletion"""
        name = name.strip()
        user_urls = get_user_urls(chat_id)
        
        if name not in user_urls:
            send_telegram_message(
                self.token,
                chat_id,
                f"❌ URL '{name}' not found.",
                reply_markup=get_cancel_keyboard(chat_id)
            )
            return
        
        url = user_urls[name]
        del user_urls[name]
        save_user_urls(chat_id, user_urls)
        
        if chat_id in self.user_states:
            del self.user_states[chat_id]
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        success_text = f"""
✅ <b>URL DELETED</b>

Name: <code>{name}</code>
URL: <code>{url}</code>

Remaining URLs: {len(user_urls)}
<b>🕐 Indian Time: {indian_time}</b>
        """
        
        send_telegram_message(self.token, chat_id, success_text, reply_markup=get_main_menu_keyboard(chat_id))
    
    def list_urls(self, chat_id):
        """List user's URLs"""
        user_urls = get_user_urls(chat_id)
        
        if not user_urls:
            no_urls_text = """
<b>📭 NO URLs FOUND</b>

Add URLs to start monitoring.
            """
            
            send_telegram_message(self.token, chat_id, no_urls_text, reply_markup=get_main_menu_keyboard(chat_id))
            return
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        list_text = f"<b>📋 YOUR URLs ({len(user_urls)})</b>\n"
        list_text += f"<b>🕐 Indian Time: {indian_time}</b>\n"
        list_text += "─" * 35 + "\n\n"
        
        for i, (name, url) in enumerate(user_urls.items(), 1):
            display_url = url[:40] + "..." if len(url) > 40 else url
            list_text += f"<b>{i}. {name}</b>\n"
            list_text += f"🔗 <code>{display_url}</code>\n"
            list_text += "─" * 25 + "\n"
        
        user_info = get_user_info(chat_id)
        is_premium = user_info.get('is_premium', False)
        max_urls = PREMIUM_FEATURES['max_urls']['premium' if is_premium else 'free']
        
        list_text += f"\n<b>📊 Total: {len(user_urls)}/{max_urls} URLs</b>"
        
        send_telegram_message(self.token, chat_id, list_text, reply_markup=get_main_menu_keyboard(chat_id))
    
    def manual_ping(self, chat_id):
        """Manual ping all URLs with Indian Time"""
        user_urls = get_user_urls(chat_id)
        
        if not user_urls:
            no_urls_text = "📭 You have no URLs to ping."
            send_telegram_message(self.token, chat_id, no_urls_text, reply_markup=get_main_menu_keyboard(chat_id))
            return
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        # Send initial message
        ping_text = f"""
<b>🏓 PINGING {len(user_urls)} URLs...</b>

<b>Indian Time: {indian_time}</b>
Please wait...
        """
        
        message = send_telegram_message(self.token, chat_id, ping_text)
        
        # Ping all URLs
        results = []
        for name, url in user_urls.items():
            result = ping_url_advanced(url, name, chat_id)
            results.append(result)
        
        # Prepare results with Indian Time
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]
        
        result_text = f"<b>🏓 PING COMPLETE</b>\n\n"
        result_text += f"<b>Indian Time: {indian_time}</b>\n"
        result_text += "─" * 35 + "\n"
        
        for result in results:
            status = "✅" if result["success"] else "❌"
            if result["success"]:
                result_text += f"{status} {result['name']} - {result['status_code']} ({result['response_time_str']})\n"
            else:
                result_text += f"{status} {result['name']} - {result['error']}\n"
        
        result_text += "─" * 35 + "\n"
        result_text += f"📊 Results: {len(successful)}✅ {len(failed)}❌\n"
        
        send_telegram_message(self.token, chat_id, result_text, reply_markup=get_main_menu_keyboard(chat_id))
    
    def show_premium_plans(self, chat_id):
        """Show premium plans with Indian Time"""
        user_info = get_user_info(chat_id)
        is_premium = user_info.get('is_premium', False)
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        if is_premium:
            premium_until = user_info.get('premium_until', 'Not set')
            premium_text = f"""
<b>👑 PREMIUM USER</b>

<b>🎉 CONGRATULATIONS!</b>
You are already a Premium user.

<b>📅 SUBSCRIPTION:</b>
• Active: ✅ YES
• Until: {premium_until}
• Features: FULL ACCESS

<b>⚡ YOUR BENEFITS:</b>
• 100 URLs maximum (Free: Only 1 URL)
• 5-minute monitoring interval
• Priority queue
• Real-time alerts
• Advanced analytics
• Priority support

<b>Indian Time: {indian_time}</b>
            """
            
            send_telegram_message(self.token, chat_id, premium_text, reply_markup=get_main_menu_keyboard(chat_id))
        else:
            premium_text = f"""
<b>⭐ PREMIUM PLANS ⭐</b>

<b>🆓 FREE PLAN:</b>
• {PREMIUM_FEATURES['max_urls']['free']} URL max (Only 1!)
• {PREMIUM_FEATURES['ping_interval']['free']//60} minute intervals
• Basic features

<b>⭐ PREMIUM BENEFITS:</b>
• {PREMIUM_FEATURES['max_urls']['premium']} URLs max (100 URLs!)
• 5-minute monitoring intervals (Same as Free)
• Priority processing
• Advanced analytics
• 24/7 priority support

<b>💎 CHOOSE YOUR PLAN:</b>
<b>Indian Time: {indian_time}</b>
            """
            
            keyboard = get_premium_plans_inline_keyboard(chat_id)
            send_telegram_message(self.token, chat_id, premium_text, reply_markup=keyboard)
    
    def buy_premium(self, chat_id, message_id, days):
        """Handle premium purchase with Indian Time"""
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        if chat_id in self.admin_ids:
            # Admin can activate directly
            expiry = set_user_premium(chat_id, int(days), chat_id)
            
            success_text = f"""
✅ <b>PREMIUM ACTIVATED</b>

Days: {days}
Expires: {expiry.strftime('%Y-%m-%d %H:%M:%S')}
Status: ✅ ACTIVE

<b>Now you can add up to 100 URLs!</b>

<b>Indian Time: {indian_time}</b>
Enjoy premium features!
            """
            
            send_telegram_message(self.token, chat_id, success_text, reply_markup=get_main_menu_keyboard(chat_id))
        else:
            # For regular users, show payment info
            plan = PREMIUM_PLANS.get(days, PREMIUM_PLANS['30'])
            
            payment_text = f"""
<b>💰 PAYMENT FOR {days} DAYS</b>

<b>Plan Details:</b>
• Duration: {plan['days']} days
• Price: ${plan['price']}
• URLs Limit: 100 URLs
• Ping Interval: 5 minutes

<b>Payment Methods:</b>
1. Contact Admin: @YourAdmin
2. Send your User ID: <code>{chat_id}</code>
3. Choose payment method
4. Get instant activation

<b>After payment:</b>
• Instant activation
• 100 URLs limit unlocked

<b>Indian Time: {indian_time}</b>
            """
            
            send_telegram_message(self.token, chat_id, payment_text, reply_markup=get_main_menu_keyboard(chat_id))
    
    def show_stats(self, chat_id):
        """Show user statistics with Indian Time"""
        user_urls = get_user_urls(chat_id)
        user_info = get_user_info(chat_id)
        settings = get_user_settings(chat_id)
        
        is_premium = user_info.get('is_premium', False)
        premium_until = user_info.get('premium_until', 'Not premium')
        join_date = user_info.get('join_date', 'Recently')
        notifications = settings.get('notifications', True)
        auto_ping = settings.get('auto_ping', True)
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        indian_date = ist_now.strftime("%d-%m-%Y")
        
        stats_text = f"""
<b>📊 YOUR STATISTICS</b>

<b>👤 ACCOUNT:</b>
• User ID: <code>{chat_id}</code>
• Status: {"⭐ PREMIUM" if is_premium else "🆓 FREE"}
• Joined: {join_date}
• {"Premium until: " + premium_until if is_premium else ""}

<b>📈 URL STATS:</b>
• Your URLs: {len(user_urls)}
• Max Allowed: {PREMIUM_FEATURES['max_urls']['premium' if is_premium else 'free']}
• Ping Interval: {PREMIUM_FEATURES['ping_interval']['premium' if is_premium else 'free']//60} minutes (for ALL users)

<b>⚙️ SETTINGS:</b>
• Notifications: {'✅ ON' if notifications else '❌ OFF'}
• Auto Ping: {'✅ ON' if auto_ping else '❌ OFF'}

<b>🕐 Indian Time: {indian_time}</b>
<b>📅 Date: {indian_date}</b>
        """
        
        send_telegram_message(self.token, chat_id, stats_text, reply_markup=get_main_menu_keyboard(chat_id))
    
    def send_help(self, chat_id):
        """Send help message with Indian Time"""
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        help_text = f"""
<b>🆘 HELP & SUPPORT</b>

<b>📖 QUICK START:</b>
1. Add URLs using ADD URL button
2. URLs are automatically monitored every 5 minutes
3. Get real-time notifications
4. Check stats anytime

<b>⚙️ SETTINGS:</b>
• Turn notifications ON/OFF
• Enable/disable auto ping

<b>🔧 FEATURES:</b>
• Automatic URL monitoring
• Real-time ping notifications
• Ping Interval: 5 minutes for ALL users
• Free: 1 URL maximum
• Premium: 100 URLs maximum

<b>📞 SUPPORT:</b>
• Admin: @YourAdmin
• Issues: Contact immediately
• 24/7 assistance available

<b>⭐ TIP:</b>
Upgrade to Premium for 100 URLs limit!

<b>Indian Time: {indian_time}</b>
        """
        
        send_telegram_message(self.token, chat_id, help_text, reply_markup=get_main_menu_keyboard(chat_id))
    
    def admin_panel(self, chat_id):
        """Admin panel with Indian Time"""
        if chat_id not in self.admin_ids:
            return
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        indian_date = ist_now.strftime("%d-%m-%Y")
        
        admin_text = f"""
<b>👑 ADMIN PANEL</b>

<b>Welcome Admin!</b>
Use the buttons below to manage the system.

<b>Admin ID:</b> <code>{chat_id}</code>
<b>Indian Time:</b> {indian_time}
<b>Date:</b> {indian_date}
        """
        
        keyboard = get_admin_keyboard()
        send_telegram_message(self.token, chat_id, admin_text, reply_markup=keyboard)
    
    def start_admin_add_premium(self, chat_id):
        """Start admin add premium process with Indian Time"""
        if chat_id not in self.admin_ids:
            return
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        add_text = f"""
<b>➕ ADD PREMIUM</b>

Enter the User ID to give premium:

Example: 123456789

<b>Indian Time: {indian_time}</b>
        """
        
        self.user_states[chat_id] = {
            'action': 'admin_add_premium',
            'data': {}
        }
        
        keyboard = get_cancel_keyboard(chat_id)
        send_telegram_message(self.token, chat_id, add_text, reply_markup=keyboard)
    
    def handle_admin_add_premium(self, chat_id, user_id_text):
        """Handle admin adding premium with Indian Time"""
        try:
            target_user_id = int(user_id_text.strip())
        except:
            send_telegram_message(
                self.token,
                chat_id,
                "❌ Invalid User ID. Please enter a valid numeric User ID.",
                reply_markup=get_cancel_keyboard(chat_id)
            )
            return
        
        # Store target user ID
        self.user_states[chat_id]['data']['target_user_id'] = target_user_id
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        # Ask for duration
        duration_text = f"""
<b>⭐ ADD PREMIUM FOR USER</b>

User ID: <code>{target_user_id}</code>

Select premium duration:

<b>Indian Time: {indian_time}</b>
        """
        
        keyboard = get_add_premium_keyboard()
        send_telegram_message(self.token, chat_id, duration_text, reply_markup=keyboard)
    
    def handle_admin_add_premium_duration(self, chat_id, days):
        """Handle admin adding premium with duration"""
        if chat_id not in self.user_states or 'target_user_id' not in self.user_states[chat_id]['data']:
            send_telegram_message(self.token, chat_id, "❌ Please start the add premium process again.", reply_markup=get_admin_keyboard())
            return
        
        target_user_id = self.user_states[chat_id]['data']['target_user_id']
        
        # Activate premium
        expiry = set_user_premium(target_user_id, days, chat_id)
        
        # Clear state
        del self.user_states[chat_id]
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        # Notify admin
        admin_text = f"""
✅ <b>PREMIUM ACTIVATED</b>

<b>For User:</b> <code>{target_user_id}</code>
<b>Days:</b> {days}
<b>Expires:</b> {expiry.strftime('%Y-%m-%d %H:%M:%S')}
<b>Activated by:</b> Admin {chat_id}

<b>Now user can add up to 100 URLs!</b>

<b>Indian Time: {indian_time}</b>
Premium features are now active!
        """
        
        # Notify user
        try:
            user_text = f"""
🎉 <b>PREMIUM ACTIVATED!</b>

Your account has been upgraded to Premium!

<b>Duration:</b> {days} days
<b>Expires:</b> {expiry.strftime('%Y-%m-%d %H:%M:%S')}
<b>Activated by:</b> Admin

<b>⭐ NEW FEATURES:</b>
• 100 URLs maximum (was only 1)
• 5-minute monitoring interval
• Priority processing
• Advanced analytics

Enjoy premium features!
            """
            send_telegram_message(self.token, target_user_id, user_text, reply_markup=get_main_menu_keyboard(target_user_id))
        except Exception as e:
            logger.error(f"Failed to notify user {target_user_id}: {str(e)}")
        
        send_telegram_message(self.token, chat_id, admin_text, reply_markup=get_admin_keyboard())
    
    def start_admin_remove_premium(self, chat_id):
        """Start admin remove premium process with Indian Time"""
        if chat_id not in self.admin_ids:
            return
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        remove_text = f"""
<b>🗑️ REMOVE PREMIUM</b>

Enter the User ID to remove premium from:

Example: 123456789

<b>Indian Time: {indian_time}</b>
        """
        
        self.user_states[chat_id] = {
            'action': 'admin_remove_premium',
            'data': {}
        }
        
        keyboard = get_cancel_keyboard(chat_id)
        send_telegram_message(self.token, chat_id, remove_text, reply_markup=keyboard)
    
    def handle_admin_remove_premium(self, chat_id, user_id_text):
        """Handle admin removing premium with Indian Time"""
        try:
            target_user_id = int(user_id_text.strip())
        except:
            send_telegram_message(
                self.token,
                chat_id,
                "❌ Invalid User ID. Please enter a valid numeric User ID.",
                reply_markup=get_cancel_keyboard(chat_id)
            )
            return
        
        # Remove premium
        remove_user_premium(target_user_id)
        
        # Clear state
        if chat_id in self.user_states:
            del self.user_states[chat_id]
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        # Notify admin
        admin_text = f"""
🗑️ <b>PREMIUM REMOVED</b>

Premium has been removed from user:
<code>{target_user_id}</code>

User is now on free plan (1 URL limit).

<b>Indian Time: {indian_time}</b>
        """
        
        # Notify user
        try:
            user_text = f"""
ℹ️ <b>PREMIUM ENDED</b>

Your premium subscription has been removed.
You are now on the free plan.

<b>Free Plan:</b>
• 1 URL maximum (was 100)
• 5-minute intervals
• Basic features

Contact admin if this was a mistake.
            """
            send_telegram_message(self.token, target_user_id, user_text, reply_markup=get_main_menu_keyboard(target_user_id))
        except Exception as e:
            logger.error(f"Failed to notify user {target_user_id}: {str(e)}")
        
        send_telegram_message(self.token, chat_id, admin_text, reply_markup=get_admin_keyboard())
    
    def start_admin_add_premium_user(self, chat_id, message_id, target_user_id):
        """Start process to add premium for user (from inline)"""
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        add_text = f"""
<b>⭐ ADD PREMIUM FOR USER</b>

User ID: <code>{target_user_id}</code>

Select premium duration:

<b>Indian Time: {indian_time}</b>
        """
        
        keyboard = get_add_premium_keyboard()
        send_telegram_message(self.token, chat_id, add_text, reply_markup=keyboard)
    
    def admin_users_list(self, chat_id, inline=False, message_id=None):
        """List all users for admin with Indian Time"""
        all_urls = load_urls()
        user_data = load_user_data()
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        users_text = f"""
<b>👥 ALL USERS ({len(all_urls)})</b>

<b>User List:</b>
<b>Indian Time: {indian_time}</b>
        """
        
        for i, (user_id, urls) in enumerate(list(all_urls.items())[:20], 1):
            user_info = user_data.get(user_id, {})
            is_premium = user_info.get('is_premium', False)
            users_text += f"\n{i}. User <code>{user_id}</code> - {len(urls)} URLs {'⭐' if is_premium else ''}"
        
        if len(all_urls) > 20:
            users_text += f"\n... and {len(all_urls) - 20} more users"
        
        if inline and message_id:
            # Create inline keyboard
            keyboard_buttons = []
            uuid_str = str(uuid.uuid4())[:8]
            
            for user_id in list(all_urls.keys())[:10]:
                user_info = user_data.get(user_id, {})
                is_premium = user_info.get('is_premium', False)
                emoji = "⭐" if is_premium else "👤"
                keyboard_buttons.append([{
                    "text": f"{emoji} User {user_id}",
                    "callback_data": f"admin_user:{user_id}:{uuid_str}"
                }])
            
            keyboard_buttons.append([{"text": "🔙 BACK", "callback_data": f"admin_panel:{uuid_str}"}])
            keyboard = {"inline_keyboard": keyboard_buttons}
            
            edit_telegram_message(self.token, chat_id, message_id, users_text, reply_markup=keyboard)
        else:
            send_telegram_message(self.token, chat_id, users_text, reply_markup=get_admin_keyboard())
    
    def admin_user_details(self, chat_id, message_id, target_user_id):
        """Show user details for admin with Indian Time"""
        user_urls = get_user_urls(target_user_id)
        user_info = get_user_info(target_user_id)
        
        is_premium = user_info.get('is_premium', False)
        premium_until = user_info.get('premium_until', 'Not premium')
        join_date = user_info.get('join_date', 'Unknown')
        last_active = user_info.get('last_active', 'Unknown')
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        user_text = f"""
<b>👤 USER DETAILS</b>

<b>User ID:</b> <code>{target_user_id}</code>
<b>Status:</b> {"⭐ PREMIUM" if is_premium else "🆓 FREE"}
<b>Premium Until:</b> {premium_until}
<b>Joined:</b> {join_date}
<b>Last Active:</b> {last_active}
<b>URLs:</b> {len(user_urls)} URLs

<b>URL List:</b>
<b>Indian Time: {indian_time}</b>
        """
        
        for name, url in list(user_urls.items())[:10]:
            user_text += f"\n• {name}: {url[:50]}..."
        
        if len(user_urls) > 10:
            user_text += f"\n... and {len(user_urls) - 10} more URLs"
        
        keyboard = get_admin_user_inline_keyboard(target_user_id)
        edit_telegram_message(self.token, chat_id, message_id, user_text, reply_markup=keyboard)
    
    def admin_activate_premium(self, chat_id, message_id, target_user_id, days):
        """Admin activate premium directly from inline plans with Indian Time"""
        try:
            days_int = int(days)
            expiry = set_user_premium(target_user_id, days_int, chat_id)
            
            # Get Indian time
            utc_now = datetime.utcnow()
            ist_now = utc_now + timedelta(hours=5, minutes=30)
            indian_time = ist_now.strftime("%H:%M:%S")
            
            # Notify admin
            admin_text = f"""
✅ <b>PREMIUM ACTIVATED</b>

<b>For User:</b> <code>{target_user_id}</code>
<b>Plan:</b> {days} days
<b>Expires:</b> {expiry.strftime('%Y-%m-%d %H:%M:%S')}

<b>Now user can add up to 100 URLs!</b>

<b>Indian Time: {indian_time}</b>
User has been upgraded successfully!
            """
            
            # Notify user
            try:
                user_text = f"""
🎉 <b>PREMIUM ACTIVATED!</b>

Your account has been upgraded to Premium!

<b>Plan:</b> {days} days
<b>Expires:</b> {expiry.strftime('%Y-%m-%d %H:%M:%S')}

<b>Now you can add up to 100 URLs!</b>

Enjoy premium features!
                """
                send_telegram_message(self.token, target_user_id, user_text, reply_markup=get_main_menu_keyboard(target_user_id))
            except:
                pass
            
            send_telegram_message(self.token, chat_id, admin_text, reply_markup=get_admin_keyboard())
            
        except Exception as e:
            error_text = f"❌ Error: {str(e)}"
            send_telegram_message(self.token, chat_id, error_text, reply_markup=get_admin_keyboard())
    
    def admin_remove_premium(self, chat_id, message_id, target_user_id):
        """Admin remove premium from user (from inline) with Indian Time"""
        remove_user_premium(target_user_id)
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        # Notify admin
        admin_text = f"""
🗑️ <b>PREMIUM REMOVED</b>

Premium has been removed from user:
<code>{target_user_id}</code>

User is now on free plan (1 URL limit).

<b>Indian Time: {indian_time}</b>
        """
        
        # Notify user
        try:
            user_text = f"""
ℹ️ <b>PREMIUM ENDED</b>

Your premium subscription has been removed.
You are now on the free plan.

<b>Free Plan:</b>
• 1 URL maximum (was 100)
• 5-minute intervals
• Basic features

Contact admin if this was a mistake.
            """
            send_telegram_message(self.token, target_user_id, user_text, reply_markup=get_main_menu_keyboard(target_user_id))
        except:
            pass
        
        send_telegram_message(self.token, chat_id, admin_text, reply_markup=get_admin_keyboard())
    
    def admin_view_urls(self, chat_id, message_id, target_user_id):
        """Admin view user's URLs with Indian Time"""
        user_urls = get_user_urls(target_user_id)
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        if not user_urls:
            urls_text = f"""
<b>📭 NO URLs FOUND</b>

User <code>{target_user_id}</code> has no URLs.

<b>Indian Time: {indian_time}</b>
            """
        else:
            urls_text = f"""
<b>📋 URLs FOR USER {target_user_id}</b>

Total URLs: {len(user_urls)}

<b>URL List:</b>
<b>Indian Time: {indian_time}</b>
            """
            
            for name, url in user_urls.items():
                urls_text += f"\n• <b>{name}</b>: <code>{url[:60]}...</code>"
        
        send_telegram_message(self.token, chat_id, urls_text, reply_markup=get_admin_keyboard())
    
    def admin_user_info(self, chat_id, message_id, target_user_id):
        """Show detailed user info for admin with Indian Time"""
        user_info = get_user_info(target_user_id)
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        info_text = f"""
<b>📄 USER INFO</b>

<b>User ID:</b> <code>{target_user_id}</code>
<b>Premium:</b> {'✅ YES' if user_info.get('is_premium', False) else '❌ NO'}
<b>Premium Until:</b> {user_info.get('premium_until', 'N/A')}
<b>Joined:</b> {user_info.get('join_date', 'Unknown')}
<b>Last Active:</b> {user_info.get('last_active', 'Unknown')}
<b>Premium History:</b> {len(user_info.get('premium_history', []))} activations

<b>Indian Time: {indian_time}</b>
        """
        
        # Show premium history
        if 'premium_history' in user_info and user_info['premium_history']:
            info_text += "\n\n<b>📜 PREMIUM HISTORY:</b>"
            for hist in user_info['premium_history'][-5:]:  # Last 5 activations
                info_text += f"\n• {hist['days']} days by {hist.get('activated_by', 'Admin')} on {hist['activated_at']}"
        
        send_telegram_message(self.token, chat_id, info_text, reply_markup=get_admin_keyboard())
    
    def admin_premium_users(self, chat_id, inline=False, message_id=None):
        """List premium users with Indian Time"""
        user_data = load_user_data()
        premium_users = {uid: info for uid, info in user_data.items() if info.get('is_premium', False)}
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        premium_text = f"""
<b>⭐ PREMIUM USERS ({len(premium_users)})</b>

<b>Premium Users List:</b>
<b>Indian Time: {indian_time}</b>
        """
        
        for i, (user_id, info) in enumerate(list(premium_users.items())[:20], 1):
            premium_until = info.get('premium_until', 'Unknown')
            premium_text += f"\n{i}. User <code>{user_id}</code> - Until: {premium_until}"
        
        if len(premium_users) > 20:
            premium_text += f"\n... and {len(premium_users) - 20} more"
        
        if inline and message_id:
            uuid_str = str(uuid.uuid4())[:8]
            keyboard = {"inline_keyboard": [[{"text": "🔙 BACK", "callback_data": f"admin_panel:{uuid_str}"}]]}
            edit_telegram_message(self.token, chat_id, message_id, premium_text, reply_markup=keyboard)
        else:
            send_telegram_message(self.token, chat_id, premium_text, reply_markup=get_admin_keyboard())
    
    def admin_stats(self, chat_id, inline=False, message_id=None):
        """Show admin statistics with Indian Time"""
        all_urls = load_urls()
        user_data = load_user_data()
        settings_data = load_user_settings()
        
        total_users = len(all_urls)
        total_urls = sum(len(urls) for urls in all_urls.values())
        premium_users = sum(1 for user in user_data.values() if user.get('is_premium', False))
        free_users = total_users - premium_users
        
        # Calculate average URLs per user
        avg_urls = total_urls / total_users if total_users > 0 else 0
        
        # Count settings
        notifications_on = sum(1 for settings in settings_data.values() if settings.get('notifications', True))
        auto_ping_on = sum(1 for settings in settings_data.values() if settings.get('auto_ping', True))
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        indian_date = ist_now.strftime("%d-%m-%Y")
        
        stats_text = f"""
<b>📊 SYSTEM STATISTICS</b>

<b>👥 USER STATS:</b>
• Total Users: {total_users}
• Premium Users: {premium_users}
• Free Users: {free_users}
• Premium Rate: {(premium_users/total_users*100) if total_users > 0 else 0:.1f}%

<b>📈 URL STATS:</b>
• Total URLs: {total_urls}
• Average URLs/User: {avg_urls:.1f}
• Most URLs by User: {max([len(urls) for urls in all_urls.values()] + [0])}

<b>⚙️ SETTINGS STATS:</b>
• Notifications ON: {notifications_on}
• Auto Ping ON: {auto_ping_on}

<b>⚙️ SYSTEM INFO:</b>
• Bot Uptime: 100%
• Ping Interval: 5 minutes (for ALL users)
• Indian Time: {indian_time}
• Date: {indian_date}

<b>💾 DATA:</b>
• Users File: {os.path.getsize(USER_DATA_FILE) if os.path.exists(USER_DATA_FILE) else 0} bytes
• URLs File: {os.path.getsize(URL_DATA_FILE) if os.path.exists(URL_DATA_FILE) else 0} bytes
• Settings File: {os.path.getsize(SETTINGS_FILE) if os.path.exists(SETTINGS_FILE) else 0} bytes
        """
        
        if inline and message_id:
            uuid_str = str(uuid.uuid4())[:8]
            keyboard = {"inline_keyboard": [[{"text": "🔙 BACK", "callback_data": f"admin_panel:{uuid_str}"}]]}
            edit_telegram_message(self.token, chat_id, message_id, stats_text, reply_markup=keyboard)
        else:
            send_telegram_message(self.token, chat_id, stats_text, reply_markup=get_admin_keyboard())
    
    def admin_check_expiry(self, chat_id, inline=False, message_id=None):
        """Check and expire premium users with Indian Time"""
        expired = check_premium_expiry()
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        if expired:
            expiry_text = f"""
✅ <b>PREMIUM EXPIRY CHECKED</b>

Expired users: {len(expired)}

<b>Expired User IDs:</b>
{', '.join([str(uid) for uid in expired[:10]])}

<b>Indian Time: {indian_time}</b>
            """
            
            if len(expired) > 10:
                expiry_text += f"\n... and {len(expired) - 10} more"
        else:
            expiry_text = f"""
✅ <b>PREMIUM EXPIRY CHECKED</b>

No users have expired premium.
All premium subscriptions are active.

<b>Indian Time: {indian_time}</b>
            """
        
        if inline and message_id:
            uuid_str = str(uuid.uuid4())[:8]
            keyboard = {"inline_keyboard": [[{"text": "🔙 BACK", "callback_data": f"admin_panel:{uuid_str}"}]]}
            edit_telegram_message(self.token, chat_id, message_id, expiry_text, reply_markup=keyboard)
        else:
            send_telegram_message(self.token, chat_id, expiry_text, reply_markup=get_admin_keyboard())
    
    def cancel_operation(self, chat_id):
        """Cancel current operation with Indian Time"""
        if chat_id in self.user_states:
            del self.user_states[chat_id]
        
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        cancel_text = f"✅ Operation cancelled.\n\n<b>Indian Time: {indian_time}</b>"
        send_telegram_message(self.token, chat_id, cancel_text, reply_markup=get_main_menu_keyboard(chat_id))
    
    def send_unknown(self, chat_id):
        """Handle unknown command with Indian Time"""
        # Get Indian time
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        indian_time = ist_now.strftime("%H:%M:%S")
        
        send_telegram_message(
            self.token,
            chat_id,
            f"❌ Unknown command. Use the buttons below.\n\n<b>Indian Time: {indian_time}</b>",
            reply_markup=get_main_menu_keyboard(chat_id)
        )
    
    def send_shutdown_message(self):
        """Send shutdown message with Indian Time"""
        logger.info("Sending shutdown notifications...")
        
        # Only notify active users (last active within 24 hours)
        user_data = load_user_data()
        for user_id, info in user_data.items():
            try:
                last_active = datetime.strptime(info['last_active'], "%Y-%m-%d %H:%M:%S")
                if (datetime.now() - last_active).days < 1:
                    # Get Indian time
                    utc_now = datetime.utcnow()
                    ist_now = utc_now + timedelta(hours=5, minutes=30)
                    indian_time = ist_now.strftime("%H:%M:%S")
                    
                    send_telegram_message(
                        self.token,
                        user_id,
                        f"🛑 <b>Service Notice</b>\n\n"
                        f"Bot is going offline for maintenance.\n"
                        f"Service will resume shortly.\n"
                        f"<b>Indian Time: {indian_time}</b>",
                        reply_markup=get_main_menu_keyboard(user_id)
                    )
            except:
                pass

# ========== MAIN FUNCTION ==========
def main():
    """Start the bot"""
    print("\n" + "="*60)
    print("🤖 PREMIUM URL PING BOT - FULL WORKING")
    print("="*60)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")
    
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: Configure your bot token!")
        return
    
    if ADMIN_USER_IDS == [123456789]:
        print("❌ ERROR: Configure admin user IDs!")
        return
    
    # Create and start bot
    bot = PremiumURLPingBot(TELEGRAM_BOT_TOKEN, ADMIN_USER_IDS)
    
    try:
        bot.start()
    except KeyboardInterrupt:
        print("\n\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        logger.error(f"Bot crashed: {str(e)}")

if __name__ == '__main__':
    main()