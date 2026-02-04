#!/usr/bin/env python3
"""
Zembi VPN Bot - VLESS VPN Key Seller with 3X-UI Integration
============================================================

Features:
- Automatic VPN key generation via 3X-UI panel API
- Plan-based IP limits:
  * Basic Plan: 1 device (IP limit: 1)
  * Silver Plan: 2 devices (IP limit: 2)
  * Golden Plan: 3 devices (IP limit: 3)
- 1 Month (30 days) validity for all plans
- Telegram username as client identifier
- Subscription links for easy app import
- Free trial with 24-hour validity
- Payment screenshot submission (users send to bot)
- Admin approval/rejection with waiting animation
- Auto VPN key generation on payment approval
- Subscription link as keyboard button on payment success
- Full copyable keys in My Subscriptions

BEFORE RUNNING:
1. Configure your Telegram credentials (API_ID, API_HASH, BOT_TOKEN)
2. Configure ADMIN_USER_ID (your Telegram user ID)
3. Configure your 3X-UI panel URL and credentials
4. Set your inbound IDs in the config
"""

import logging
import sys
import uuid
import time
import json
import asyncio
import httpx
import urllib.parse
import os
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

# ==========================
# TELEGRAM CONFIG
# ==========================
API_ID = os.getenv('API_ID')                    # <- Your API ID from my.telegram.org (INTEGER!)
API_HASH = os.getenv('API_HASH')      # <- Your API hash from my.telegram.org
BOT_TOKEN = os.getenv('BOT_TOKEN')  # <- Your bot token from @BotFather

# ADMIN CONFIG (IMPORTANT!)
ADMIN_USER_ID = os.getenv('ADMIN_USER_ID')            # <- Your Telegram user ID (send /id to @userinfobot)
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')       # <- Your admin username for support (without @)

# ==========================
# 3X-UI PANEL CONFIG
# ==========================
PANEL_URL = os.getenv('PANEL_URL')  # <- Your 3X-UI panel URL
PANEL_USERNAME = os.getenv('PANEL_USERNAME') # <- 3X-UI panel username  
PANEL_PASSWORD = os.getenv('PANEL_PASSWORD')                    # <- 3X-UI panel password

# SERVER CONFIG (for subscription links)
SERVER_IP = os.getenv('SERVER_IP')               # <- Your VPN server IP (e.g., "123.45.67.89")
SERVER_PORT = os.getenv('SERVER_PORT')                          # <- Your VPN inbound port
SUB_PORT = os.getenv('SUB_PORT')                            # <- Subscription port (usually same as panel port)

# Inbound IDs
TRIAL_INBOUND_ID = os.getenv('TRIAL_INBOUND_ID')                       # <- Inbound ID for trial keys
PAID_INBOUND_ID = os.getenv('PAID_INBOUND_ID')                        # <- Inbound ID for paid keys

# Trial settings
TRIAL_DURATION_HOURS = 24
TRIAL_TRAFFIC_GB = 1
TRIAL_DEVICE_LIMIT = 1

# ==========================
# PLAN CONFIGURATION
# ==========================
# All plans: 30 days validity, unlimited traffic
# IP limit = device limit
plan_1_price = "5000 ks"
plan_2_price = "9450 ks"
plan_3_price = "13850 ks"

PAYMENT_NAME = "Khaing Myo Zaw"
KPAY_NO = "098 951 23061"
AYA_NO = "098 951 23061"
WAVE_NO = "098 951 23061"

VPN_PLANS = {
    "plan_1": {
        "label": f"1 device = {plan_1_price}",
        "name": "Basic Plan",
        "device": "1 device",
        "ip_limit": 1,          # IP limit for Basic
        "price": plan_1_price,
        "days": 30,             # 1 month
        "traffic_gb": 0,        # 0 = unlimited
    },
    "plan_2": {
        "label": f"2 devices = {plan_2_price}",
        "name": "Silver Plan",
        "device": "2 devices",
        "ip_limit": 2,          # IP limit for Silver
        "price": plan_2_price,
        "days": 30,             # 1 month
        "traffic_gb": 0,
    },
    "plan_3": {
        "label": f"3 devices = {plan_3_price}",
        "name": "Golden Plan",
        "device": "3 devices",
        "ip_limit": 3,          # IP limit for Golden
        "price": plan_3_price,
        "days": 30,             # 1 month
        "traffic_gb": 0,
    },
}

