import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# بارگذاری متغیرها از فایل .env
load_dotenv(BASE_DIR / ".env")


class Settings:
    """تنظیمات سراسری ربات MS_VPN_BOT - متصل به پنل MHPanel."""

    # توکن ربات تلگرام
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

    # کلید اختصاصی API پنل MHPanel
    PANEL_API_KEY = os.getenv("PANEL_API_KEY", "")

    # آدرس پایه‌ی API پنل MHPanel
    PANEL_API_URL = os.getenv("PANEL_API_URL", "https://your-domain.com/api").rstrip("/")

    # آدرس سابسکریپشن عمومی پنل
    PANEL_SUB_URL = os.getenv("PANEL_SUB_URL", "https://your-domain.com/sub").rstrip("/")

    # دامنه و آی‌پی عمومی سرور
    SERVER_IP = os.getenv("SERVER_IP", "127.0.0.1")
    SERVER_DOMAIN = os.getenv("SERVER_DOMAIN", "your-domain.com")

    # کلید پیش‌فرض IPsec PSK برای پروتکل‌های L2TP/IPsec
    IPSEC_PSK = os.getenv("IPSEC_PSK", "123456789")

    # مشخصات تانل DNS (SlowDNS / DNSTT)
    DNSTT_DOMAIN = os.getenv("DNSTT_DOMAIN", "t.your-domain.com")
    DNSTT_PUBKEY = os.getenv("DNSTT_PUBKEY", "")

    # یوزرنیم ربات بدون @
    BOT_USERNAME = os.getenv("BOT_USERNAME", "YourBotUsername")

    # لیست شناسه‌های عددی ادمین‌های تلگرام
    raw_admins = f"{os.getenv('ADMIN_IDS', '')},{os.getenv('ADMIN_ID', '')}"
    ADMIN_IDS = list({int(x.strip()) for x in raw_admins.split(",") if x.strip().isdigit()})

    # مسیر دیتابیس محلی ربات
    DB_PATH = str(Path(os.getenv("DB_PATH", str(BASE_DIR / "data" / "bot.db"))).resolve())

    # زمان مهلت اتصال API (ثانیه)
    API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))

    # تنظیمات پیش‌فرض اکانت تستی
    TRIAL_TRAFFIC_GB = float(os.getenv("TRIAL_TRAFFIC_GB", "1.0"))
    TRIAL_DURATION_DAYS = int(os.getenv("TRIAL_DURATION_DAYS", "1"))

    # اطلاعات کارت بانکی جهت شارژ
    CARD_NUMBER = os.getenv("CARD_NUMBER", "6037990000000000")
    CARD_HOLDER = os.getenv("CARD_HOLDER", "مدیریت ربات")

    # پشتیبانی و کانال
    SUPPORT_ID = os.getenv("SUPPORT_ID", "@YourSupport")
    CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/YourChannel")

    # درصد پورسانت زیرمجموعه‌گیری
    REFERRAL_PERCENT = int(os.getenv("REFERRAL_PERCENT", "10"))

    DYNAMIC_ADMINS = set()

    def is_admin(self, user_id: int) -> bool:
        """بررسی اینکه آیا کاربر مدیر ربات است یا خیر."""
        return user_id in self.ADMIN_IDS or user_id in self.DYNAMIC_ADMINS


# یک نمونه‌ی سراسری برای استفاده در کل برنامه
settings = Settings()
settings.DYNAMIC_ADMINS = set(settings.ADMIN_IDS)
