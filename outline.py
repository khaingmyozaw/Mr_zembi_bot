#!/usr/bin/env python3
"""
Zembi VPN Bot - VLESS & Outline VPN Key Seller
===============================================

Features:
- VLESS keys via 3X-UI panel API (automated)
- Outline keys via Marzban panel API (automated)
- Plan-based IP limits for VLESS
- Outline: 1 key, 2 keys, 3 keys options (1 key = 1 device)
- 1 Month (30 days) validity for all plans
- Telegram username as client identifier
- Subscription links for easy app import
- Free trial with 24-hour validity (VLESS only)
- Payment screenshot submission
- Admin approval/rejection with waiting animation
- Auto VPN key generation on payment approval

BEFORE RUNNING:
1. Configure Telegram credentials (API_ID, API_HASH, BOT_TOKEN)
2. Configure ADMIN_USER_ID
3. Configure 3X-UI panel for VLESS
4. Configure Marzban panel for Outline
"""

import logging
import sys
import uuid
import time
import json
import asyncio
import os
import httpx
import urllib.parse
import base64
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Message,
)
from pyrogram.errors import FloodWait
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ==========================
# TELEGRAM CONFIG
# ==========================
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')

# ADMIN CONFIG
ADMIN_USER_ID = os.getenv('ADMIN_USER_ID')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')

# ==========================
# 3X-UI PANEL CONFIG (VLESS)
# ==========================
PANEL_URL = os.getenv('PANEL_URL')
PANEL_USERNAME = os.getenv('PANEL_USERNAME', 'admin')
PANEL_PASSWORD = os.getenv('PANEL_PASSWORD')

# VLESS SERVER CONFIG
SERVER_IP = os.getenv('SERVER_IP', '127.0.0.1')
SERVER_PORT = int(os.getenv('SERVER_PORT', '443'))
SUB_PORT = int(os.getenv('SUB_PORT', '2053'))

# Inbound IDs for VLESS
TRIAL_INBOUND_ID = int(os.getenv('TRIAL_INBOUND_ID', '1'))
PLAN1_INBOUND_ID = int(os.getenv('PLAN1_INBOUND_ID', '1'))
PLAN2_INBOUND_ID = int(os.getenv('PLAN2_INBOUND_ID', '2'))
PLAN3_INBOUND_ID = int(os.getenv('PLAN3_INBOUND_ID', '3'))

# ==========================
# MARZBAN PANEL CONFIG (OUTLINE)
# ==========================
# IMPORTANT: Do NOT include /dashboard in the URL!
# Correct: http://your-server:8080
# Wrong:   http://your-server:8080/dashboard
MARZBAN_URL = os.getenv('MARZBAN_URL')
MARZBAN_USERNAME = os.getenv('MARZBAN_USERNAME', 'admin')
MARZBAN_PASSWORD = os.getenv('MARZBAN_PASSWORD')
OUTLINE_SERVER_IP = os.getenv('OUTLINE_SERVER_IP', '127.0.0.1')
OUTLINE_INBOUND_NAME = os.getenv('OUTLINE_INBOUND_NAME', 'Shadowsocks TCP')

# Trial settings (VLESS only)
TRIAL_DURATION_HOURS = int(os.getenv('TRIAL_DURATION_HOURS', '24'))
TRIAL_TRAFFIC_GB = int(os.getenv('TRIAL_TRAFFIC_GB', '1'))
TRIAL_DEVICE_LIMIT = int(os.getenv('TRIAL_DEVICE_LIMIT', '1'))

# ==========================
# PLAN CONFIGURATION
# ==========================
plan_1_price = "5000 ks"
plan_2_price = "9450 ks"
plan_3_price = "13850 ks"

PAYMENT_NAME = "Khaing Myo Zaw"
KPAY_NO = "098 951 23061"
AYA_NO = "098 951 23061"
WAVE_NO = "098 951 23061"

# VLESS Plans (3X-UI) - IP limit based
VLESS_PLANS = {
    "vless_1": {
        "label": f"1 device = {plan_1_price}",
        "name": "VLESS Basic",
        "device": "1 device",
        "ip_limit": 1,
        "price": plan_1_price,
        "days": 30,
        "traffic_gb": 0,
        "inbound_id": PLAN1_INBOUND_ID,
        "type": "vless",
    },
    "vless_2": {
        "label": f"2 devices = {plan_2_price}",
        "name": "VLESS Silver",
        "device": "2 devices",
        "ip_limit": 2,
        "price": plan_2_price,
        "days": 30,
        "traffic_gb": 0,
        "inbound_id": PLAN2_INBOUND_ID,
        "type": "vless",
    },
    "vless_3": {
        "label": f"3 devices = {plan_3_price}",
        "name": "VLESS Golden",
        "device": "3 devices",
        "ip_limit": 3,
        "price": plan_3_price,
        "days": 30,
        "traffic_gb": 0,
        "inbound_id": PLAN3_INBOUND_ID,
        "type": "vless",
    },
}

# Outline Plans (Marzban) - 1 key = 1 device
OUTLINE_PLANS = {
    "outline_1": {
        "label": f"1 key = {plan_1_price}",
        "name": "Outline 1 Key",
        "num_keys": 1,
        "price": plan_1_price,
        "days": 30,
        "traffic_gb": 0,
        "type": "outline",
    },
    "outline_2": {
        "label": f"2 keys = {plan_2_price}",
        "name": "Outline 2 Keys",
        "num_keys": 2,
        "price": plan_2_price,
        "days": 30,
        "traffic_gb": 0,
        "type": "outline",
    },
    "outline_3": {
        "label": f"3 keys = {plan_3_price}",
        "name": "Outline 3 Keys",
        "num_keys": 3,
        "price": plan_3_price,
        "days": 30,
        "traffic_gb": 0,
        "type": "outline",
    },
}

