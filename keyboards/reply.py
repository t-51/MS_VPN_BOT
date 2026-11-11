"""کیبوردهای پایین‌صفحه (Reply) ربات MS_VPN_BOT."""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """ساخت منوی اصلی با پشتیبانی از دکمه مدیریت برای ادمین‌ها."""
    rows = [
        [KeyboardButton(text="🛒 خرید اشتراک"), KeyboardButton(text="🎁 اکانت تستی")],
        [KeyboardButton(text="📦 اکانت‌های من"), KeyboardButton(text="💰 کیف پول")],
        [KeyboardButton(text="📲 دانلود نرم‌افزارها"), KeyboardButton(text="❓ راهنمای اتصال")],
        [KeyboardButton(text="🤝 زیرمجموعه"), KeyboardButton(text="🎫 تیکت‌ها")],
        [KeyboardButton(text="🔔 اعلان‌ها"), KeyboardButton(text="👤 پروفایل")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="👑 پنل مدیریت")])

    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


# منوی اصلی پیش‌فرض
main_menu_keyboard = get_main_keyboard(False)

# دکمه‌ی لغو برای مراحل FSM
cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ لغو")]],
    resize_keyboard=True,
)
