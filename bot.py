import logging
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Message,
)

# ==========================
# CONFIG – FILL THESE IN
# ==========================
API_ID = 34721867                    # <- Your API ID from my.telegram.org (INTEGER!)
API_HASH = "c8ad7cce9bf5150a17182c54a8910951"      # <- Your API hash from my.telegram.org
BOT_TOKEN = "8220296600:AAEUzg_pIVRzp9-tgYAt5azygK6NtbCdltU"  # <- Your bot token from @BotFather

ADMIN_USER_ID = 2021841732            # <- Your Telegram user ID (send /id to @userinfobot)
ADMIN_USERNAME = "mr_zembi"       # <- Your admin username for support (without @)

# ==========================
# 3X-UI PANEL CONFIG
# ==========================
PANEL_URL = "http://18.143.40.158:1100/dashboard/"  # <- Your 3X-UI panel URL (include port)
PANEL_USERNAME = "zembi"                   # <- 3X-UI panel username
PANEL_PASSWORD = "wh0i$zembi"                   # <- 3X-UI panel password
TRIAL_INBOUND_ID = 5                       # <- Inbound ID for trial keys (check in panel)
PAID_INBOUND_ID = 5                        # <- Inbound ID for paid keys (optional, can use same)


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
    "mr_zembi_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# PLAN PRICES
plan_1 = "5000 ks"
plan_2 = "9450 ks"
plan_3 = "13850 ks"

common_name = "Khaing Myo Zaw"
kpay_no = "`098 951 23061`"
aya_no = "`098 951 23061`"
wave_no = "`098 951 23061`"

# ==========================
# PLAN DATA
# ==========================
VPN_PLANS = {
    "plan_1": {
        "label": f"1 device = {plan_1}",
        "name": "Basic plan",
        "device": '1 device',
        "price": plan_1,
    },
    "plan_2": {
        "label": f"2 devices = {plan_2}",
        "name": "Silver plan",
        "device": '2 devices',
        "price": plan_2,
    },
    "plan_3": {
        "label": f"3 devices = {plan_3}",
        "name": "Golden plan",
        "device": '3 devices',
        "price": plan_3,
    },
}


# ==========================
# HELPERS
# ==========================
async def process_plan_selection(message: Message, plan_key: str):
    """
    This function is the 'real' logic for each plan.
    Both /plan1 commands and inline buttons call this.
    """
    plan = VPN_PLANS[plan_key]
    text = (
        f"✅ {plan['name']}\n"
        f"Device limit: {plan['device']}\n"
        "Data transfer: unlimited\n"
        f"💲Price: {plan['price']}\n\n"
        "ဆက်လက် လုပ်ဆောင်ရန်\n"
        "အောက်ပါ account တစ်ခုခုကို\n"
        f"ကျသင့်ငွေအား ပေးချေပြီး screenshot လေးပို့ပေးပါဗျ။ \n\n"
        "💰 K Pay\n"
        f"{common_name}\n"
        f"📞 {kpay_no}\n\n"
        "💰 AYA Pay\n"
        f"{common_name}\n"
        f"📞 {aya_no}\n\n"
        "💰 Wave Pay\n"
        f"{common_name}\n"
        f"📞 {wave_no}\n\n\n"

        "⚠️ ကျေးဇူးပြု၍ note မှာ VPN နဲ့ ပတ်သတ်တဲ့ စာသားတွေ မရေးပါနဲ့ခင်ဗျာ။"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Kpay QR", callback_data="plan_1"),
                InlineKeyboardButton("AYA Pay QR", callback_data="plan_1"),
                InlineKeyboardButton("Wave Pay QR", callback_data="plan_1"),
            ],
        ]
    )

    await message.reply_text(text, reply_markup=keyboard)


# ==========================
# /start COMMAND
# ==========================
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    text = (
        "မင်္ဂလာပါ 🙏🏻 \n"
        "ကျနော် zembi ပါ။ ✌🏻 \n\n"
        "V2Ray, Hiddify နဲ့ တခြားသော\n" 
        "📱 vpn app အများစုမှာ အသုံးပြုနိုင်ပြီး လိုင်းဆွဲအား ကောင်းမွန်တဲ့\n" 
        "🔑 vless vpn key တွေကို စျေးနှုန်း ချိုချိုသာသာနဲ့ ရောင်းပေးနေတာပါဗျ။\n\n"
        "အောက်မှာပြထားတဲ့ နှစ်သက်ရာ plan လေးကို နှိပ်ပြီး အလွယ်တကူဝယ်ယူနိုင်ပါတယ်နော်။ \n\n"
        "Server: Singapore 🇸🇬 \n"
        "Speed: Fast  \n"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(VPN_PLANS["plan_1"]["label"], callback_data="plan_1"),InlineKeyboardButton(VPN_PLANS["plan_2"]["label"], callback_data="plan_2")
            ],
            [
                InlineKeyboardButton(VPN_PLANS["plan_3"]["label"], callback_data="plan_3"),
                InlineKeyboardButton(VPN_PLANS["plan_3"]["label"], callback_data="plan_3"),
            ],
        ]
    )

    await message.reply_text(text, reply_markup=keyboard)


# ==========================
# CALLBACK QUERY HANDLER
# (button clicks)
# ==========================
@app.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    data = query.data

    # Avoid 'loading...' spinner staying forever
    await query.answer()

    if data in VPN_PLANS:
        # User clicked on a plan button
        await process_plan_selection(query.message, data)


# ==========================
# OPTIONAL: TEXT COMMANDS
# (launch same logic as buttons)
# ==========================
@app.on_message(filters.command("plan1") & filters.private)
async def cmd_plan1(client: Client, message: Message):
    await process_plan_selection(message, "plan_1")


@app.on_message(filters.command("plan2") & filters.private)
async def cmd_plan2(client: Client, message: Message):
    await process_plan_selection(message, "plan_2")


@app.on_message(filters.command("plan3") & filters.private)
async def cmd_plan3(client: Client, message: Message):
    await process_plan_selection(message, "plan_3")


# ==========================
# MAIN
# ==========================
if __name__ == "__main__":
    logger.info("Starting Mr_zembi_bot…")
    app.run()