# Combined plans for lookup
ALL_PLANS = {**VLESS_PLANS, **OUTLINE_PLANS}

# ==========================
# VALIDATE CONFIG
# ==========================
def validate_config():
    errors = []
    warnings = []
    
    if not API_ID:
        errors.append("API_ID is not set")
    if not API_HASH:
        errors.append("API_HASH is not set")
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN is not set")
    if not ADMIN_USER_ID:
        errors.append("ADMIN_USER_ID is not set")
    if not PANEL_URL:
        warnings.append("PANEL_URL is not set (VLESS won't work)")
    if not PANEL_PASSWORD:
        warnings.append("PANEL_PASSWORD is not set")
    if not MARZBAN_URL:
        warnings.append("MARZBAN_URL is not set (Outline won't work)")
    if not MARZBAN_PASSWORD:
        warnings.append("MARZBAN_PASSWORD is not set")
    
    if errors:
        print("=" * 60)
        print("ERROR: Missing required environment variables!")
        print("=" * 60)
        for err in errors:
            print(f"  ❌ {err}")
        print()
        print("Create a .env file with required variables.")
        print("=" * 60)
        sys.exit(1)
    
    if warnings:
        print("=" * 60)
        print("WARNINGS:")
        for warn in warnings:
            print(f"  ⚠️ {warn}")
        print("=" * 60)
    
    return True

validate_config()

# Convert to proper types after validation
API_ID = int(API_ID)
ADMIN_USER_ID = int(ADMIN_USER_ID)

