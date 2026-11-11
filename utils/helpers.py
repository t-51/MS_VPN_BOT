"""توابع کمکی مشترک ربات MS_VPN_BOT."""
from typing import Optional, Any

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_fa(text: Any) -> str:
    """تبدیل ارقام لاتین به فارسی."""
    return str(text).translate(_FA_DIGITS)


def to_toman(amount: Any) -> str:
    """قالب‌بندی مبلغ به تومان با جداکننده‌ی هزارگان و ارقام فارسی."""
    try:
        n = int(amount)
    except (TypeError, ValueError):
        return str(amount)
    return to_fa(f"{n:,}") + " تومان"


def to_days(duration: Any) -> str:
    """تبدیل مدت (روز) به متن فارسی."""
    try:
        d = int(duration)
    except (TypeError, ValueError):
        return str(duration)
    if d % 30 == 0:
        months = d // 30
        return f"{to_fa(months)} ماه"
    return f"{to_fa(d)} روز"


def api_error_text(resp: dict) -> str:
    """استخراج پیام خطای کاربرپسند از پاسخ پنل MHPanel."""
    if not isinstance(resp, dict):
        return "❌ پاسخ نامعتبر از سرور MHPanel."

    err = resp.get("error")
    if err and isinstance(err, str):
        return f"❌ {err}"

    status = resp.get("status_code")
    if status == 401:
        return "⛔ کلید دسترسی به پنل نامعتبر است (Unauthorized API Key)."
    if status and int(status) >= 500:
        return "⚠️ سرور پنل در حال حاضر در دسترس نیست. لطفاً دقایقی دیگر تلاش کنید."
    return "❌ خطایی هنگام ارتباط با پنل MHPanel رخ داد."
