"""توابع کمکی مشترک ربات MS_VPN_BOT."""
import re
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


def duration_label(days: Any) -> str:
    """برچسب خوانا برای مدت زمان پلن (مثلاً ۱ ماهه، ۲ ماهه، ۳ ماهه)."""
    try:
        d = int(days)
    except (TypeError, ValueError):
        return f"{days} روز"
    if d == 30:
        return "۱ ماهه (۳۰ روز)"
    elif d == 60:
        return "۲ ماهه (۶۰ روز)"
    elif d == 90:
        return "۳ ماهه (۹۰ روز)"
    elif d % 30 == 0:
        return f"{to_fa(d // 30)} ماهه ({to_fa(d)} روز)"
    return f"{to_fa(d)} روزه"


def calculate_account_refund(
    account: dict,
    live_data: Optional[dict] = None,
    plan_price: int = 0,
) -> tuple:
    """محاسبه میزان مصرف ترافیک و زمان و مبلغ باقیمانده جهت عودت به کیف پول کاربر."""
    from datetime import datetime

    if account.get("is_trial"):
        return 0, {
            "price": 0, "used_gb": 0.0, "total_gb": 0.0, "remaining_gb": 0.0,
            "used_days": 0.0, "total_days": 0, "remaining_days": 0, "refund_ratio": 0.0
        }

    price = account.get("price") or 0
    if not price and plan_price:
        price = plan_price
    if price <= 0:
        return 0, {
            "price": 0, "used_gb": 0.0, "total_gb": account.get("traffic_gb", 0.0),
            "remaining_gb": account.get("traffic_gb", 0.0), "used_days": 0.0,
            "total_days": account.get("duration_days", 0), "remaining_days": account.get("duration_days", 0),
            "refund_ratio": 0.0
        }

    total_gb = float(account.get("traffic_gb") or 0.0)
    total_days = int(account.get("duration_days") or 30)

    used_gb = 0.0
    if live_data and live_data.get("success"):
        u = live_data.get("user", {})
        used_bytes = u.get("used_traffic")
        if used_bytes is None:
            used_bytes = (u.get("rx") or 0) + (u.get("tx") or 0)
        if used_bytes:
            used_gb = round(used_bytes / (1024 ** 3), 2)
        elif u.get("traffic_percent"):
            used_gb = round(total_gb * (u.get("traffic_percent") / 100.0), 2)

    created_at_str = account.get("created_at")
    used_days = 0.0
    if created_at_str:
        try:
            dt_created = datetime.strptime(str(created_at_str)[:19], "%Y-%m-%d %H:%M:%S")
            diff_sec = (datetime.now() - dt_created).total_seconds()
            used_days = max(0.0, round(diff_sec / 86400.0, 1))
        except Exception:
            used_days = 0.0

    remaining_days = max(0.0, round(total_days - used_days, 1))
    time_ratio = max(0.0, min(1.0, (total_days - used_days) / total_days)) if total_days > 0 else 0.0

    if total_gb > 0:
        remaining_gb = max(0.0, round(total_gb - used_gb, 2))
        traffic_ratio = max(0.0, min(1.0, (total_gb - used_gb) / total_gb))
        final_ratio = min(time_ratio, traffic_ratio)
    else:
        remaining_gb = 0.0
        final_ratio = time_ratio

    if final_ratio <= 0.01:
        refund_amount = 0
    else:
        refund_amount = int(price * final_ratio)
        refund_amount = (refund_amount // 500) * 500
        refund_amount = max(0, min(price, refund_amount))

    breakdown = {
        "price": price,
        "used_gb": used_gb,
        "total_gb": total_gb,
        "remaining_gb": remaining_gb if total_gb > 0 else 0.0,
        "used_days": used_days,
        "total_days": total_days,
        "remaining_days": remaining_days,
        "refund_ratio": final_ratio,
    }
    return refund_amount, breakdown


def make_qr_code_file(data: str, filename: str = "qrcode.png"):
    """تولید فایل تصویر بارکد QR استاندارد تلگرام از یک متن یا لینک سابسکریپشن."""
    import io
    import qrcode
    from aiogram.types import BufferedInputFile

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return BufferedInputFile(bio.getvalue(), filename=filename)


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


def format_bytes(num_bytes: Any) -> str:
    """تبدیل بایت به قالب خوانای فارسی و انگلیسی (KB, MB, GB)."""
    try:
        n = float(num_bytes or 0)
    except (ValueError, TypeError):
        return "۰ بایت"
    if n < 1024:
        return f"{to_fa(int(n))} بایت"
    elif n < 1024 ** 2:
        return f"{to_fa(round(n / 1024, 1))} KB"
    elif n < 1024 ** 3:
        return f"{to_fa(round(n / (1024 ** 2), 2))} MB"
    else:
        return f"{to_fa(round(n / (1024 ** 3), 2))} GB"


def make_clean_wg_filename(base_name: str, port: Optional[int] = None) -> str:
    """
    تولید نام فایل معتبر و استاندارد برای کلاینت رسمی وایرگارد (حداکثر ۱۵ نویسه بدون .conf):
    طبق استاندارد رسمی WireGuard در لینوکس، اندروید و iOS، نام تانل از روی نام فایل تعیین می‌شود
    و باید دقیقاً شامل [a-zA-Z0-9_] و حداکثر ۱۵ نویسه باشد تا خطای Invalid tunnel name ندهد.
    """
    clean = re.sub(r'[^a-zA-Z0-9_]', '', str(base_name or "wg"))
    if not clean or clean[0].isdigit():
        clean = f"wg_{clean}"

    if port:
        suffix = f"_{port}"
        max_base = 15 - len(suffix)
        base = clean[:max_base].rstrip('_')
        tunnel_name = f"{base}{suffix}"
    else:
        tunnel_name = clean[:15].rstrip('_')

    if len(tunnel_name) < 2:
        tunnel_name = f"wg_{tunnel_name}"
    return f"{tunnel_name[:15]}.conf"


def sanitize_wireguard_conf(conf_text: str, domain: Optional[str] = None, port: Optional[int] = None) -> str:
    """
    پاکسازی و استانداردسازی کامل متن کانفیگ وایرگارد:
    - حذف فضاهای خالی و فاصله‌های اضافی در ابتدا و انتهای هر خط (به ویژه قبل از [Interface] و [Peer])
    - اطمینان از تنظیم استاندارد MTU = 1280 جهت جلوگیری از افت بسته در اینترنت موبایل
    - اطمینان از PersistentKeepalive = 25 جهت پایداری اتصال
    - جایگزینی و تنظیم تمیز فیلد Endpoint در صورت تغییر پورت یا دامین
    - جداسازی تمیز بخش‌ها با یک خط استاندارد
    """
    if not conf_text:
        return ""

    lines = conf_text.splitlines()
    cleaned_lines = []
    for l in lines:
        s = l.strip()
        if not s:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue
        cleaned_lines.append(s)

    text = "\n".join(cleaned_lines).strip()

    if not text.startswith("[Interface]") and "[Interface]" in text:
        text = text[text.index("[Interface]"):]

    if port:
        if domain:
            text = re.sub(r'^\s*Endpoint\s*=.*$', f'Endpoint = {domain}:{port}', text, flags=re.MULTILINE)
        else:
            text = re.sub(r'^\s*Endpoint\s*=\s*([^:]+):\d+', rf'Endpoint = \1:{port}', text, flags=re.MULTILINE)

    if re.search(r'^\s*MTU\s*=', text, flags=re.MULTILINE):
        text = re.sub(r'^\s*MTU\s*=\s*\d+', 'MTU = 1280', text, flags=re.MULTILINE)
    elif "[Interface]" in text:
        text = text.replace("[Interface]", "[Interface]\nMTU = 1280", 1)

    if re.search(r'^\s*PersistentKeepalive\s*=', text, flags=re.MULTILINE):
        text = re.sub(r'^\s*PersistentKeepalive\s*=\s*\d+', 'PersistentKeepalive = 25', text, flags=re.MULTILINE)
    elif "[Peer]" in text:
        text = text.replace("[Peer]", "[Peer]\nPersistentKeepalive = 25", 1)

    return text.strip() + "\n"