# ==========================
# LOGGING
# ==========================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ==========================
# BOT INIT
# ==========================
app = Client(
    "zembi_vpn_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ==========================
# IN-MEMORY STORAGE
# ==========================
user_trials = {}
user_subscriptions = {}
pending_payments = {}
user_states = {}
waiting_tasks = {}

# ==========================
# VPN APPS LIST
# ==========================
VPN_APPS = [
    {"name": "V2RayNG", "platform": "Android", "url": "https://play.google.com/store/apps/details?id=com.v2ray.ang", "for": "vless"},
    {"name": "Hiddify", "platform": "Android/iOS", "url": "https://hiddify.com", "for": "vless"},
    {"name": "Streisand", "platform": "iOS", "url": "https://apps.apple.com/app/streisand", "for": "vless"},
    {"name": "V2RayN", "platform": "Windows", "url": "https://github.com/2dust/v2rayN", "for": "vless"},
    {"name": "Outline", "platform": "All Platforms", "url": "https://getoutline.org/get-started/#step-3", "for": "outline"},
]


# ==========================
# 3X-UI API CLASS (VLESS)
# ==========================
class XUIClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.username = username
        self.password = password
        self.session = None
        self.logged_in = False
    
    async def restart_xray(self) -> bool:
        if not self.logged_in:
            if not await self.login():
                return False
        
        restart_endpoints = [
            "/panel/setting/restartXrayService",
            "/server/restartXrayService",
            "/xui/setting/restartXrayService",
        ]
        
        for endpoint in restart_endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                resp = await self.session.post(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success"):
                        logger.info(f"✅ Xray restarted via {endpoint}")
                        return True
            except Exception as e:
                continue
        
        logger.warning("⚠️ Could not restart Xray")
        return False
    
    async def login(self) -> bool:
        if not self.base_url:
            return False
        try:
            self.session = httpx.AsyncClient(
                timeout=30.0,
                verify=False,
                follow_redirects=True,
            )
            
            login_url = f"{self.base_url}/login"
            response = await self.session.post(
                login_url,
                data={"username": self.username, "password": self.password},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    self.logged_in = True
                    logger.info("✅ Successfully logged into 3X-UI")
                    return True
            return False
        except Exception as e:
            logger.error(f"3X-UI Login error: {e}")
            return False
    
    async def get_inbound(self, inbound_id: int) -> dict | None:
        if not self.logged_in:
            if not await self.login():
                return None
        
        try:
            api_url = f"{self.base_url}/panel/api/inbounds/list"
            response = await self.session.get(api_url)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    for inbound in result.get("obj", []):
                        if inbound.get("id") == inbound_id:
                            return inbound
            return None
        except Exception as e:
            logger.error(f"Error getting inbound: {e}")
            return None
    
    async def add_client(
        self,
        inbound_id: int,
        email: str,
        tg_username: str = "",
        traffic_limit_gb: int = 0,
        expiry_days: int = 30,
        ip_limit: int = 1,
    ) -> dict | None:
        try:
            if not self.logged_in:
                if not await self.login():
                    return None
            
            inbound = await self.get_inbound(inbound_id)
            if not inbound:
                logger.error(f"Inbound {inbound_id} not found")
                return None
            
            client_uuid = str(uuid.uuid4())
            expiry_time = int((datetime.now() + timedelta(days=expiry_days)).timestamp() * 1000)
            traffic_limit = traffic_limit_gb * 1024 * 1024 * 1024 if traffic_limit_gb > 0 else 0
            
            client_email = f"{tg_username}_{int(time.time())}" if tg_username else email
            
            client_settings = {
                "id": client_uuid,
                "email": client_email,
                "limitIp": ip_limit,
                "totalGB": traffic_limit,
                "expiryTime": expiry_time,
                "enable": True,
                "tgId": "",
                "subId": client_email,
                "flow": ""
            }
            
            settings_json = json.dumps({"clients": [client_settings]})
            
            api_url = f"{self.base_url}/panel/api/inbounds/addClient"
            response = await self.session.post(
                api_url,
                data={"id": inbound_id, "settings": settings_json},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    logger.info(f"✅ VLESS Client added: {client_email} IP limit: {ip_limit}")
                    
                    await self.restart_xray()
                    
                    vless_key = self._generate_vless_key(inbound, client_uuid, client_email)
                    sub_link = f"https://{SERVER_IP}:{SUB_PORT}/sub/{urllib.parse.quote(client_email)}"
                    
                    return {
                        "uuid": client_uuid,
                        "email": client_email,
                        "expiry": datetime.now() + timedelta(days=expiry_days),
                        "ip_limit": ip_limit,
                        "vless_key": vless_key,
                        "sub_link": sub_link,
                    }
            return None
        except Exception as e:
            logger.error(f"Error adding VLESS client: {e}")
            return None
    
    def _generate_vless_key(self, inbound: dict, client_uuid: str, remark: str) -> str:
        try:
            stream_settings = json.loads(inbound.get("streamSettings", "{}"))
            port = inbound.get("port", SERVER_PORT)
            network = stream_settings.get("network", "tcp")
            security = stream_settings.get("security", "none")
            
            params = [f"type={network}"]
            
            if security == "tls":
                params.append("security=tls")
                tls_settings = stream_settings.get("tlsSettings", {})
                if tls_settings.get("serverName"):
                    params.append(f"sni={tls_settings['serverName']}")
            elif security == "reality":
                params.append("security=reality")
                reality_settings = stream_settings.get("realitySettings", {})
                if reality_settings.get("serverNames"):
                    params.append(f"sni={reality_settings['serverNames'][0]}")
                if reality_settings.get("publicKey"):
                    params.append(f"pbk={reality_settings['publicKey']}")
            else:
                params.append("security=none")
            
            if network == "ws":
                ws_settings = stream_settings.get("wsSettings", {})
                if ws_settings.get("path"):
                    params.append(f"path={urllib.parse.quote(ws_settings['path'])}")
            
            params.append("encryption=none")
            query_string = "&".join(params)
            encoded_remark = urllib.parse.quote(remark)
            
            return f"vless://{client_uuid}@{SERVER_IP}:{port}?{query_string}#{encoded_remark}"
        except Exception as e:
            return f"vless://{client_uuid}@{SERVER_IP}:{SERVER_PORT}?security=none&type=tcp#{remark}"


# ==========================
# MARZBAN API CLASS (OUTLINE)
# ==========================
class MarzbanClient:
    def __init__(self, base_url: str, username: str, password: str):
        # Remove /dashboard from base_url if present
        self.base_url = base_url.rstrip("/") if base_url else ""
        if "/dashboard" in self.base_url:
            self.base_url = self.base_url.replace("/dashboard", "")
        self.username = username
        self.password = password
        self.session = None
        self.access_token = None
        self.logged_in = False
    
    async def login(self) -> bool:
        if not self.base_url:
            logger.error("MARZBAN_URL is not set")
            return False
        try:
            self.session = httpx.AsyncClient(
                timeout=30.0,
                verify=False,
                follow_redirects=True,
            )
            
            # Marzban API login endpoint
            login_url = f"{self.base_url}/api/admin/token"
            logger.info(f"Marzban login URL: {login_url}")
            
            response = await self.session.post(
                login_url,
                data={
                    "username": self.username,
                    "password": self.password,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            logger.info(f"Marzban login response: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                self.access_token = result.get("access_token")
                if self.access_token:
                    self.logged_in = True
                    logger.info("✅ Successfully logged into Marzban")
                    return True
                else:
                    logger.error(f"No access_token in response: {result}")
            else:
                logger.error(f"Marzban login failed: {response.status_code}")
                logger.error(f"Response: {response.text[:500]}")
            
            return False
        except Exception as e:
            logger.error(f"Marzban Login error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def create_user(
        self,
        username: str,
        traffic_limit_gb: int = 0,
        expiry_days: int = 30,
    ) -> dict | None:
        """
        Create a new Shadowsocks user in Marzban for Outline.
        Returns the SS key (Outline compatible).
        """
        try:
            if not self.logged_in:
                if not await self.login():
                    return None
            
            # Calculate expiry timestamp
            expiry_time = int((datetime.now() + timedelta(days=expiry_days)).timestamp())
            traffic_limit = traffic_limit_gb * 1024 * 1024 * 1024 if traffic_limit_gb > 0 else 0
            
            # Unique username
            unique_username = f"{username}_{int(time.time())}"
            
            # Create user data for Marzban
            user_data = {
                "username": unique_username,
                "proxies": {
                    "shadowsocks": {
                        "method": "chacha20-ietf-poly1305"
                    }
                },
                "inbounds": {
                    "shadowsocks": [OUTLINE_INBOUND_NAME]
                },
                "expire": expiry_time,
                "data_limit": traffic_limit,
                "data_limit_reset_strategy": "no_reset",
                "status": "active",
                "note": f"Telegram: @{username}",
            }
            
            api_url = f"{self.base_url}/api/user"
            logger.info(f"Creating Marzban user: {unique_username}")
            
            response = await self.session.post(
                api_url,
                json=user_data,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            logger.info(f"Marzban create user response: {response.status_code}")
            
            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"✅ Outline user created: {unique_username}")
                
                # Get the SS link from the response
                ss_links = result.get("links", [])
                ss_key = None
                sub_link = None
                
                for link in ss_links:
                    if link.startswith("ss://"):
                        ss_key = link
                        break
                
                # Get subscription link
                sub_link = result.get("subscription_url", "")
                if not sub_link:
                    sub_link = f"{self.base_url}/sub/{unique_username}"
                
                if not ss_key:
                    # Try to construct SS key manually
                    proxies = result.get("proxies", {})
                    ss_proxy = proxies.get("shadowsocks", {})
                    if ss_proxy:
                        password = ss_proxy.get("password", "")
                        method = ss_proxy.get("method", "chacha20-ietf-poly1305")
                        port = 443  # Default port - adjust based on your config
                        
                        auth = base64.urlsafe_b64encode(
                            f"{method}:{password}".encode()
                        ).decode().rstrip("=")
                        ss_key = f"ss://{auth}@{OUTLINE_SERVER_IP}:{port}#{urllib.parse.quote(unique_username)}"
                
                return {
                    "username": unique_username,
                    "expiry": datetime.now() + timedelta(days=expiry_days),
                    "ss_key": ss_key,
                    "sub_link": sub_link,
                }
            else:
                logger.error(f"Marzban create user failed: {response.status_code}")
                logger.error(f"Response: {response.text[:500]}")
            
            return None
        except Exception as e:
            logger.error(f"Error creating Marzban user: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None


# Initialize API clients
xui = XUIClient(PANEL_URL, PANEL_USERNAME, PANEL_PASSWORD) if PANEL_URL else None
marzban = MarzbanClient(MARZBAN_URL, MARZBAN_USERNAME, MARZBAN_PASSWORD) if MARZBAN_URL else None


# ==========================
# WAITING ANIMATION
# ==========================
async def show_waiting_animation(client: Client, chat_id: int, message_id: int, payment_id: str):
    frames = ["⏳", "⌛"]
    frame_idx = 0
    
    while payment_id in pending_payments and pending_payments[payment_id]["status"] == "pending":
        try:
            payment = pending_payments[payment_id]
            elapsed = int(time.time() - payment["timestamp"])
            mins, secs = divmod(elapsed, 60)
            
            vpn_type = "🔐 VLESS" if payment["plan"].get("type") == "vless" else "🌐 Outline"
            
            text = (
                f"{frames[frame_idx]} **Admin စစ်ဆေးနေပါတယ်...**\n\n"
                f"💳 Payment ID: `{payment_id[:8]}`\n"
                f"📦 Plan: {vpn_type} - {payment['plan_name']}\n"
                f"⏱ စောင့်ဆိုင်းချိန်: {mins}:{secs:02d}\n\n"
                "📸 Screenshot ကို Admin ဆီပို့ပြီးပါပြီ။\n\n"
                "📸 5-30 မိနစ်ကြာသည်အထိ reply တစ်စုံတစ်ရာ မရရှိပါက Support ကို နှိပ်ပြီး တိုက်ရိုက် ဆက်သွယ်နိုင်ပါတယ်ခင်ဗျာ။"
            )
            
            await client.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text
            )
            
            frame_idx = (frame_idx + 1) % len(frames)
            await asyncio.sleep(3)
            
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(5)


# ==========================
# HELPERS
# ==========================
def get_main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎁 Free Trial", callback_data="free_trial"),
            InlineKeyboardButton("📋 My Subscriptions", callback_data="my_subs"),
        ],
        [
            InlineKeyboardButton("📲 VPN Apps", callback_data="vpn_apps"),
            InlineKeyboardButton("🆘 Support", url=f"https://t.me/{ADMIN_USERNAME}"),
        ],
        [
            InlineKeyboardButton("🔐 VLESS VPN", callback_data="vless_prices"),
            InlineKeyboardButton("🌐 Outline VPN", callback_data="outline_prices"),
        ],
    ])


def get_username(user) -> str:
    if user.username:
        return user.username
    elif user.first_name:
        return f"{user.first_name}_{user.id}"
    else:
        return f"user_{user.id}"


# ==========================
# /start COMMAND
# ==========================
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    user_states.pop(message.from_user.id, None)
    
    user_name = message.from_user.first_name or "User"
    text = (
        f"မင်္ဂလာပါ {user_name}! 🙏🏻\n\n"
        "ကျနော်က **Zembi** ပါ။ ✌🏻\n\n"
        "🔐 **VLESS** နဲ့ 🌐 **Outline** VPN key တွေကို\n"
        "စျေးနှုန်း ချိုချိုသာသာနဲ့ ရောင်းပေးနေတာပါဗျ။\n\n"
        "**🔐 VLESS VPN:**\n"
        "• လက်ရှိ မြန်မာနိုင်ငံနှင့် အသင့်တော်ဆုံး\n"
        "• V2Ray, Hiddify app များဖြင့် သုံးရန်\n"
        "• Singapore Server 🇸🇬\n"
        "• IP limit based (1 key = multi device)\n\n"
        "**🌐 Outline VPN:**\n"
        "• အလွယ်တကူ ချိတ်ဆက်နိုင်\n"
        "• Outline app ဖြင့် သုံးရန်\n"
        "• US Server 🇺🇸\n"
        "• 1 key = 1 device\n\n"
        "📊 Data: Unlimited\n"
        "⏰ Validity: 30 Days\n\n"
        "အောက်က menu မှ \n"
        "VLESS VPN သို့မဟုတ် Outline VPN ကိုနှိပ်ပြီး ဝယ်ယူနိုင်ပါတယ်ဗျ။\n\n"
        "အသေးစိတ်သိလိုပါက Support ကိုနှိပ်ပြီး admin နဲ့ ဆက်သွယ်နိုင်ပါတယ်နော်။\n\n"
    )
    await message.reply_text(text, reply_markup=get_main_menu_keyboard())


# ==========================
# CALLBACK HANDLER
# ==========================
@app.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id
    user = query.from_user
    
    await query.answer()

    # ========== FREE TRIAL (VLESS only) ==========
    if data == "free_trial":
        if user_trials.get(user_id, {}).get("used"):
            await query.message.reply_text(
                "❌ **Free Trial ယူပြီးသားဖြစ်ပါတယ်။**",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 VLESS VPN", callback_data="vless_prices")],
                    [InlineKeyboardButton("🌐 Outline VPN", callback_data="outline_prices")],
                    [InlineKeyboardButton("⬅️ Back", callback_data="back_menu")],
                ])
            )
            return
        
        if not xui:
            await query.message.reply_text("❌ VLESS server not configured.")
            return
        
        loading_msg = await query.message.reply_text("⏳ Trial key ထုတ်ပေးနေပါတယ်...")
        
        tg_username = get_username(user)
        result = await xui.add_client(
            inbound_id=TRIAL_INBOUND_ID,
            email=f"trial_{tg_username}",
            tg_username=tg_username,
            traffic_limit_gb=TRIAL_TRAFFIC_GB,
            expiry_days=TRIAL_DURATION_HOURS / 24,
            ip_limit=TRIAL_DEVICE_LIMIT,
        )
        
        if result:
            user_trials[user_id] = {"used": True, "key": result["vless_key"]}
            expiry = result["expiry"].strftime("%Y-%m-%d %H:%M")
            
            if user_id not in user_subscriptions:
                user_subscriptions[user_id] = []
            user_subscriptions[user_id].append({
                "plan": "Free Trial (VLESS)",
                "type": "vless",
                "status": "active",
                "expires": expiry,
                "key": result["vless_key"],
                "sub_link": result["sub_link"],
                "ip_limit": TRIAL_DEVICE_LIMIT,
            })
            
            await loading_msg.edit_text(
                "🎁 **Free Trial Activated!**\n\n"
                f"📱 Device Limit: {TRIAL_DEVICE_LIMIT}\n"
                f"⏰ Duration: {TRIAL_DURATION_HOURS} Hours\n"
                f"📅 Expires: {expiry}\n\n"
                "🔑 **VLESS Key:**\n"
                f"`{result['vless_key']}`\n\n"
                "_(Tap to copy)_",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📱 Open Sub Link", url=result['sub_link'])],
                    [InlineKeyboardButton("📲 VPN Apps", callback_data="vpn_apps")],
                    [InlineKeyboardButton("⬅️ Menu", callback_data="back_menu")],
                ])
            )
        else:
            await loading_msg.edit_text(
                "❌ **Error ဖြစ်သွားပါတယ်။** Admin ကို ဆက်သွယ်ပါ။",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🆘 Support", url=f"https://t.me/{ADMIN_USERNAME}")],
                ])
            )

    # ========== MY SUBSCRIPTIONS ==========
    elif data == "my_subs":
        subs = user_subscriptions.get(user_id, [])
        if subs:
            text = "📋 **Your Subscriptions:**\n\n"
            buttons = []
            
            for i, sub in enumerate(subs, 1):
                status_emoji = "✅" if sub.get("status") == "active" else "❌"
                type_emoji = "🔐" if sub.get("type") == "vless" else "🌐"
                text += (
                    f"**{i}. {type_emoji} {sub['plan']}** {status_emoji}\n"
                    f"   📅 Expires: {sub['expires']}\n\n"
                )
                buttons.append([InlineKeyboardButton(
                    f"🔑 View Key #{i}", 
                    callback_data=f"view_key_{i-1}"
                )])
            
            buttons.append([
                InlineKeyboardButton("🔐 VLESS VPN", callback_data="vless_prices"),
                InlineKeyboardButton("🌐 Outline VPN", callback_data="outline_prices"),
            ])
            buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="back_menu")])
            
            await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await query.message.reply_text(
                "📋 **Subscription မရှိသေးပါ။**\n🎁 Free Trial စမ်းကြည့်ပါ!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎁 Free Trial", callback_data="free_trial")],
                    [InlineKeyboardButton("🔐 VLESS VPN", callback_data="vless_prices")],
                    [InlineKeyboardButton("🌐 Outline VPN", callback_data="outline_prices")],
                    [InlineKeyboardButton("⬅️ Back", callback_data="back_menu")],
                ])
            )

    # ========== VIEW KEY DETAILS ==========
    elif data.startswith("view_key_"):
        key_idx = int(data.replace("view_key_", ""))
        subs = user_subscriptions.get(user_id, [])
        
        if key_idx < len(subs):
            sub = subs[key_idx]
            type_emoji = "🔐" if sub.get("type") == "vless" else "🌐"
            
            # Handle multiple keys for Outline
            keys = sub.get("keys", [sub.get("key", "N/A")])
            if isinstance(keys, str):
                keys = [keys]
            
            text = (
                f"{type_emoji} **{sub['plan']}**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📅 Expires: {sub['expires']}\n"
            )
            
            if sub.get("type") == "vless":
                text += f"📱 IP Limit: {sub.get('ip_limit', 1)} device(s)\n\n"
                text += "🔑 **VLESS Key (Tap to copy):**\n"
                text += f"`{keys[0]}`\n\n"
            else:
                text += f"🔑 Keys: {len(keys)}\n\n"
                for i, key in enumerate(keys, 1):
                    text += f"**Key #{i}:**\n`{key}`\n\n"
            
            if sub.get('sub_link'):
                text += f"📱 **Subscription Link:**\n`{sub.get('sub_link')}`"
            
            buttons = []
            if sub.get('sub_link'):
                buttons.append([InlineKeyboardButton("📱 Open Sub Link", url=sub['sub_link'])])
            buttons.append([InlineKeyboardButton("📲 VPN Apps", callback_data="vpn_apps")])
            buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="my_subs")])
            
            await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    # ========== VLESS PRICES ==========
    elif data == "vless_prices":
        await query.message.reply_text(
            "🔐 **VLESS VPN Plans**\n\n"
            "✅ Unlimited Data\n"
            "✅ 30 Days Validity\n"
            "✅ Singapore Server 🇸🇬\n"
            "✅ High-Speed\n"
            "✅ 1 Key = Multi Device (IP based)\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🥉 **Basic** - {plan_1_price} (1 device)\n"
            f"🥈 **Silver** - {plan_2_price} (2 devices)\n"
            f"🥇 **Golden** - {plan_3_price} (3 devices)\n\n"
            "Plan ရွေးချယ်ပါ:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🥉 Basic - {plan_1_price}", callback_data="buy_vless_1")],
                [InlineKeyboardButton(f"🥈 Silver - {plan_2_price}", callback_data="buy_vless_2")],
                [InlineKeyboardButton(f"🥇 Golden - {plan_3_price}", callback_data="buy_vless_3")],
                [InlineKeyboardButton("🌐 View Outline Plans", callback_data="outline_prices")],
                [InlineKeyboardButton("⬅️ Back", callback_data="back_menu")],
            ])
        )

    # ========== OUTLINE PRICES ==========
    elif data == "outline_prices":
        await query.message.reply_text(
            "🌐 **Outline VPN Plans**\n\n"
            "✅ Unlimited Data\n"
            "✅ 30 Days Validity\n"
            "✅ Easy to connect\n"
            "✅ Works on all platforms\n"
            "⚠️ 1 Key = 1 Device\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🥉 **1 Key** - {plan_1_price}\n"
            f"🥈 **2 Keys** - {plan_2_price}\n"
            f"🥇 **3 Keys** - {plan_3_price}\n\n"
            "Plan ရွေးချယ်ပါ:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🥉 1 Key - {plan_1_price}", callback_data="buy_outline_1")],
                [InlineKeyboardButton(f"🥈 2 Keys - {plan_2_price}", callback_data="buy_outline_2")],
                [InlineKeyboardButton(f"🥇 3 Keys - {plan_3_price}", callback_data="buy_outline_3")],
                [InlineKeyboardButton("🔐 View VLESS Plans", callback_data="vless_prices")],
                [InlineKeyboardButton("⬅️ Back", callback_data="back_menu")],
            ])
        )

    # ========== BUY VLESS PLAN ==========
    elif data.startswith("buy_vless_"):
        plan_key = data.replace("buy_", "")
        plan = VLESS_PLANS.get(plan_key)
        
        if not plan:
            return
        
        user_states[user_id] = {
            "state": "waiting_screenshot",
            "plan_key": plan_key,
            "plan": plan
        }
        
        text = (
            f"🔐 **{plan['name']}**\n\n"
            f"📱 IP Limit: {plan['ip_limit']} device(s)\n"
            f"📊 Data: Unlimited\n"
            f"⏰ Validity: {plan['days']} days\n"
            f"💵 Price: **{plan['price']}**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "**💳 ငွေလွှဲရန်:**\n\n"
            f"💰 **K Pay** - {PAYMENT_NAME}\n"
            f"   📞 `{KPAY_NO}`\n\n"
            f"💰 **AYA Pay** - {PAYMENT_NAME}\n"
            f"   📞 `{AYA_NO}`\n\n"
            f"💰 **Wave Pay** - {PAYMENT_NAME}\n"
            f"   📞 `{WAVE_NO}`\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📸 **ငွေလွှဲပြီးရင် screenshot ပို့ပေးပါခင်ဗျာ။**\n\n"
            "⚠️ **Note မှာ VPN နဲ့ ပတ်သတ်တဲ့ စာသားတွေ မရေးပါနဲ့နော်!**"
        )
        
        await query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")],
            ])
        )

    # ========== BUY OUTLINE PLAN ==========
    elif data.startswith("buy_outline_"):
        plan_key = data.replace("buy_", "")
        plan = OUTLINE_PLANS.get(plan_key)
        
        if not plan:
            return
        
        user_states[user_id] = {
            "state": "waiting_screenshot",
            "plan_key": plan_key,
            "plan": plan
        }
        
        text = (
            f"🌐 **{plan['name']}**\n\n"
            f"🔑 Keys: {plan['num_keys']}\n"
            f"📊 Data: Unlimited\n"
            f"⏰ Validity: {plan['days']} days\n"
            f"💵 Price: **{plan['price']}**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "**💳 ငွေလွှဲရန်:**\n\n"
            f"💰 **K Pay** - {PAYMENT_NAME}\n"
            f"   📞 `{KPAY_NO}`\n\n"
            f"💰 **AYA Pay** - {PAYMENT_NAME}\n"
            f"   📞 `{AYA_NO}`\n\n"
            f"💰 **Wave Pay** - {PAYMENT_NAME}\n"
            f"   📞 `{WAVE_NO}`\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📸 **ငွေလွှဲပြီးရင် screenshot ပို့ပေးပါ။**\n\n"
            "⚠️ **Note မှာ VPN နဲ့ ပတ်သတ်တဲ့ စာသားတွေ မရေးပါနဲ့နော်!**"
        )
        
        await query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")],
            ])
        )

    # ========== CANCEL PAYMENT ==========
    elif data == "cancel_payment":
        user_states.pop(user_id, None)
        await query.message.reply_text("❌ **ပယ်ဖျက်လိုက်ပါပြီ။**", reply_markup=get_main_menu_keyboard())

    # ========== VPN APPS ==========
    elif data == "vpn_apps":
        text = "📲 **VPN Apps**\n\n"
        text += "**🔐 For VLESS:**\n"
        buttons = []
        for app in VPN_APPS:
            if app["for"] == "vless":
                text += f"• {app['name']} - {app['platform']}\n"
                buttons.append([InlineKeyboardButton(f"📥 {app['name']}", url=app["url"])])
        
        text += "\n**🌐 For Outline:**\n"
        for app in VPN_APPS:
            if app["for"] == "outline":
                text += f"• {app['name']} - {app['platform']}\n"
                buttons.append([InlineKeyboardButton(f"📥 {app['name']}", url=app["url"])])
        
        buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="back_menu")])
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    # ========== ADMIN APPROVE ==========
    elif data.startswith("approve_"):
        if user_id != ADMIN_USER_ID:
            await query.answer("❌ Admin only!", show_alert=True)
            return
        
        payment_id = data.replace("approve_", "")
        
        if payment_id not in pending_payments:
            await query.answer("❌ Not found!", show_alert=True)
            return
        
        payment = pending_payments[payment_id]
        
        if payment["status"] != "pending":
            await query.answer("❌ Already processed!", show_alert=True)
            return
        
        if payment_id in waiting_tasks:
            waiting_tasks[payment_id].cancel()
            del waiting_tasks[payment_id]
        
        pending_payments[payment_id]["status"] = "approved"
        
        plan = payment["plan"]
        buyer_user_id = payment["user_id"]
        tg_username = payment["username"]
        plan_type = plan.get("type", "vless")
        
        result = None
        
        if plan_type == "vless":
            if not xui:
                await query.message.edit_caption(
                    caption=query.message.caption + "\n\n❌ VLESS server not configured!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📤 Message User", url=f"tg://user?id={buyer_user_id}")],
                    ])
                )
                del pending_payments[payment_id]
                return
            
            # Generate VLESS key from 3X-UI
            inbound_id = plan.get("inbound_id", PLAN1_INBOUND_ID)
            result = await xui.add_client(
                inbound_id=inbound_id,
                email=f"{tg_username}_{plan['name'].replace(' ', '_')}",
                tg_username=tg_username,
                traffic_limit_gb=plan.get("traffic_gb", 0),
                expiry_days=plan.get("days", 30),
                ip_limit=plan.get("ip_limit", 1),
            )
            
            if result:
                if buyer_user_id not in user_subscriptions:
                    user_subscriptions[buyer_user_id] = []
                
                user_subscriptions[buyer_user_id].append({
                    "plan": plan["name"],
                    "type": "vless",
                    "status": "active",
                    "expires": result["expiry"].strftime("%Y-%m-%d %H:%M"),
                    "key": result["vless_key"],
                    "sub_link": result["sub_link"],
                    "ip_limit": plan.get("ip_limit", 1),
                })
                
                try:
                    await client.send_message(
                        chat_id=buyer_user_id,
                        text=(
                            "🎉 **Payment Approved!**\n"
                            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"🔐 **{plan['name']}** activated!\n\n"
                            f"📱 IP Limit: {plan.get('ip_limit', 1)} device(s)\n"
                            f"📅 Duration: {plan.get('days', 30)} days\n"
                            f"⏰ Expires: {result['expiry'].strftime('%Y-%m-%d %H:%M')}\n\n"
                            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                            "🔑 **VLESS Key (Tap to copy):**\n"
                            f"`{result['vless_key']}`\n\n"
                            "ကျေးဇူးတင်ပါတယ် 🙏"
                        ),
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("📱 Open Sub Link", url=result['sub_link'])],
                            [InlineKeyboardButton("📋 My Subscriptions", callback_data="my_subs")],
                            [InlineKeyboardButton("📲 VPN Apps", callback_data="vpn_apps")],
                        ])
                    )
                except Exception as e:
                    logger.error(f"Failed to send to user: {e}")
                
                await query.message.edit_caption(
                    caption=query.message.caption + f"\n\n✅ **APPROVED**\n🔐 VLESS Key sent",
                    reply_markup=None
                )
        
        else:
            # Generate Outline keys from Marzban
            if not marzban:
                await query.message.edit_caption(
                    caption=query.message.caption + "\n\n❌ Marzban server not configured!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📤 Message User", url=f"tg://user?id={buyer_user_id}")],
                    ])
                )
                del pending_payments[payment_id]
                return
            
            num_keys = plan.get("num_keys", 1)
            generated_keys = []
            sub_link = None
            expiry = None
            
            for i in range(num_keys):
                key_result = await marzban.create_user(
                    username=f"{tg_username}_key{i+1}",
                    traffic_limit_gb=plan.get("traffic_gb", 0),
                    expiry_days=plan.get("days", 30),
                )
                
                if key_result:
                    generated_keys.append(key_result["ss_key"])
                    if not sub_link:
                        sub_link = key_result.get("sub_link", "")
                    if not expiry:
                        expiry = key_result["expiry"]
            
            if generated_keys:
                if buyer_user_id not in user_subscriptions:
                    user_subscriptions[buyer_user_id] = []
                
                user_subscriptions[buyer_user_id].append({
                    "plan": plan["name"],
                    "type": "outline",
                    "status": "active",
                    "expires": expiry.strftime("%Y-%m-%d %H:%M") if expiry else "N/A",
                    "keys": generated_keys,
                    "key": generated_keys[0],
                    "sub_link": sub_link,
                    "num_keys": len(generated_keys),
                })
                
                # Build message with all keys
                keys_text = ""
                for i, key in enumerate(generated_keys, 1):
                    keys_text += f"**Key #{i}:**\n`{key}`\n\n"
                
                try:
                    await client.send_message(
                        chat_id=buyer_user_id,
                        text=(
                            "🎉 **Payment Approved!**\n"
                            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"🌐 **{plan['name']}** activated!\n\n"
                            f"🔑 Keys: {len(generated_keys)}\n"
                            f"📅 Duration: {plan.get('days', 30)} days\n"
                            f"⏰ Expires: {expiry.strftime('%Y-%m-%d %H:%M') if expiry else 'N/A'}\n\n"
                            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                            "🔑 **Outline Keys (Tap to copy):**\n\n"
                            f"{keys_text}"
                            "💡 Outline app ဖွင့်ပြီး key ကို paste လုပ်ပါ။\n\n"
                            "ကျေးဇူးတင်ပါတယ် 🙏"
                        ),
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("📋 My Subscriptions", callback_data="my_subs")],
                            [InlineKeyboardButton("📲 VPN Apps", callback_data="vpn_apps")],
                        ])
                    )
                except Exception as e:
                    logger.error(f"Failed to send to user: {e}")
                
                await query.message.edit_caption(
                    caption=query.message.caption + f"\n\n✅ **APPROVED**\n🌐 {len(generated_keys)} Outline Key(s) sent",
                    reply_markup=None
                )
                
                result = True  # Mark as successful
        
        if not result:
            try:
                await client.send_message(
                    chat_id=buyer_user_id,
                    text="✅ Payment approved!\n⚠️ Key gen failed. Admin will send manually."
                )
            except:
                pass
            await query.message.edit_caption(
                caption=query.message.caption + "\n\n✅ APPROVED - ⚠️ Key gen failed!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📤 Message User", url=f"tg://user?id={buyer_user_id}")],
                ])
            )
        
        del pending_payments[payment_id]

    # ========== ADMIN REJECT ==========
    elif data.startswith("reject_"):
        if user_id != ADMIN_USER_ID:
            await query.answer("❌ Admin only!", show_alert=True)
            return
        
        payment_id = data.replace("reject_", "")
        
        if payment_id not in pending_payments:
            await query.answer("❌ Not found!", show_alert=True)
            return
        
        payment = pending_payments[payment_id]
        
        if payment["status"] != "pending":
            await query.answer("❌ Already processed!", show_alert=True)
            return
        
        if payment_id in waiting_tasks:
            waiting_tasks[payment_id].cancel()
            del waiting_tasks[payment_id]
        
        pending_payments[payment_id]["status"] = "rejected"
        
        try:
            await client.send_message(
                chat_id=payment["user_id"],
                text="❌ **Payment Rejected**\n\nအားနာပါတယ်ခင်ဗျာ... \nလူကြီးမင်း၏ Screenshot ကို ပြန်လည် စစ်ဆေးပေးပါဦးဗျာ။",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🆘 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")],
                    [InlineKeyboardButton("🔄 Try Again", callback_data="back_menu")],
                ])
            )
        except Exception as e:
            logger.error(f"Failed to notify user: {e}")
        
        await query.message.edit_caption(
            caption=query.message.caption + "\n\n❌ **REJECTED**",
            reply_markup=None
        )
        
        del pending_payments[payment_id]

    # ========== BACK TO MENU ==========
    elif data == "back_menu":
        user_states.pop(user_id, None)
        await query.message.reply_text("🔐 **Zembi VPN Bot**\n\nMenu:", reply_markup=get_main_menu_keyboard())