# ==========================
# VALIDATE CONFIG
# ==========================
if BOT_TOKEN == "123456789:ABCdefGHIjklMNOpqrsTUVwxyz" or "your_" in API_HASH:
    print("=" * 60)
    print("ERROR: Configure your Telegram credentials!")
    print("=" * 60)
    sys.exit(1)

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
    "zembi_bot",
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
    {"name": "V2RayNG", "platform": "Android", "url": "https://play.google.com/store/apps/details?id=com.v2ray.ang"},
    {"name": "Hiddify", "platform": "Android/iOS", "url": "https://hiddify.com"},
    {"name": "Streisand", "platform": "iOS", "url": "https://apps.apple.com/app/streisand"},
    {"name": "V2RayN", "platform": "Windows", "url": "https://github.com/2dust/v2rayN"},
    {"name": "Qv2ray", "platform": "Linux/Mac", "url": "https://github.com/Qv2ray/Qv2ray"},
]


# ==========================
# 3X-UI API CLASS
# ==========================
class XUIClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.session = None
        self.logged_in = False
    
    async def login(self) -> bool:
        try:
            client = httpx.AsyncClient(
                timeout=30.0,
                verify=False,
                follow_redirects=True,
            )
            
            login_url = f"{self.base_url}/login"
            logger.info(f"Attempting login to: {login_url}")
            
            response = await client.post(
                login_url,
                data={"username": self.username, "password": self.password},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            logger.info(f"Login response: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    self.session = httpx.AsyncClient(
                        timeout=30.0,
                        verify=False,
                        cookies=response.cookies,
                        follow_redirects=True,
                    )
                    self.logged_in = True
                    logger.info("Successfully logged into 3X-UI panel")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Login error: {e}")
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
        uuid_str: str = None,
        traffic_limit_gb: int = 0,
        expiry_days: int = 30,
        ip_limit: int = 1,
    ) -> dict | None:
        """
        Add a new client to an inbound.
        
        Args:
            inbound_id: The inbound ID to add client to
            email: Client email/identifier (used for remark)
            tg_username: Telegram username to set on the key
            uuid_str: Optional UUID, auto-generated if not provided
            traffic_limit_gb: Traffic limit in GB (0 = unlimited)
            expiry_days: Number of days until expiry
            ip_limit: Maximum concurrent IPs/devices
        """
        try:
            if not self.logged_in:
                if not await self.login():
                    return None
            
            inbound = await self.get_inbound(inbound_id)
            if not inbound:
                logger.error(f"Inbound {inbound_id} not found")
                return None
            
            client_uuid = uuid_str or str(uuid.uuid4())
            expiry_time = int((datetime.now() + timedelta(days=expiry_days)).timestamp() * 1000)
            traffic_limit = traffic_limit_gb * 1024 * 1024 * 1024 if traffic_limit_gb > 0 else 0
            
            # Use telegram username as the client remark/email
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
            
            data = {
                "id": inbound_id,
                "settings": json.dumps({"clients": [client_settings]})
            }
            
            api_url = f"{self.base_url}/panel/api/inbounds/addClient"
            response = await self.session.post(api_url, data=data)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    # Generate VLESS key
                    vless_key = self._generate_vless_key(inbound, client_uuid, client_email)
                    
                    # Generate subscription link
                    sub_link = self._generate_sub_link(client_email)
                    
                    return {
                        "uuid": client_uuid,
                        "email": client_email,
                        "expiry": datetime.now() + timedelta(days=expiry_days),
                        "traffic_limit_gb": traffic_limit_gb,
                        "ip_limit": ip_limit,
                        "vless_key": vless_key,
                        "sub_link": sub_link,
                    }
            
            return None
        except Exception as e:
            logger.error(f"Error adding client: {e}")
            return None
    
    def _generate_sub_link(self, client_email: str) -> str:
        """Generate subscription link for the client."""
        # 3X-UI subscription URL format
        # Usually: https://SERVER:PORT/sub/CLIENT_EMAIL
        sub_url = f"https://{SERVER_IP}:{SUB_PORT}/sub/{urllib.parse.quote(client_email)}"
        return sub_url
    
    def _generate_vless_key(self, inbound: dict, client_uuid: str, remark: str) -> str:
        """Generate VLESS connection string."""
        try:
            stream_settings = json.loads(inbound.get("streamSettings", "{}"))
            port = inbound.get("port", SERVER_PORT)
            server = SERVER_IP
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
                if reality_settings.get("fingerprint"):
                    params.append(f"fp={reality_settings['fingerprint']}")
            else:
                params.append("security=none")
            
            if network == "ws":
                ws_settings = stream_settings.get("wsSettings", {})
                if ws_settings.get("path"):
                    params.append(f"path={urllib.parse.quote(ws_settings['path'])}")
                if ws_settings.get("headers", {}).get("Host"):
                    params.append(f"host={ws_settings['headers']['Host']}")
            elif network == "grpc":
                grpc_settings = stream_settings.get("grpcSettings", {})
                if grpc_settings.get("serviceName"):
                    params.append(f"serviceName={grpc_settings['serviceName']}")
            
            params.append("encryption=none")
            query_string = "&".join(params)
            
            # URL encode the remark
            encoded_remark = urllib.parse.quote(remark)
            vless_key = f"vless://{client_uuid}@{server}:{port}?{query_string}#{encoded_remark}"
            
            return vless_key
        except Exception as e:
            logger.error(f"Error generating VLESS key: {e}")
            return f"vless://{client_uuid}@{server}:{port}?security=none&type=tcp#{remark}"


