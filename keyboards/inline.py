"""کیبوردهای شیشه‌ای (Inline) کاربر و پنل مدیریت MS_VPN_BOT."""
from typing import List, Any, Dict, Optional

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.formatters import plan_label
from utils.helpers import to_toman


# ── فروشگاه و دسته‌بندی‌ها (کاربر) ───────────────────────────

def build_shop_categories_keyboard(categories: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """دسته‌بندی‌های پویا از دیتابیس برای نمایش به کاربر."""
    kb = InlineKeyboardBuilder()
    for cat in categories:
        icon = cat.get("icon") or "⚡"
        title = cat.get("title", "دسته")
        kb.button(text=f"{icon} {title}", callback_data=f"shop:cat:{cat.get('key')}")
    kb.button(text="🔙 بازگشت به منوی اصلی", callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()


def build_plans_keyboard(plans: List[Dict[str, Any]], category_key: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for plan in plans:
        kb.button(
            text=plan_label(plan),
            callback_data=f"buy:plan:{plan.get('id')}",
        )
    kb.button(text="🔙 بازگشت به دسته‌بندی‌ها", callback_data="shop:categories")
    kb.adjust(1)
    return kb.as_markup()


def build_payment_methods_keyboard(plan_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💼 پرداخت از موجودی کیف پول", callback_data=f"buy:pay:{plan_id}:wallet")
    kb.button(text="💳 پرداخت مستقیم با کارت‌به‌کارت", callback_data=f"buy:pay:{plan_id}:card")
    kb.button(text="🔙 بازگشت به پلن‌ها", callback_data="shop:categories")
    kb.adjust(1)
    return kb.as_markup()


# ── اکانت‌های من ─────────────────────────────────────────────

def build_accounts_keyboard(accounts: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    cat_icons = {"singbox": "🚀", "v2ray": "⚡", "system_l2tp": "🛡️", "dnstt": "🌐", "reality": "🕶️"}
    for acc in accounts:
        cat = acc.get("category", "singbox")
        icon = cat_icons.get(cat, "📦")
        plan = acc.get("plan_name", "اشتراک")
        acc_type = "🎁 تستی" if acc.get("is_trial") else icon
        kb.button(
            text=f"{acc_type} {plan} ({acc.get('panel_username')})",
            callback_data=f"acc:view:{acc.get('id')}",
        )
    kb.button(text="🔙 بازگشت به منو", callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()


def account_details_keyboard(account_id: int, category: str = "singbox", sub_url: str = "") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if category in ["singbox", "v2ray", "reality"]:
        if sub_url:
            kb.button(text="🌐 مشاهده صفحه ساب در مرورگر", url=sub_url)
        kb.button(text="⚡ دریافت کانفیگ‌های تکی", callback_data=f"acc:configs:{account_id}")
        kb.button(text="🔄 تغییر شناسه اتصال (UUID)", callback_data=f"acc:reset_id_ask:{account_id}")
        kb.button(text="🔁 تبدیل این اکانت به پروتکل دیگر", callback_data=f"acc:convert_ask:{account_id}")
        kb.button(text="🔄 بروزرسانی وضعیت", callback_data=f"acc:view:{account_id}")
        kb.button(text="🔙 بازگشت به لیست اکانت‌ها", callback_data="acc:list")
        kb.adjust(1, 1, 1, 1, 1, 1)
    elif category == "wireguard":
        kb.button(text="📥 دانلود فایل کانفیگ (.conf)", callback_data=f"acc:dl_wg_conf:{account_id}")
        kb.button(text="📷 دریافت بارکد QR", callback_data=f"acc:dl_wg_qr:{account_id}")
        kb.button(text="📋 مشاهده متن کانفیگ", callback_data=f"acc:view_wg_text:{account_id}")
        kb.button(text="⚡ آموزش اتصال وایرگارد", callback_data="tut:view:wireguard")
        kb.button(text="🔄 بازسازی و تغییر کلیدها", callback_data=f"acc:reset_id_ask:{account_id}")
        kb.button(text="🔁 تبدیل این اکانت به پروتکل دیگر", callback_data=f"acc:convert_ask:{account_id}")
        kb.button(text="🔄 بروزرسانی وضعیت", callback_data=f"acc:view:{account_id}")
        kb.button(text="🔙 بازگشت به لیست اکانت‌ها", callback_data="acc:list")
        kb.adjust(2, 1, 1, 1, 1, 1, 1)
    elif category == "gas":
        kb.button(text="🌐 جزئیات و کلید اتصال وب‌اپ", callback_data=f"acc:gas_info:{account_id}")
        kb.button(text="📖 راهنمای اتصال و آموزش GAS", callback_data="tut:view:gas")
        kb.button(text="🔄 تغییر رمز اختصاصی", callback_data=f"acc:reset_id_ask:{account_id}")
        kb.button(text="🔁 تبدیل این اکانت به پروتکل دیگر", callback_data=f"acc:convert_ask:{account_id}")
        kb.button(text="🔄 بروزرسانی وضعیت", callback_data=f"acc:view:{account_id}")
        kb.button(text="🔙 بازگشت به لیست اکانت‌ها", callback_data="acc:list")
        kb.adjust(1, 1, 1, 1, 1, 1)
    elif category == "system_l2tp":
        kb.button(text="📥 دانلود فایل OpenVPN (.ovpn)", callback_data=f"acc:dl_ovpn:{account_id}")
        kb.button(text="📱 کانفیگ‌های SlipNet (DNS / SSH / Tor)", callback_data=f"acc:slipnet_list:{account_id}")
        kb.button(text="📜 سرتیفیکیت Cisco", callback_data=f"acc:dl_cert:{account_id}:cisco")
        kb.button(text="📜 سرتیفیکیت IKEv2", callback_data=f"acc:dl_cert:{account_id}:ikev2")
        kb.button(text="📜 سرتیفیکیت SSTP", callback_data=f"acc:dl_cert:{account_id}:sstp")
        kb.button(text="📚 آموزش اتصال به سیسکو و OpenVPN", callback_data="tut:view:cisco")
        kb.button(text="🔄 تغییر رمز عبور اکانت", callback_data=f"acc:reset_id_ask:{account_id}")
        kb.button(text="🔁 تبدیل این اکانت به پروتکل دیگر", callback_data=f"acc:convert_ask:{account_id}")
        kb.button(text="🔄 بروزرسانی وضعیت", callback_data=f"acc:view:{account_id}")
        kb.button(text="🔙 بازگشت به لیست اکانت‌ها", callback_data="acc:list")
        kb.adjust(1, 1, 3, 1, 1, 1, 1, 1)
    elif category == "dnstt":
        kb.button(text="📱 کانفیگ‌های SlipNet (DNS / SSH / Tor)", callback_data=f"acc:slipnet_list:{account_id}")
        kb.button(text="📋 نمایش متنی تمام کانفیگ‌ها در چت", callback_data=f"acc:slp_text_all:{account_id}")
        kb.button(text="📥 دانلود تمام کانفیگ‌ها (.txt)", callback_data=f"acc:slp_dl_all:{account_id}")
        kb.button(text="📷 دریافت بارکد QR تانل", callback_data=f"acc:slp_qr:{account_id}")
        kb.button(text="🔄 تغییر رمز عبور اکانت", callback_data=f"acc:reset_id_ask:{account_id}")
        kb.button(text="🔁 تبدیل این اکانت به پروتکل دیگر", callback_data=f"acc:convert_ask:{account_id}")
        kb.button(text="🔄 بروزرسانی وضعیت", callback_data=f"acc:view:{account_id}")
        kb.button(text="🔙 بازگشت به لیست اکانت‌ها", callback_data="acc:list")
        kb.adjust(1, 1, 2, 1, 1, 1, 1)
    else:
        kb.button(text="🔄 تغییر شناسه / رمز عبور", callback_data=f"acc:reset_id_ask:{account_id}")
        kb.button(text="🔁 تبدیل این اکانت به پروتکل دیگر", callback_data=f"acc:convert_ask:{account_id}")
        kb.button(text="🔄 بروزرسانی وضعیت", callback_data=f"acc:view:{account_id}")
        kb.button(text="🔙 بازگشت به لیست اکانت‌ها", callback_data="acc:list")
        kb.adjust(1, 1, 1, 1)
    return kb.as_markup()


def account_reset_confirm_keyboard(account_id: int) -> InlineKeyboardMarkup:
    """کیبورد تأیید بازنشانی و تغییر شناسه / رمز اکانت."""
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ بله، شناسه / رمز جدید بساز", callback_data=f"acc:reset_id_do:{account_id}")
    kb.button(text="❌ انصراف", callback_data=f"acc:view:{account_id}")
    kb.adjust(1)
    return kb.as_markup()


def slipnet_protocols_keyboard(account_id: int) -> InlineKeyboardMarkup:
    """کیبورد تفکیک‌شده تانل‌های DNS و SlipNet و Tor."""
    kb = InlineKeyboardBuilder()
    kb.button(text="📋 نمایش متنی تمام کانفیگ‌ها در چت", callback_data=f"acc:slp_text_all:{account_id}")
    kb.button(text="📷 دریافت بارکد QR کانفیگ اصلی", callback_data=f"acc:slp_qr:{account_id}")
    kb.button(text="📥 دانلود همه در یک فایل متنی (.txt)", callback_data=f"acc:slp_dl_all:{account_id}")
    kb.button(text="🛡️ کانفیگ VayDNS", callback_data=f"acc:slp_v:{account_id}:vaydns")
    kb.button(text="🌐 کانفیگ DNSTT (SlowDNS)", callback_data=f"acc:slp_v:{account_id}:dnstt")
    kb.button(text="🚀 کانفیگ Slipstream (QUIC)", callback_data=f"acc:slp_v:{account_id}:slipstream")
    kb.button(text="⚡ کانفیگ MasterDNS", callback_data=f"acc:slp_v:{account_id}:masterdnsvpn")
    kb.button(text="🔒 کانفیگ NoizDNS (SayeDNS)", callback_data=f"acc:slp_v:{account_id}:noizdns")
    kb.button(text="🌐 کانفیگ DoH-DNSTT", callback_data=f"acc:slp_v:{account_id}:doh")
    kb.button(text="🧅 کانفیگ پل Tor (obfs4)", callback_data=f"acc:slp_v:{account_id}:tor")
    kb.button(text="🔙 بازگشت به مشخصات اکانت", callback_data=f"acc:view:{account_id}")
    kb.adjust(1, 2, 2, 2, 2, 1, 1)
    return kb.as_markup()


def account_convert_categories_keyboard(account_id: int, current_cat: str, categories: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """کیبورد انتخاب دسته‌بندی مقصد برای تبدیل اکانت."""
    kb = InlineKeyboardBuilder()
    for c in categories:
        if c.get("key") != current_cat and c.get("is_active"):
            icon = c.get("icon", "🔹")
            title = c.get("title", c.get("key"))
            kb.button(text=f"{icon} {title}", callback_data=f"acc:conv_cat:{account_id}:{c.get('key')}")
    kb.button(text="🔙 انصراف و بازگشت", callback_data=f"acc:view:{account_id}")
    kb.adjust(1)
    return kb.as_markup()


def account_convert_plans_keyboard(account_id: int, current_price: int, plans: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """کیبورد انتخاب پلن مقصد همراه با نمایش تفاوت قیمت."""
    kb = InlineKeyboardBuilder()
    for p in plans:
        if p.get("is_active"):
            target_price = p.get("price", 0)
            diff = target_price - current_price
            if diff > 0:
                diff_label = f"(+{diff:,} تومان)"
            elif diff < 0:
                diff_label = f"({diff:,} عودت)"
            else:
                diff_label = "(یکسان)"
            kb.button(
                text=f"📦 {p.get('name')} {diff_label}",
                callback_data=f"acc:conv_plan:{account_id}:{p.get('id')}",
            )
    kb.button(text="🔙 بازگشت", callback_data=f"acc:convert_ask:{account_id}")
    kb.adjust(1)
    return kb.as_markup()


def account_convert_confirm_keyboard(account_id: int, target_plan_id: int) -> InlineKeyboardMarkup:
    """کیبورد تأیید نهایی عملیات تبدیل اکانت."""
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ تأیید و اجرای تبدیل اکانت", callback_data=f"acc:conv_exec:{account_id}:{target_plan_id}")
    kb.button(text="❌ انصراف", callback_data=f"acc:view:{account_id}")
    kb.adjust(1)
    return kb.as_markup()


def build_tutorials_main_keyboard() -> InlineKeyboardMarkup:
    """منوی اصلی راهنماهای اتصال."""
    kb = InlineKeyboardBuilder()
    kb.button(text="📱 راهنمای اندروید (Android)", callback_data="tut:view:android")
    kb.button(text="🍏 راهنمای آیفون / آیپد (iOS)", callback_data="tut:view:ios")
    kb.button(text="💻 راهنمای ویندوز (Windows)", callback_data="tut:view:windows")
    kb.button(text="⚡ آموزش اتصال WireGuard", callback_data="tut:view:wireguard")
    kb.button(text="🛡️ آموزش Cisco AnyConnect", callback_data="tut:view:cisco")
    kb.button(text="🔒 آموزش OpenVPN", callback_data="tut:view:openvpn")
    kb.button(text="☁️ آموزش گوگل اسکریپت (GAS)", callback_data="tut:view:gas")
    kb.button(text="⚡ آموزش SSH Tunnel", callback_data="tut:view:ssh")
    kb.button(text="🌐 آموزش تانل SlowDNS", callback_data="tut:view:slowdns")
    kb.button(text="🔙 بستن راهنما", callback_data="tut:close")
    kb.adjust(2, 2, 2, 2, 1, 1)
    return kb.as_markup()


def build_tutorial_back_keyboard(tut_key: str = "", dl_links: Optional[Dict[str, str]] = None) -> InlineKeyboardMarkup:
    from utils.tutorials import CLIENT_DOWNLOADS
    dls = dl_links or CLIENT_DOWNLOADS
    kb = InlineKeyboardBuilder()

    if tut_key == "android":
        kb.button(text="📥 دانلود v2rayNG", url=dls.get("v2rayng_google_play", CLIENT_DOWNLOADS["v2rayng_google_play"]))
        kb.button(text="📥 دانلود WireGuard", url=dls.get("wireguard_android", CLIENT_DOWNLOADS["wireguard_android"]))
        kb.button(text="📥 دانلود سیسکو (Google Play)", url=dls.get("cisco_android", CLIENT_DOWNLOADS["cisco_android"]))
        kb.button(text="📥 دانلود OpenVPN (Google Play)", url=dls.get("openvpn_android", CLIENT_DOWNLOADS["openvpn_android"]))
    elif tut_key == "ios":
        kb.button(text="📥 دانلود Streisand (App Store)", url=dls.get("streisand_ios", CLIENT_DOWNLOADS["streisand_ios"]))
        kb.button(text="📥 دانلود WireGuard (App Store)", url=dls.get("wireguard_ios", CLIENT_DOWNLOADS["wireguard_ios"]))
        kb.button(text="📥 دانلود V2Box (App Store)", url=dls.get("v2box_ios", CLIENT_DOWNLOADS["v2box_ios"]))
        kb.button(text="📥 دانلود سیسکو (App Store)", url=dls.get("cisco_ios", CLIENT_DOWNLOADS["cisco_ios"]))
        kb.button(text="📥 دانلود OpenVPN (App Store)", url=dls.get("openvpn_ios", CLIENT_DOWNLOADS["openvpn_ios"]))
    elif tut_key == "windows":
        kb.button(text="📥 دانلود v2rayN", url=dls.get("v2rayn_windows", CLIENT_DOWNLOADS["v2rayn_windows"]))
        kb.button(text="📥 دانلود WireGuard ویندوز", url=dls.get("wireguard_windows", CLIENT_DOWNLOADS["wireguard_windows"]))
        kb.button(text="📥 دانلود سیسکو ویندوز", url=dls.get("cisco_windows", CLIENT_DOWNLOADS["cisco_windows"]))
        kb.button(text="📥 دانلود OpenVPN ویندوز", url=dls.get("openvpn_windows", CLIENT_DOWNLOADS["openvpn_windows"]))
    elif tut_key == "wireguard":
        kb.button(text="📥 WireGuard اندروید", url=dls.get("wireguard_android", CLIENT_DOWNLOADS["wireguard_android"]))
        kb.button(text="📥 WireGuard آیفون", url=dls.get("wireguard_ios", CLIENT_DOWNLOADS["wireguard_ios"]))
        kb.button(text="📥 WireGuard ویندوز", url=dls.get("wireguard_windows", CLIENT_DOWNLOADS["wireguard_windows"]))
        kb.button(text="📥 WireGuard مک", url=dls.get("wireguard_macos", CLIENT_DOWNLOADS["wireguard_macos"]))
    elif tut_key == "gas":
        kb.button(text="🌐 Google OAuth Playground", url=dls.get("google_oauth_playground", CLIENT_DOWNLOADS["google_oauth_playground"]))
        kb.button(text="☁️ Cloudflare API Tokens", url=dls.get("cloudflare_dash", CLIENT_DOWNLOADS["cloudflare_dash"]))
        kb.button(text="📥 کلاینت Goose VPN", url=dls.get("goose_github", CLIENT_DOWNLOADS["goose_github"]))
    elif tut_key == "cisco":
        kb.button(text="📥 سیسکو اندروید", url=dls.get("cisco_android", CLIENT_DOWNLOADS["cisco_android"]))
        kb.button(text="📥 سیسکو آیفون", url=dls.get("cisco_ios", CLIENT_DOWNLOADS["cisco_ios"]))
        kb.button(text="📥 سیسکو ویندوز", url=dls.get("cisco_windows", CLIENT_DOWNLOADS["cisco_windows"]))
    elif tut_key == "openvpn":
        kb.button(text="📥 OpenVPN اندروید", url=dls.get("openvpn_android", CLIENT_DOWNLOADS["openvpn_android"]))
        kb.button(text="📥 OpenVPN آیفون", url=dls.get("openvpn_ios", CLIENT_DOWNLOADS["openvpn_ios"]))
        kb.button(text="📥 OpenVPN ویندوز", url=dls.get("openvpn_windows", CLIENT_DOWNLOADS["openvpn_windows"]))

    kb.button(text="🔙 بازگشت به منوی آموزش‌ها", callback_data="tut:main")
    kb.adjust(2)
    return kb.as_markup()


# ──────────────────────────────────────────────────────────────
#  کیبوردهای مرکز دانلود نرم‌افزارها (App Download Center)
# ──────────────────────────────────────────────────────────────

def build_apps_center_keyboard() -> InlineKeyboardMarkup:
    """منوی اصلی مرکز دانلود نرم‌افزارها تفکیک‌شده بر اساس سیستم‌عامل و پروتکل."""
    kb = InlineKeyboardBuilder()
    # بر اساس سیستم‌عامل
    kb.button(text="📱 اندروید (Android)", callback_data="app:os:android")
    kb.button(text="🍏 آیفون و آیپد (iOS)", callback_data="app:os:ios")
    kb.button(text="💻 ویندوز (Windows PC)", callback_data="app:os:windows")
    kb.button(text="🖥️ مک (macOS)", callback_data="app:os:macos")
    kb.button(text="🐧 لینوکس (Linux)", callback_data="app:os:linux")

    # بر اساس پروتکل
    kb.button(text="🚀 پروتکل Sing-box و V2Ray", callback_data="app:proto:singbox")
    kb.button(text="⚡ پروتکل وایرگارد (WireGuard)", callback_data="app:proto:wireguard")
    kb.button(text="🛡️ پروتکل‌های سیسکو و سیستمی", callback_data="app:proto:standard")
    kb.button(text="🌐 تانل ضد فیلتر SlowDNS", callback_data="app:proto:dnstt")
    kb.button(text="☁️ گوگل اسکریپت و کلودفلر (GAS)", callback_data="app:proto:gas")

    kb.button(text="🔙 بازگشت به منوی اصلی", callback_data="menu:home")
    kb.adjust(2, 2, 1, 2, 2, 1, 1)
    return kb.as_markup()


def build_apps_os_detail_keyboard(os_key: str, dl_links: Optional[Dict[str, str]] = None) -> InlineKeyboardMarkup:
    """کیبورد دکمه‌های دانلود مستقیم برای یک سیستم‌عامل خاص."""
    from utils.tutorials import CLIENT_DOWNLOADS
    dls = dl_links or CLIENT_DOWNLOADS
    kb = InlineKeyboardBuilder()

    if os_key == "android":
        kb.button(text="📥 دانلود v2rayNG (گوگل‌پلی)", url=dls.get("v2rayng_google_play", CLIENT_DOWNLOADS["v2rayng_google_play"]))
        kb.button(text="📦 دانلود مستقیم APK (گیت‌هاب)", url=dls.get("v2rayng_github", CLIENT_DOWNLOADS["v2rayng_github"]))
        kb.button(text="⚡ دانلود WireGuard اندروید", url=dls.get("wireguard_android", CLIENT_DOWNLOADS["wireguard_android"]))
        kb.button(text="🛡️ دانلود سیسکو AnyConnect", url=dls.get("cisco_android", CLIENT_DOWNLOADS["cisco_android"]))
        kb.button(text="🔒 دانلود OpenVPN Connect", url=dls.get("openvpn_android", CLIENT_DOWNLOADS["openvpn_android"]))
        kb.button(text="🌐 دانلود SlowDNS", url=dls.get("slowdns_android", CLIENT_DOWNLOADS["slowdns_android"]))
    elif os_key == "ios":
        kb.button(text="🌟 دانلود Streisand (اپ‌استور)", url=dls.get("streisand_ios", CLIENT_DOWNLOADS["streisand_ios"]))
        kb.button(text="📱 دانلود V2Box (اپ‌استور)", url=dls.get("v2box_ios", CLIENT_DOWNLOADS["v2box_ios"]))
        kb.button(text="⚡ دانلود WireGuard (اپ‌استور)", url=dls.get("wireguard_ios", CLIENT_DOWNLOADS["wireguard_ios"]))
        kb.button(text="🦊 دانلود FoXray (اپ‌استور)", url=dls.get("foxray_ios", CLIENT_DOWNLOADS["foxray_ios"]))
        kb.button(text="🛡️ دانلود سیسکو Secure Client", url=dls.get("cisco_ios", CLIENT_DOWNLOADS["cisco_ios"]))
        kb.button(text="🔒 دانلود OpenVPN iOS", url=dls.get("openvpn_ios", CLIENT_DOWNLOADS["openvpn_ios"]))
    elif os_key == "windows":
        kb.button(text="🌟 دانلود نرم‌افزار v2rayN", url=dls.get("v2rayn_windows", CLIENT_DOWNLOADS["v2rayn_windows"]))
        kb.button(text="⚡ دانلود نصاب WireGuard ویندوز", url=dls.get("wireguard_windows", CLIENT_DOWNLOADS["wireguard_windows"]))
        kb.button(text="🛡️ دانلود سیسکو AnyConnect ویندوز", url=dls.get("cisco_windows", CLIENT_DOWNLOADS["cisco_windows"]))
        kb.button(text="🔒 دانلود OpenVPN ویندوز", url=dls.get("openvpn_windows", CLIENT_DOWNLOADS["openvpn_windows"]))
    elif os_key == "macos":
        kb.button(text="📱 دانلود V2Box مک", url=dls.get("v2box_ios", CLIENT_DOWNLOADS["v2box_ios"]))
        kb.button(text="⚡ دانلود WireGuard مک", url=dls.get("wireguard_macos", CLIENT_DOWNLOADS["wireguard_macos"]))
        kb.button(text="🚀 باینری دسکتاپ Sing-box", url=dls.get("singbox_desktop", CLIENT_DOWNLOADS["singbox_desktop"]))
    elif os_key == "linux":
        kb.button(text="🌐 راهنمای رسمی WireGuard Linux", url=dls.get("wireguard_linux", CLIENT_DOWNLOADS["wireguard_linux"]))
        kb.button(text="🚀 دانلود هسته Sing-box Linux", url=dls.get("singbox_desktop", CLIENT_DOWNLOADS["singbox_desktop"]))

    kb.button(text="🔙 بازگشت به مرکز دانلود", callback_data="app:center")
    kb.adjust(2)
    return kb.as_markup()


def build_apps_proto_detail_keyboard(proto_key: str, dl_links: Optional[Dict[str, str]] = None) -> InlineKeyboardMarkup:
    """کیبورد دکمه‌های مستقیم دانلود برای یک پروتکل خاص."""
    from utils.tutorials import CLIENT_DOWNLOADS
    dls = dl_links or CLIENT_DOWNLOADS
    kb = InlineKeyboardBuilder()

    if proto_key == "singbox":
        kb.button(text="📥 v2rayNG اندروید", url=dls.get("v2rayng_google_play", CLIENT_DOWNLOADS["v2rayng_google_play"]))
        kb.button(text="📥 Streisand آیفون", url=dls.get("streisand_ios", CLIENT_DOWNLOADS["streisand_ios"]))
        kb.button(text="📥 v2rayN ویندوز", url=dls.get("v2rayn_windows", CLIENT_DOWNLOADS["v2rayn_windows"]))
        kb.button(text="📥 V2Box مک", url=dls.get("v2box_ios", CLIENT_DOWNLOADS["v2box_ios"]))
    elif proto_key == "wireguard":
        kb.button(text="📥 WireGuard اندروید", url=dls.get("wireguard_android", CLIENT_DOWNLOADS["wireguard_android"]))
        kb.button(text="📥 WireGuard آیفون", url=dls.get("wireguard_ios", CLIENT_DOWNLOADS["wireguard_ios"]))
        kb.button(text="📥 WireGuard ویندوز", url=dls.get("wireguard_windows", CLIENT_DOWNLOADS["wireguard_windows"]))
        kb.button(text="📥 WireGuard مک", url=dls.get("wireguard_macos", CLIENT_DOWNLOADS["wireguard_macos"]))
    elif proto_key == "standard":
        kb.button(text="🛡️ سیسکو اندروید", url=dls.get("cisco_android", CLIENT_DOWNLOADS["cisco_android"]))
        kb.button(text="🛡️ سیسکو آیفون", url=dls.get("cisco_ios", CLIENT_DOWNLOADS["cisco_ios"]))
        kb.button(text="🔒 OpenVPN اندروید", url=dls.get("openvpn_android", CLIENT_DOWNLOADS["openvpn_android"]))
        kb.button(text="🔒 OpenVPN آیفون", url=dls.get("openvpn_ios", CLIENT_DOWNLOADS["openvpn_ios"]))
    elif proto_key == "dnstt":
        kb.button(text="📥 دانلود SlowDNS اندروید", url=dls.get("slowdns_android", CLIENT_DOWNLOADS["slowdns_android"]))
        kb.button(text="📥 دانلود HTTP Custom", url=dls.get("http_custom_android", CLIENT_DOWNLOADS["http_custom_android"]))
    elif proto_key == "gas":
        kb.button(text="🌐 Google OAuth Playground", url=dls.get("google_oauth_playground", CLIENT_DOWNLOADS["google_oauth_playground"]))
        kb.button(text="☁️ پنل توکن‌های Cloudflare", url=dls.get("cloudflare_dash", CLIENT_DOWNLOADS["cloudflare_dash"]))
        kb.button(text="📥 کلاینت Goose VPN (گیت‌هاب)", url=dls.get("goose_github", CLIENT_DOWNLOADS["goose_github"]))

    kb.button(text="🔙 بازگشت به مرکز دانلود", callback_data="app:center")
    kb.adjust(2)
    return kb.as_markup()

    kb.adjust(2)
    return kb.as_markup()


def account_configs_keyboard(account_id: int, configs: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    # دانلود تمام کانفیگ‌ها در یک فایل متنی
    kb.button(text="📥 دانلود تمام کانفیگ‌ها در یک فایل متنی (.txt)", callback_data=f"acc:dl_all_cfgs:{account_id}")
    for idx, cfg in enumerate(configs[:18]):
        tag = cfg.get("tag", f"کانفیگ {idx+1}")
        proto = cfg.get("type", "").upper()
        port = cfg.get("port")
        port_info = f" :{port}" if port else ""
        kb.button(text=f"🔑 {proto} ({tag}){port_info}", callback_data=f"acc:cfg_view:{account_id}:{idx}")
    kb.button(text="🔙 بازگشت به مشخصات اکانت", callback_data=f"acc:view:{account_id}")
    kb.adjust(1)
    return kb.as_markup()


# ── کیف پول ──────────────────────────────────────────────────

def wallet_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 شارژ حساب با کارت‌به‌کارت", callback_data="wllt:card")
    kb.button(text="📋 شماره کارت و مشخصات واریز", callback_data="wllt:info")
    kb.button(text="🔙 بازگشت", callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()


# ── تیکت‌ها ──────────────────────────────────────────────────

def build_tickets_keyboard(tickets: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for t in tickets:
        kb.button(
            text=f"🎫 #{t.get('id')} — {t.get('subject', '—')}",
            callback_data=f"tk:view:{t.get('id')}",
        )
    kb.button(text="➕ ارسال تیکت جدید", callback_data="tk:new")
    kb.button(text="🔙 بازگشت", callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()


def ticket_details_keyboard(ticket_id: int, can_reply: bool = True) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if can_reply:
        kb.button(text="💬 ارسال پاسخ", callback_data=f"tk:reply:{ticket_id}")
    kb.button(text="🔙 بازگشت به لیست تیکت‌ها", callback_data="tk:list")
    kb.adjust(1)
    return kb.as_markup()


# ── اعلان‌ها ─────────────────────────────────────────────────

def build_notifications_keyboard(notifications: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for n in notifications:
        if not n.get("is_read"):
            kb.button(
                text=f"📩 خواندن اعلان #{n.get('id')}",
                callback_data=f"ntf:read:{n.get('id')}",
            )
    kb.button(text="🔙 بازگشت", callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()


# ──────────────────────────────────────────────────────────────
#  کیبوردهای شیشه‌ای پنل مدیریت (Admin Inline Keyboards)
# ──────────────────────────────────────────────────────────────

def admin_main_keyboard() -> InlineKeyboardMarkup:
    """منوی اصلی کنترل پنل مدیریت."""
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 آمار و تحلیل فروش حرفه‌ای", callback_data="adm:stats")
    kb.button(text="👤 مدیریت کاربران ربات", callback_data="adm:users_menu")
    kb.button(text="👑 مدیریت مدیران ربات", callback_data="adm:admins_menu")
    kb.button(text="📁 مدیریت دسته‌بندی‌ها و پلن‌ها", callback_data="adm:categories")
    kb.button(text="⚙️ مدیریت پروتکل‌ها و سرور", callback_data="adm:server_configs")
    kb.button(text="💳 مدیریت شماره کارت بانکی", callback_data="adm:card_settings")
    kb.button(text="📥 فیش‌های واریزی در انتظار", callback_data="adm:pending_tx")
    kb.button(text="📢 ارسال اعلان و پیام همگانی", callback_data="adm:broadcast")
    kb.button(text="🎁 تنظیمات اکانت تست", callback_data="adm:trial")
    kb.button(text="🔔 تنظیمات اعلان‌های مدیریت", callback_data="adm:notifications")
    kb.button(text="👥 مدیریت رفرال و پورسانت", callback_data="adm:referral")
    kb.button(text="📚 مدیریت و ویرایش آموزش‌ها", callback_data="adm:tutorials")
    kb.button(text="📲 مدیریت لینک‌های دانلود نرم‌افزار", callback_data="adm:downloads")
    kb.button(text="🎫 پاسخ به تیکت‌های کاربران", callback_data="adm:tickets")
    kb.button(text="🔄 تست اتصال زنده MHPanel", callback_data="adm:test_panel")
    kb.button(text="❌ بستن پنل مدیریت", callback_data="adm:close")
    kb.adjust(1, 2, 2, 2, 2, 2, 2, 2, 1)
    return kb.as_markup()


def admin_notifications_keyboard(is_buy_on: bool, is_trial_on: bool) -> InlineKeyboardMarkup:
    """کیبورد تنظیمات اعلان‌های آن‌تایم خرید و تست برای ادمین."""
    kb = InlineKeyboardBuilder()
    buy_icon = "🟢 روشن (ارسال فعال)" if is_buy_on else "🔴 خاموش (غیرفعال)"
    trial_icon = "🟢 روشن (ارسال فعال)" if is_trial_on else "🔴 خاموش (غیرفعال)"

    kb.button(text=f"🛒 اعلان خرید: {buy_icon}", callback_data="adm:notify:toggle_buy")
    kb.button(text=f"🎁 اعلان تست: {trial_icon}", callback_data="adm:notify:toggle_trial")
    kb.button(text="🔙 بازگشت به منوی مدیریت", callback_data="adm:main")
    kb.adjust(1)
    return kb.as_markup()


# ── کیبوردهای مدیریت کاربران (User Management Keyboards) ─────────

def admin_users_menu_keyboard() -> InlineKeyboardMarkup:
    """منوی جستجو و مشاهده کاربران توسط ادمین."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🔍 جستجوی کاربر (آیدی عددی یا یوزرنیم)", callback_data="adm:u_search")
    kb.button(text="📋 لیست ۲۰ کاربر اخیر ثبت‌نامی", callback_data="adm:u_recent")
    kb.button(text="🔙 بازگشت به منوی اصلی مدیریت", callback_data="adm:main")
    kb.adjust(1)
    return kb.as_markup()


def admin_user_card_keyboard(target_user_id: int) -> InlineKeyboardMarkup:
    """عملیات مدیریتی روی یک کاربر خاص."""
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 افزایش موجودی کیف پول", callback_data=f"adm:u_bal_add:{target_user_id}")
    kb.button(text="💸 کسر از موجودی کیف پول", callback_data=f"adm:u_bal_sub:{target_user_id}")
    kb.button(text="📦 صدور و فعال‌سازی مستقیم اکانت", callback_data=f"adm:u_acc_cat:{target_user_id}")
    kb.button(text="🧾 صدور فاکتور / تراکنش دستی", callback_data=f"adm:u_inv:{target_user_id}")
    kb.button(text="💬 ارسال پیام مستقیم به کاربر", callback_data=f"adm:u_msg:{target_user_id}")
    kb.button(text="💳 تاریخچه تراکنش‌ها و رسیدها", callback_data=f"adm:u_txs:{target_user_id}")
    kb.button(text="📦 مشاهده اکانت‌های این کاربر", callback_data=f"adm:u_accs:{target_user_id}")
    kb.button(text="🔙 بازگشت به مدیریت کاربران", callback_data="adm:users_menu")
    kb.adjust(2, 1, 2, 2, 1)
    return kb.as_markup()


def admin_manage_admins_keyboard(admins: List[Dict[str, Any]], primary_admins: List[int]) -> InlineKeyboardMarkup:
    """کیبورد لیست مدیران و افزودن/حذف مدیر جدید."""
    kb = InlineKeyboardBuilder()
    for a in admins:
        uid = a.get("telegram_id")
        name = a.get("first_name") or a.get("username") or str(uid)
        is_primary = uid in primary_admins
        if not is_primary:
            kb.button(text=f"🗑 حذف دسترسی {name}", callback_data=f"adm:admin_del:{uid}")
    kb.button(text="➕ افزودن مدیر جدید به ربات", callback_data="adm:admin_add")
    kb.button(text="🔙 بازگشت به منوی مدیریت", callback_data="adm:main")
    kb.adjust(1)
    return kb.as_markup()


# ── مدیریت پروتکل‌ها و سرور ──────────────────────────────────

def admin_server_configs_keyboard() -> InlineKeyboardMarkup:
    """تفکیک پروتکل‌های سرور به بخش‌های مستقل و مجزا."""
    kb = InlineKeyboardBuilder()
    kb.button(text="⚡ ۱. هسته سینگ‌باکس و V2Ray (سوئیت کامل ۲۳ اینباند)", callback_data="adm:srv_proto:singbox")
    kb.button(text="🛡️ ۲. پروتکل‌های استاندارد (Cisco / OpenVPN / L2TP / IKEv2 / SSH / SSTP)", callback_data="adm:srv_proto:system")
    kb.button(text="🌐 ۳. تانل‌های اضطراری DNS (SlowDNS / DNSTT)", callback_data="adm:srv_proto:dns")
    kb.button(text="📚 فایل‌های سرتیفیکیت و کانفیگ OpenVPN", callback_data="adm:srv:tut_files")
    kb.button(text="🎛 سوئیچ روشن/خاموش پروتکل‌ها و دسته‌ها", callback_data="adm:categories")
    kb.button(text="🔄 تست پینگ و پاسخ‌دهی زنده API", callback_data="adm:test_panel")
    kb.button(text="🔙 بازگشت به منوی مدیریت", callback_data="adm:main")
    kb.adjust(1)
    return kb.as_markup()


def admin_system_l2tp_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📥 دریافت فایل تستی OpenVPN (.ovpn)", callback_data="adm:dl_test_ovpn")
    kb.button(text="📜 سرتیفیکیت Cisco AnyConnect", callback_data="adm:dl_admin_cert:cisco")
    kb.button(text="📜 سرتیفیکیت IKEv2 / IPsec", callback_data="adm:dl_admin_cert:ikev2")
    kb.button(text="📜 سرتیفیکیت SSTP", callback_data="adm:dl_admin_cert:sstp")
    kb.button(text="🌐 تغییر آی‌پی سرور", callback_data="adm:srv:set_ip")
    kb.button(text="🔐 تغییر Pre-Shared Key (PSK)", callback_data="adm:srv:set_psk")
    kb.button(text="🔙 بازگشت به پروتکل‌ها", callback_data="adm:server_configs")
    kb.adjust(1, 3, 2, 1)
    return kb.as_markup()


# ── مدیریت دسته‌بندی‌ها و پلن‌ها ──────────────────────────────

def admin_categories_list_keyboard(categories: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """کیبورد مدیریت دسته‌بندی‌ها با امکان روشن/خاموش سریع و حذف یا ویرایش."""
    kb = InlineKeyboardBuilder()
    layout = []
    for cat in categories:
        is_active = bool(cat.get("is_active"))
        status_btn = "🟢 روشن" if is_active else "🔴 خاموش"
        icon = cat.get("icon") or "⚡"
        p_cnt = cat.get("plans_count", 0)
        title = cat.get("title", "دسته")
        kb.button(
            text=f"{icon} {title} ({p_cnt} پلن)",
            callback_data=f"adm:cat_view:{cat.get('key')}",
        )
        kb.button(
            text=status_btn,
            callback_data=f"adm:cat_toggle_quick:{cat.get('key')}",
        )
        kb.button(
            text="🗑 حذف",
            callback_data=f"adm:cat_del_ask:{cat.get('key')}",
        )
        layout.append(3)
    kb.button(text="➕ افزودن دسته‌بندی جدید", callback_data="adm:cat_add")
    layout.append(1)
    kb.button(text="🔙 بازگشت به مدیریت", callback_data="adm:main")
    layout.append(1)
    kb.adjust(*layout)
    return kb.as_markup()


def admin_category_detail_keyboard(cat_key: str, is_active: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    toggle_txt = "🔴 غیرفعال‌سازی این دسته" if is_active else "🟢 فعال‌سازی این دسته"
    kb.button(text="📋 مشاهده و مدیریت پلن‌ها", callback_data=f"adm:plans_list:{cat_key}")
    kb.button(text="➕ افزودن پلن جدید به این دسته", callback_data=f"adm:plan_add:{cat_key}")
    kb.button(text=toggle_txt, callback_data=f"adm:cat_toggle:{cat_key}")
    kb.button(text="🗑 حذف کامل این دسته‌بندی و پلن‌ها", callback_data=f"adm:cat_del_ask:{cat_key}")
    kb.button(text="🔙 بازگشت به لیست دسته‌ها", callback_data="adm:categories")
    kb.adjust(1)
    return kb.as_markup()


def admin_cat_delete_confirm_keyboard(cat_key: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 بله، قطعاً حذف شود", callback_data=f"adm:cat_del_confirm:{cat_key}")
    kb.button(text="❌ انصراف و بازگشت", callback_data=f"adm:cat_view:{cat_key}")
    kb.adjust(1)
    return kb.as_markup()


def admin_category_proto_select_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 ۱. هسته کامل Sing-box و V2Ray (تمام پروتکل‌ها)", callback_data="adm:newcat_proto:singbox")
    kb.button(text="🛡️ ۲. پروتکل‌های سیستمی مستقیم (L2TP / IKEv2)", callback_data="adm:newcat_proto:system_l2tp")
    kb.button(text="🌐 ۳. تانل اضطراری DNS (SlowDNS / DNSTT)", callback_data="adm:newcat_proto:dnstt")
    kb.button(text="❌ انصراف", callback_data="adm:categories")
    kb.adjust(1)
    return kb.as_markup()


def admin_bank_cards_list_keyboard(cards: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """لیست کارت‌های گردون بانکی با امکان روشن/خاموش سریع و حذف در پنل ادمین."""
    kb = InlineKeyboardBuilder()
    layout = []
    for c in cards:
        is_active = bool(c.get("is_active"))
        st_icon = "🟢" if is_active else "🔴"
        st_text = "🟢 روشن" if is_active else "🔴 خاموش"
        c_num = c.get("card_number", "")
        short_num = f"{c_num[:4]}..{c_num[-4:]}" if len(c_num) >= 8 else c_num
        holder = c.get("card_holder", "")
        # محدود کردن طول نام دارنده
        short_holder = holder[:15] + ".." if len(holder) > 15 else holder

        kb.button(
            text=f"{st_icon} {short_num} ({short_holder})",
            callback_data=f"adm:card_view:{c['id']}",
        )
        kb.button(
            text=st_text,
            callback_data=f"adm:card_toggle:{c['id']}",
        )
        kb.button(
            text="🗑",
            callback_data=f"adm:card_del:{c['id']}",
        )
        layout.append(3)

    kb.button(text="➕ افزودن کارت بانکی جدید به گردونه", callback_data="adm:card_add")
    layout.append(1)
    kb.button(text="🔙 بازگشت به مدیریت", callback_data="adm:main")
    layout.append(1)
    kb.adjust(*layout)
    return kb.as_markup()


def admin_bank_card_detail_keyboard(card_id: int, is_active: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    toggle_txt = "🔴 غیرفعال‌سازی این کارت" if is_active else "🟢 فعال‌سازی این کارت"
    kb.button(text=toggle_txt, callback_data=f"adm:card_toggle:{card_id}")
    kb.button(text="🗑 حذف این کارت", callback_data=f"adm:card_del:{card_id}")
    kb.button(text="🔙 بازگشت به لیست کارت‌ها", callback_data="adm:card_settings")
    kb.adjust(1)
    return kb.as_markup()


def admin_broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 بله، ارسال به تمام اعضا", callback_data="adm:broadcast:send")
    kb.button(text="❌ لغو و انصراف", callback_data="adm:broadcast:cancel")
    kb.adjust(2)
    return kb.as_markup()


def admin_plans_list_keyboard(plans: List[Dict[str, Any]], cat_key: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for plan in plans:
        st = "🟢" if plan.get("is_active") else "🔴"
        name = plan.get("name", "پلن")
        pr = to_toman(plan.get("price", 0))
        kb.button(
            text=f"{st} {name} — {pr}",
            callback_data=f"adm:plan_view:{plan.get('id')}",
        )
    kb.button(text="➕ افزودن پلن جدید", callback_data=f"adm:plan_add:{cat_key}")
    kb.button(text="🔙 بازگشت به دسته‌بندی", callback_data=f"adm:cat_view:{cat_key}")
    kb.adjust(1)
    return kb.as_markup()


def admin_plan_detail_keyboard(plan_id: int, cat_key: str, is_active: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    toggle_txt = "🔴 غیرفعال‌سازی پلن" if is_active else "🟢 فعال‌سازی پلن"
    kb.button(text=toggle_txt, callback_data=f"adm:plan_toggle:{plan_id}")
    kb.button(text="🗑 حذف پلن", callback_data=f"adm:plan_del:{plan_id}")
    kb.button(text="🔙 بازگشت به پلن‌ها", callback_data=f"adm:plans_list:{cat_key}")
    kb.adjust(1)
    return kb.as_markup()


# ── سایر کیبوردهای مدیریت و تست ──────────────────────────────

def trial_select_keyboard() -> InlineKeyboardMarkup:
    """کیبورد انتخاب نوع یا پروتکل اکانت تستی برای کاربر."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🌟 پکیج جامع (تست کلیه پروتکل‌ها به صورت یکجا)", callback_data="trial:mode:all")
    kb.button(text="🚀 ۱. کانفیگ‌های Sing-box و V2Ray", callback_data="trial:mode:singbox")
    kb.button(text="🛡️ ۲. سیسکو، اوپن‌وی‌پی‌ان و L2TP", callback_data="trial:mode:system_l2tp")
    kb.button(text="⚡ ۳. وایرگارد مدرن (WireGuard)", callback_data="trial:mode:wireguard")
    kb.button(text="🌐 ۴. تانل ضد فیلتر DNS (SlipNet)", callback_data="trial:mode:dnstt")
    kb.button(text="❌ انصراف و بازگشت", callback_data="trial:cancel")
    kb.adjust(1)
    return kb.as_markup()


def admin_trial_keyboard(is_enabled: bool, trial_mode: str = "menu") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    toggle_txt = "🔴 غیرفعال‌سازی تست رایگان" if is_enabled else "🟢 فعال‌سازی تست رایگان"
    kb.button(text=toggle_txt, callback_data="adm:trial:toggle")
    kb.button(text="📶 تغییر حجم اکانت تست", callback_data="adm:trial:set_gb")
    kb.button(text="⏱ تغییر مدت روز اعتبار", callback_data="adm:trial:set_days")
    
    mode_lbl = "🌟 نحوه صدور: منوی انتخاب + پکیج کامل" if trial_mode == "menu" else "⚡ نحوه صدور: صدور مستقیم همه حالت‌ها"
    kb.button(text=mode_lbl, callback_data="adm:trial:toggle_mode")
    kb.button(text="🗑 پاکسازی دستی تست‌های منقضی شده از پنل", callback_data="adm:trial:cleanup")
    
    kb.button(text="🔙 بازگشت به مدیریت", callback_data="adm:main")
    kb.adjust(1)
    return kb.as_markup()



def admin_referral_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔢 تغییر درصد پورسانت", callback_data="adm:ref:set_pct")
    kb.button(text="🏆 برترین بازاریاب‌ها", callback_data="adm:ref:top")
    kb.button(text="🔙 بازگشت به مدیریت", callback_data="adm:main")
    kb.adjust(1)
    return kb.as_markup()


def admin_tx_keyboard(tx_id: int, has_photo: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if has_photo:
        kb.button(text="🖼 مشاهده عکس فیش", callback_data=f"adm:tx_photo:{tx_id}")
    kb.button(text="✅ تأیید و شارژ حساب", callback_data=f"adm:tx_appr:{tx_id}")
    kb.button(text="❌ رد درخواست", callback_data=f"adm:tx_rej:{tx_id}")
    kb.button(text="🔙 بازگشت به فیش‌ها", callback_data="adm:pending_tx")
    if has_photo:
        kb.adjust(1, 2, 1)
    else:
        kb.adjust(2, 1)
    return kb.as_markup()


def admin_ticket_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 ارسال پاسخ به کاربر", callback_data=f"adm:tk_rep:{ticket_id}")
    kb.button(text="🔒 بستن تیکت", callback_data=f"adm:tk_close:{ticket_id}")
    kb.button(text="🔙 بازگشت به تیکت‌ها", callback_data="adm:tickets")
    kb.adjust(2, 1)
    return kb.as_markup()


# ── کیبوردهای مدیریت آموزش‌ها و دانلودها ─────────────────────

def admin_tutorials_list_keyboard() -> InlineKeyboardMarkup:
    """لیست کل آموزش‌ها جهت انتخاب برای ویرایش توسط مدیر."""
    from utils.tutorials import TUTORIAL_TITLES
    kb = InlineKeyboardBuilder()
    for k, title in TUTORIAL_TITLES.items():
        kb.button(text=title, callback_data=f"adm:tut_view:{k}")
    kb.button(text="🔙 بازگشت به منوی مدیریت", callback_data="adm:main")
    kb.adjust(1)
    return kb.as_markup()


def admin_tutorial_detail_keyboard(tut_key: str, is_custom: bool) -> InlineKeyboardMarkup:
    """عملیات روی یک آموزش خاص."""
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ ویرایش متن آموزش", callback_data=f"adm:tut_edit:{tut_key}")
    if is_custom:
        kb.button(text="🔄 بازنشانی به متن پیش‌فرض", callback_data=f"adm:tut_reset:{tut_key}")
    kb.button(text="🔙 بازگشت به لیست آموزش‌ها", callback_data="adm:tutorials")
    kb.adjust(1)
    return kb.as_markup()


def admin_downloads_list_keyboard() -> InlineKeyboardMarkup:
    """لیست نرم‌افزارها جهت تغییر لینک دانلود توسط مدیر."""
    from utils.tutorials import CLIENT_DOWNLOAD_TITLES
    kb = InlineKeyboardBuilder()
    for k, title in CLIENT_DOWNLOAD_TITLES.items():
        kb.button(text=title, callback_data=f"adm:dl_view:{k}")
    kb.button(text="🔙 بازگشت به منوی مدیریت", callback_data="adm:main")
    kb.adjust(1)
    return kb.as_markup()


def admin_download_detail_keyboard(dl_key: str, is_custom: bool) -> InlineKeyboardMarkup:
    """عملیات روی یک لینک دانلود نرم‌افزار."""
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ تغییر لینک دانلود", callback_data=f"adm:dl_edit:{dl_key}")
    if is_custom:
        kb.button(text="🔄 بازنشانی به لینک پیش‌فرض", callback_data=f"adm:dl_reset:{dl_key}")
    kb.button(text="🔙 بازگشت به لیست نرم‌افزارها", callback_data="adm:downloads")
    kb.adjust(1)
    return kb.as_markup()