# ==========================
# SCREENSHOT HANDLER
# ==========================
@app.on_message(filters.photo & filters.private)
async def screenshot_handler(client: Client, message: Message):
    user_id = message.from_user.id
    user = message.from_user
    
    if user_id not in user_states or user_states[user_id].get("state") != "waiting_screenshot":
        await message.reply_text(
            "❓ Plan ရွေးပါ။",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔐 VLESS VPN", callback_data="vless_prices")],
                [InlineKeyboardButton("🌐 Outline VPN", callback_data="outline_prices")],
            ])
        )
        return
    
    plan_key = user_states[user_id]["plan_key"]
    plan = user_states[user_id]["plan"]
    tg_username = get_username(user)
    plan_type = plan.get("type", "vless")
    
    payment_id = str(uuid.uuid4())
    
    pending_payments[payment_id] = {
        "user_id": user_id,
        "username": tg_username,
        "first_name": user.first_name or "User",
        "plan_key": plan_key,
        "plan_name": plan["name"],
        "plan": plan,
        "photo_file_id": message.photo.file_id,
        "timestamp": time.time(),
        "status": "pending",
        "chat_id": message.chat.id,
    }
    
    user_states.pop(user_id, None)
    
    type_emoji = "🔐" if plan_type == "vless" else "🌐"
    
    waiting_msg = await message.reply_text(
        f"✅ **Screenshot လက်ခံရရှိပါပြီ!**\n\n"
        f"📦 Plan: {type_emoji} {plan['name']}\n"
        f"⏳ Admin စစ်ဆေးနေပါတယ်..."
    )
    
    pending_payments[payment_id]["message_id"] = waiting_msg.id
    
    # Prepare admin text based on plan type
    if plan_type == "vless":
        plan_info = f"📱 IP Limit: {plan.get('ip_limit', 1)}"
    else:
        plan_info = f"🔑 Keys: {plan.get('num_keys', 1)}"
    
    admin_text = (
        f"💳 **New Payment**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 User: {user.first_name}\n"
        f"📧 Username: @{tg_username}\n"
        f"🆔 ID: `{user_id}`\n\n"
        f"📦 Plan: **{type_emoji} {plan['name']}**\n"
        f"💵 Price: {plan['price']}\n"
        f"{plan_info}\n\n"
        f"💳 Payment ID: `{payment_id[:8]}`"
    )
    
    try:
        await client.send_photo(
            chat_id=ADMIN_USER_ID,
            photo=message.photo.file_id,
            caption=admin_text,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_{payment_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_{payment_id}"),
                ],
            ])
        )
        
        task = asyncio.create_task(
            show_waiting_animation(client, message.chat.id, waiting_msg.id, payment_id)
        )
        waiting_tasks[payment_id] = task
        
    except Exception as e:
        logger.error(f"Failed to forward to admin: {e}")
        await message.reply_text(
            "❌ Admin ဆီပို့မရပါ။",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🆘 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")],
            ])
        )


# ==========================
# ADMIN COMMANDS
# ==========================
@app.on_message(filters.command("admin") & filters.private)
async def admin_panel(client: Client, message: Message):
    if message.from_user.id != ADMIN_USER_ID:
        return
    
    pending = len([p for p in pending_payments.values() if p["status"] == "pending"])
    
    await message.reply_text(
        f"👑 **Admin Panel**\n\n"
        f"⏳ Pending: {pending}\n"
        f"👥 Subscribers: {len(user_subscriptions)}\n"
        f"🎁 Trial users: {len(user_trials)}\n\n"
        f"**Commands:**\n"
        f"/generate <user_id> <plan_key>"
    )


# ==========================
# MAIN
# ==========================
if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Zembi VPN Bot")
    print("   🔐 VLESS (3X-UI) - Auto key generation")
    print("   🌐 Outline (Marzban) - Auto key generation")
    print("=" * 50)
    
    try:
        app.run()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)