# Initialize 3X-UI client
xui = XUIClient(PANEL_URL, PANEL_USERNAME, PANEL_PASSWORD)


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
            
            text = (
                f"{frames[frame_idx]} **Admin စစ်ဆေးနေပါတယ်...**\n\n"
                f"💳 Payment ID: `{payment_id[:8]}`\n"
                f"📦 Plan: {payment['plan_name']}\n"
                f"⏱ စောင့်ဆိုင်းချိန်: {mins}:{secs:02d}\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "📸 Screenshot ကို Admin ဆီပို့ပြီးပါပြီ။\n"
                "✅ Approve ဖြစ်ရင် VPN key ပို့ပေးပါမယ်။\n"
                "❌ Reject ဖြစ်ရင် အကြောင်းကြားပါမယ်။"
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
        except Exception as e:
            logger.error(f"Animation error: {e}")
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
            InlineKeyboardButton("💰 View Prices", callback_data="view_prices"),
            InlineKeyboardButton("📲 VPN Apps", callback_data="vpn_apps"),
        ],
        [
            InlineKeyboardButton("🆘 Contact Support", url=f"https://t.me/{ADMIN_USERNAME}"),
        ],
    ])


def get_username(user) -> str:
    """Get telegram username or generate one from user info."""
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
        "ကျနော် **Zembi** ပါ။ ✌🏻\n\n"
        "🔑 VLESS VPN key တွေကို\n"
        "စျေးနှုန်း ချိုချိုသာသာနဲ့ ရောင်းပေးနေတာပါဗျ။\n\n"
        "**📋 Plans:**\n"
        "• Basic (1 device): 5000 ks\n"
        "• Silver (2 devices): 9450 ks\n"
        "• Golden (3 devices): 13850 ks\n\n"
        "🌏 Server: Singapore 🇸🇬\n"
        "⚡ Speed: High-Speed\n"
        "📊 Data: Unlimited\n"
        "⏰ Validity: 30 Days\n\n"
        "အောက်က menu မှ ရွေးချယ်ပါ:"
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

    # ========== FREE TRIAL ==========
    if data == "free_trial":
        if user_trials.get(user_id, {}).get("used"):
            await query.message.reply_text(
                "❌ **Free Trial ယူပြီးသားဖြစ်ပါတယ်။**\n\n"
                "Plan ဝယ်ယူဖို့ View Prices ကိုနှိပ်ပါ။",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 View Prices", callback_data="view_prices")],
                    [InlineKeyboardButton("⬅️ Back", callback_data="back_menu")],
                ])
            )
            return
        
        loading_msg = await query.message.reply_text("⏳ Trial key ထုတ်ပေးနေပါတယ်...")
        
        tg_username = get_username(user)
        email = f"trial_{tg_username}"
        
        result = await xui.add_client(
            inbound_id=TRIAL_INBOUND_ID,
            email=email,
            tg_username=tg_username,
            traffic_limit_gb=TRIAL_TRAFFIC_GB,
            expiry_days=TRIAL_DURATION_HOURS / 24,
            ip_limit=TRIAL_DEVICE_LIMIT,
        )
        
        if result:
            user_trials[user_id] = {
                "used": True,
                "key": result["vless_key"],
                "sub_link": result["sub_link"],
                "expires": result["expiry"]
            }
            
            expiry = result["expiry"].strftime("%Y-%m-%d %H:%M")
            
            await loading_msg.edit_text(
                "🎁 **Free Trial Activated!**\n\n"
                f"👤 User: @{tg_username}\n"
                f"📱 Device Limit: {TRIAL_DEVICE_LIMIT}\n"
                f"📊 Traffic: {TRIAL_TRAFFIC_GB} GB\n"
                f"⏰ Duration: {TRIAL_DURATION_HOURS} Hours\n"
                f"📅 Expires: {expiry}\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "🔑 **VLESS Key:**\n"
                f"`{result['vless_key']}`\n\n"
                "_(Tap to copy)_\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "💡 **အသုံးပြုနည်း:**\n"
                "1. VPN App ဒေါင်းလုပ်ပါ\n"
                "2. VLESS Key သို့မဟုတ် Sub Link ကူးပါ\n"
                "3. App မှာ Import/Add လုပ်ပါ\n"
                "4. Connect နှိပ်ပြီး သုံးပါ! 🚀",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📱 Open Subscription Link", url=result['sub_link'])],
                    [InlineKeyboardButton("📲 VPN Apps", callback_data="vpn_apps")],
                    [InlineKeyboardButton("💰 Upgrade Plan", callback_data="view_prices")],
                    [InlineKeyboardButton("⬅️ Menu", callback_data="back_menu")],
                ])
            )
            
            if user_id not in user_subscriptions:
                user_subscriptions[user_id] = []
            user_subscriptions[user_id].append({
                "plan": "Free Trial",
                "status": "active",
                "expires": expiry,
                "key": result["vless_key"],
                "sub_link": result["sub_link"],
                "ip_limit": TRIAL_DEVICE_LIMIT,
            })
        else:
            await loading_msg.edit_text(
                "❌ **Error ဖြစ်သွားပါတယ်။**\n"
                "Admin ကို ဆက်သွယ်ပါ။",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🆘 Support", url=f"https://t.me/{ADMIN_USERNAME}")],
                ])
            )

    # ========== MY SUBSCRIPTIONS ==========
    elif data == "my_subs":
        subs = user_subscriptions.get(user_id, [])
        if subs:
            # Show summary first
            text = "📋 **Your Subscriptions:**\n\n"
            buttons = []
            
            for i, sub in enumerate(subs, 1):
                status_emoji = "✅" if sub.get("status") == "active" else "❌"
                text += (
                    f"**{i}. {sub['plan']}** {status_emoji}\n"
                    f"   📅 Expires: {sub['expires']}\n"
                    f"   📱 IP Limit: {sub.get('ip_limit', 1)} device(s)\n\n"
                )
                # Add button to view full key details
                buttons.append([InlineKeyboardButton(
                    f"🔑 View Key #{i} - {sub['plan']}", 
                    callback_data=f"view_key_{i-1}"
                )])
            
            buttons.append([InlineKeyboardButton("💰 Buy New Plan", callback_data="view_prices")])
            buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="back_menu")])
            
            await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        else:
            text = "📋 **Subscription မရှိသေးပါ။**\n\n🎁 Free Trial စမ်းကြည့်ပါ!"
            await query.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎁 Free Trial", callback_data="free_trial")],
                    [InlineKeyboardButton("💰 View Prices", callback_data="view_prices")],
                    [InlineKeyboardButton("⬅️ Back", callback_data="back_menu")],
                ])
            )

    # ========== VIEW KEY DETAILS ==========
    elif data.startswith("view_key_"):
        key_idx = int(data.replace("view_key_", ""))
        subs = user_subscriptions.get(user_id, [])
        
        if key_idx < len(subs):
            sub = subs[key_idx]
            status_emoji = "✅" if sub.get("status") == "active" else "❌"
            
            text = (
                f"🔑 **{sub['plan']}** {status_emoji}\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📅 Expires: {sub['expires']}\n"
                f"📱 IP Limit: {sub.get('ip_limit', 1)} device(s)\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "🔑 **VLESS Key (Tap to copy):**\n"
                f"`{sub.get('key', 'N/A')}`\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "📱 **Subscription Link (Tap to copy):**\n"
                f"`{sub.get('sub_link', 'N/A')}`\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "💡 Key ကို copy လုပ်ပြီး VPN App မှာ paste လုပ်ပါ။\n"
                "သို့မဟုတ် Subscription Link ကို import လုပ်ပါ။"
            )
            
            buttons = []
            if sub.get('sub_link'):
                buttons.append([InlineKeyboardButton("📱 Open Subscription Link", url=sub['sub_link'])])
            buttons.append([InlineKeyboardButton("📲 VPN Apps", callback_data="vpn_apps")])
            buttons.append([InlineKeyboardButton("⬅️ Back to Subscriptions", callback_data="my_subs")])
            buttons.append([InlineKeyboardButton("🏠 Menu", callback_data="back_menu")])
            
            await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await query.message.reply_text(
                "❌ Subscription not found.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data="my_subs")],
                ])
            )

    # ========== VIEW PRICES ==========
    elif data == "view_prices":
        await query.message.reply_text(
            "💰 **VPN Plans & Pricing**\n\n"
            "**Plan အားလုံးပါဝင်သည်:**\n"
            "✅ Unlimited Data\n"
            "✅ 30 Days Validity\n"
            "✅ Singapore Server 🇸🇬\n"
            "✅ High-Speed Connection\n"
            "✅ Subscription Link\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🥉 **Basic Plan** - 5000 ks\n"
            "   └ IP Limit: 1 device\n\n"
            "🥈 **Silver Plan** - 9450 ks\n"
            "   └ IP Limit: 2 devices\n\n"
            "🥇 **Golden Plan** - 13850 ks\n"
            "   └ IP Limit: 3 devices\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Plan ရွေးချယ်ပါ:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🥉 Basic (1 device) - {plan_1_price}", callback_data="buy_plan_1")],
                [InlineKeyboardButton(f"🥈 Silver (2 devices) - {plan_2_price}", callback_data="buy_plan_2")],
                [InlineKeyboardButton(f"🥇 Golden (3 devices) - {plan_3_price}", callback_data="buy_plan_3")],
                [InlineKeyboardButton("⬅️ Back", callback_data="back_menu")],
            ])
        )

    # ========== BUY PLAN ==========
    elif data.startswith("buy_plan_"):
        plan_key = data.replace("buy_", "")
        plan = VPN_PLANS.get(plan_key)
        
        if not plan:
            return
        
        user_states[user_id] = {
            "state": "waiting_screenshot",
            "plan_key": plan_key,
            "plan": plan
        }
        
        text = (
            f"✅ **{plan['name']}**\n\n"
            f"📱 IP Limit: {plan['ip_limit']} device(s)\n"
            f"📊 Data: Unlimited\n"
            f"⏰ Validity: {plan['days']} days\n"
            f"💵 Price: **{plan['price']}**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "**💳 ငွေလွှဲရန်:**\n\n"
            f"💰 **K Pay**\n"
            f"   👤 {PAYMENT_NAME}\n"
            f"   📞 `{KPAY_NO}`\n\n"
            f"💰 **AYA Pay**\n"
            f"   👤 {PAYMENT_NAME}\n"
            f"   📞 `{AYA_NO}`\n\n"
            f"💰 **Wave Pay**\n"
            f"   👤 {PAYMENT_NAME}\n"
            f"   📞 `{WAVE_NO}`\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📸 **ငွေလွှဲပြီးရင် screenshot ပို့ပေးပါ။**\n\n"
            "⚠️ **Note မှာ VPN မရေးပါနဲ့!**"
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
        await query.message.reply_text(
            "❌ **ပယ်ဖျက်လိုက်ပါပြီ။**",
            reply_markup=get_main_menu_keyboard()
        )

    # ========== VPN APPS ==========
    elif data == "vpn_apps":
        text = "📲 **VPN Apps**\n\n"
        buttons = []
        for app in VPN_APPS:
            text += f"• **{app['name']}** - {app['platform']}\n"
            buttons.append([InlineKeyboardButton(f"📥 {app['name']}", url=app["url"])])
        
        text += (
            "\n**အသုံးပြုနည်း:**\n"
            "1️⃣ App တစ်ခုဒေါင်းပါ\n"
            "2️⃣ VLESS Key/Sub Link ကူးပါ\n"
            "3️⃣ App → Import → Paste\n"
            "4️⃣ Connect! 🚀"
        )
        
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
        
        # Stop animation
        if payment_id in waiting_tasks:
            waiting_tasks[payment_id].cancel()
            del waiting_tasks[payment_id]
        
        pending_payments[payment_id]["status"] = "approved"
        
        # Generate VPN key with telegram username and plan-based IP limit
        plan = payment["plan"]
        buyer_user_id = payment["user_id"]
        tg_username = payment["username"]
        
        result = await xui.add_client(
            inbound_id=PAID_INBOUND_ID,
            email=f"{tg_username}_{plan['name'].replace(' ', '_')}",
            tg_username=tg_username,
            traffic_limit_gb=plan["traffic_gb"],
            expiry_days=plan["days"],
            ip_limit=plan["ip_limit"],  # Plan-based IP limit
        )
        
        if result:
            # Store subscription
            if buyer_user_id not in user_subscriptions:
                user_subscriptions[buyer_user_id] = []
            
            user_subscriptions[buyer_user_id].append({
                "plan": plan["name"],
                "status": "active",
                "expires": result["expiry"].strftime("%Y-%m-%d %H:%M"),
                "key": result["vless_key"],
                "sub_link": result["sub_link"],
                "ip_limit": plan["ip_limit"],
            })
            
            # Notify user with key and subscription link BUTTON
            try:
                await client.send_message(
                    chat_id=buyer_user_id,
                    text=(
                        "🎉 **Payment Approved!**\n"
                        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"✅ **{plan['name']}** activated!\n\n"
                        f"👤 User: @{tg_username}\n"
                        f"📱 IP Limit: {plan['ip_limit']} device(s)\n"
                        f"📅 Duration: {plan['days']} days\n"
                        f"📊 Traffic: Unlimited\n"
                        f"⏰ Expires: {result['expiry'].strftime('%Y-%m-%d %H:%M')}\n\n"
                        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        "🔑 **VLESS Key (Tap to copy):**\n"
                        f"`{result['vless_key']}`\n\n"
                        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        "💡 Key ကို copy လုပ်ပြီး VPN App မှာ paste လုပ်ပါ။\n"
                        "သို့မဟုတ် အောက်က Subscription Link ကို နှိပ်ပြီး import လုပ်ပါ။\n\n"
                        "ကျေးဇူးတင်ပါတယ် 🙏"
                    ),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📱 Open Subscription Link", url=result['sub_link'])],
                        [InlineKeyboardButton("📋 My Subscriptions", callback_data="my_subs")],
                        [InlineKeyboardButton("📲 VPN Apps", callback_data="vpn_apps")],
                        [InlineKeyboardButton("🏠 Menu", callback_data="back_menu")],
                    ])
                )
            except Exception as e:
                logger.error(f"Failed to send to user: {e}")
            
            await query.message.edit_caption(
                caption=query.message.caption + f"\n\n✅ **APPROVED**\n🔑 Key sent to @{tg_username}",
                reply_markup=None
            )
        else:
            await client.send_message(
                chat_id=buyer_user_id,
                text="✅ Payment approved!\n⚠️ Key gen failed. Admin will send manually."
            )
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
                text=(
                    "❌ **Payment Rejected**\n\n"
                    "Screenshot verify မရပါ။\n"
                    "Admin ကို ဆက်သွယ်ပါ။"
                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🆘 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")],
                    [InlineKeyboardButton("🔄 Try Again", callback_data="view_prices")],
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
        await query.message.reply_text(
            "🔐 **Zembi VPN Bot**\n\nMenu:",
            reply_markup=get_main_menu_keyboard()
        )


# ==========================
# SCREENSHOT HANDLER
# ==========================
@app.on_message(filters.photo & filters.private)
async def screenshot_handler(client: Client, message: Message):
    user_id = message.from_user.id
    user = message.from_user
    
    if user_id not in user_states or user_states[user_id].get("state") != "waiting_screenshot":
        await message.reply_text(
            "❓ အရင်ဆုံး plan ရွေးပါ။",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 View Prices", callback_data="view_prices")],
            ])
        )
        return
    
    plan_key = user_states[user_id]["plan_key"]
    plan = user_states[user_id]["plan"]
    tg_username = get_username(user)
    
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
    
    waiting_msg = await message.reply_text(
        f"✅ **Screenshot လက်ခံရရှိပါပြီ!**\n\n"
        f"📦 Plan: {plan['name']}\n"
        f"📱 IP Limit: {plan['ip_limit']}\n\n"
        "⏳ Admin စစ်ဆေးနေပါတယ်..."
    )
    
    pending_payments[payment_id]["message_id"] = waiting_msg.id
    
    admin_text = (
        f"💳 **New Payment**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 User: {user.first_name}\n"
        f"📧 Username: @{tg_username}\n"
        f"🆔 ID: `{user_id}`\n\n"
        f"📦 Plan: **{plan['name']}**\n"
        f"💵 Price: {plan['price']}\n"
        f"📱 IP Limit: {plan['ip_limit']}\n"
        f"⏰ Validity: {plan['days']} days\n\n"
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
            "❌ Admin ဆီပို့မရပါ။ တိုက်ရိုက်ဆက်သွယ်ပါ။",
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
        f"/generate <user_id> <plan_key>\n"
        f"/broadcast <message>"
    )


@app.on_message(filters.command("generate") & filters.private)
async def admin_generate(client: Client, message: Message):
    if message.from_user.id != ADMIN_USER_ID:
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.reply_text(
            "Usage: /generate <user_id> <plan_key>\n"
            "Plans: plan_1, plan_2, plan_3"
        )
        return
    
    target_user = args[1]
    plan_key = args[2]
    
    if plan_key not in VPN_PLANS:
        await message.reply_text(f"❌ Invalid plan: {plan_key}")
        return
    
    plan = VPN_PLANS[plan_key]
    
    result = await xui.add_client(
        inbound_id=PAID_INBOUND_ID,
        email=f"manual_{target_user}",
        tg_username=f"user_{target_user}",
        traffic_limit_gb=plan["traffic_gb"],
        expiry_days=plan["days"],
        ip_limit=plan["ip_limit"],
    )
    
    if result:
        await message.reply_text(
            f"✅ **Key Generated!**\n\n"
            f"📦 Plan: {plan['name']}\n"
            f"📱 IP Limit: {plan['ip_limit']}\n"
            f"📅 Expires: {result['expiry'].strftime('%Y-%m-%d')}\n\n"
            f"🔑 **VLESS Key:**\n`{result['vless_key']}`\n\n"
            f"📱 **Sub Link:**\n`{result['sub_link']}`"
        )
    else:
        await message.reply_text("❌ Failed to generate key.")


# ==========================
# MAIN
# ==========================
if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Zembi VPN Bot")
    print("   Plan-based IP limits | 30 days validity")
    print("   Telegram username on keys | Subscription links")
    print("=" * 50)
    
    try:
        app.run()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
