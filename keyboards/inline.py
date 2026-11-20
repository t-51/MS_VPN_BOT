"""کیبوردهای شیشه‌ای (Inline) کاربر و پنل مدیریت MS_VPN_BOT."""
from typing import List, Any, Dict, Optional

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.formatters import plan_label
from utils.helpers import to_toman, to_fa, duration_label, to_days


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


def shop_category_durations_keyboard(cat_key: str, durations: List[int]) -> InlineKeyboardMarkup:
    """کیبورد انتخاب مدت زمان اشتراک قبل از نمایش پلن‌ها."""
    kb = InlineKeyboardBuilder()
    for d in durations:
        lbl = duration_label(d)
        kb.button(text=f"📅 اشتراک {lbl}", callback_data=f"shop:dur:{cat_key}:{d}")
    kb.button(text="🔙 بازگشت به دسته‌بندی‌ها", callback_data="shop:categories")
    kb.adjust(1)
    return kb.as_markup()


def build_plans_keyboard(
    plans: List[Dict[str, Any]],
    category_key: str,
    current_dur: Optional[int] = None,
) -> InlineKeyboardMarkup:
    """کیبورد لیست پلن‌های یک دسته‌بندی (تفکیک‌شده بر اساس زمان)."""
    kb = InlineKeyboardBuilder()

    def format_plan_btn(p):
        traffic = f"{to_fa(p.get('traffic_gb'))}GB" if p.get('traffic_gb') > 0 else "نامحدود"
        price = to_toman(p.get('price'))
        name = p.get('name')
        if current_dur:
            return f"📶 {name} ({traffic}) — {price}"
        return plan_label(p)

    for plan in plans:
        kb.button(
            text=format_plan_btn(plan),
            callback_data=f"buy:plan:{plan.get('id')}",
        )
    if current_dur:
        kb.button(text="🔙 تغییر مدت زمان (بازگشت)", callback_data=f"shop:cat:{category_key}")
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

def build_accounts_keyboard(
    accounts: List[Dict[str, Any]],
    user_categories: Optional[List[Dict[str, Any]]] = None,
    current_cat_id: Optional[int] = None,
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    cat_icons = {"singbox": "🚀", "v2ray": "⚡", "system_l2tp": "🛡️", "dnstt": "🌐", "reality": "🕶️"}

    # دکمه‌های فیلتر پوشه‌ها در صورت وجود دسته‌بندی شخصی
    filter_count = 0
    if user_categories:
        all_btn = "🌟 همه" if (current_cat_id is None or current_cat_id == 0) else "همه"
        kb.button(text=all_btn, callback_data="acc:filter:all")
        filter_count += 1
        for uc in user_categories[:5]:
            is_active = (current_cat_id == uc.get("id"))
            txt = f"{'✅ ' if is_active else '📁 '}{uc.get('name')[:12]}"
            kb.button(text=txt, callback_data=f"acc:filter:{uc.get('id')}")
            filter_count += 1

    for acc in accounts:
        cat = acc.get("category", "singbox")
        icon = cat_icons.get(cat, "📦")
        plan = acc.get("plan_name", "اشتراک")
        acc_type = "🎁 تستی" if acc.get("is_trial") else icon
        custom_name = acc.get("custom_name")
        btn_txt = f"{acc_type} {custom_name} — {plan}" if custom_name else f"{acc_type} {plan} ({acc.get('panel_username')})"
        kb.button(
            text=btn_txt,
            callback_data=f"acc:view:{acc.get('id')}",
        )

    kb.button(text="📁 مدیریت پوشه‌ها و دسته‌بندی‌ها", callback_data="acc:manage_user_cats")
    if accounts:
        kb.button(text="🎁 هدیه دادن یکی از اشتراک‌ها", callback_data="acc:gift_select")
    kb.button(text="🔍 استعلام کانفیگ با شناسه (UID)", callback_data="acc:search_uid")
    kb.button(text="🔙 بازگشت به منو", callback_data="menu:home")

    if filter_count > 0:
        layout = [filter_count] + [1] * len(accounts) + [1, 1, 1, 1] if accounts else [filter_count, 1, 1, 1]
        kb.adjust(*layout)
    else:
        kb.adjust(1)
    return kb.as_markup()


def account_details_keyboard(account_id: int, category: str = "singbox", sub_url: str = "") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if category in ["singbox", "v2ray", "reality"]:
        if sub_url:
            kb.button(text="🌐 مشاهده صفحه ساب در مرورگر", url=sub_url)
        kb.button(text="📷 دریافت بارکد QR سابسکریپشن", callback_data=f"acc:view_qr:{account_id}")
        kb.button(text="⚡ دریافت کانفیگ‌های تکی", callback_data=f"acc:configs:{account_id}")
        kb.button(text="🔄 تمدید اشتراک", callback_data=f"acc:renew_ask:{account_id}")
        kb.button(text="🚀 ارتقای پلن اشتراک", callback_data=f"acc:upgrade_ask:{account_id}")
        kb.button(text="✏️ تغییر نام دلخواه", callback_data=f"acc:set_name:{account_id}")
        kb.button(text="📁 دسته‌بندی و پوشه", callback_data=f"acc:set_cat:{account_id}")
        kb.button(text="🗑 لغو و حذف کانفیگ (با عودت وجه)", callback_data=f"acc:del_ask:{account_id}")
        kb.button(text="🔄 تغییر شناسه اتصال (UUID)", callback_data=f"acc:reset_id_ask:{account_id}")
        kb.button(text="🔁 تبدیل این اکانت به پروتکل دیگر", callback_data=f"acc:convert_ask:{account_id}")
        kb.button(text="🎁 هدیه دادن این اشتراک", callback_data=f"acc:gift_ask:{account_id}")
        kb.button(text="🔄 بروزرسانی وضعیت", callback_data=f"acc:view:{account_id}")
        kb.button(text="🔙 بازگشت به لیست اکانت‌ها", callback_data="acc:list")
        if sub_url:
            kb.adjust(1, 1, 1, 2, 2, 1, 1, 1, 1, 1, 1)
        else:
            kb.adjust(1, 1, 2, 2, 1, 1, 1, 1, 1, 1)
    elif category in ["wireguard", "amneziawg"]:
        kb.button(text="📥 دانلود کانفیگ اصلی (.conf)", callback_data=f"acc:dl_wg_conf:{account_id}")
        kb.button(text="📷 دریافت بارکد QR اصلی", callback_data=f"acc:dl_wg_qr:{account_id}")
        kb.button(text="🔀 پورت‌های اتصال (چند پورته)", callback_data=f"acc:wg_multiport:{account_id}")
        kb.button(text="📦 دانلود تمام پورت‌ها (فایل ZIP)", callback_data=f"acc:dl_wg_zip:{account_id}")
        kb.button(text="📋 مشاهده متن کانفیگ", callback_data=f"acc:view_wg_text:{account_id}")
        tut_btn = "tut:view:amneziawg" if category == "amneziawg" else "tut:view:wireguard"
        tut_txt = "🛡️ آموزش اتصال AmneziaWG" if category == "amneziawg" else "⚡ آموزش اتصال وایرگارد"
        kb.button(text=tut_txt, callback_data=tut_btn)
        kb.button(text="🔄 تمدید اشتراک", callback_data=f"acc:renew_ask:{account_id}")
        kb.button(text="🚀 ارتقای پلن اشتراک", callback_data=f"acc:upgrade_ask:{account_id}")
        kb.button(text="✏️ تغییر نام دلخواه", callback_data=f"acc:set_name:{account_id}")
        kb.button(text="📁 دسته‌بندی و پوشه", callback_data=f"acc:set_cat:{account_id}")
        kb.button(text="🗑 لغو و حذف کانفیگ (با عودت وجه)", callback_data=f"acc:del_ask:{account_id}")
        kb.button(text="🔄 بازسازی و تغییر کلیدها", callback_data=f"acc:reset_id_ask:{account_id}")
        kb.button(text="🔁 تبدیل این اکانت به پروتکل دیگر", callback_data=f"acc:convert_ask:{account_id}")
        kb.button(text="🎁 هدیه دادن این اشتراک", callback_data=f"acc:gift_ask:{account_id}")
        kb.button(text="🔄 بروزرسانی وضعیت", callback_data=f"acc:view:{account_id}")
        kb.button(text="🔙 بازگشت به لیست اکانت‌ها", callback_data="acc:list")
        kb.adjust(2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1)
    elif category == "gas":
        kb.button(text="🌐 جزئیات و کلید اتصال وب‌اپ", callback_data=f"acc:gas_info:{account_id}")
        kb.button(text="📖 راهنمای اتصال و آموزش GAS", callback_data="tut:view:gas")
        kb.button(text="🔄 تمدید اشتراک", callback_data=f"acc:renew_ask:{account_id}")
        kb.button(text="🚀 ارتقای پلن اشتراک", callback_data=f"acc:upgrade_ask:{account_id}")
        kb.button(text="✏️ تغییر نام دلخواه", callback_data=f"acc:set_name:{account_id}")
        kb.button(text="📁 دسته‌بندی و پوشه", callback_data=f"acc:set_cat:{account_id}")
        kb.button(text="🗑 لغو و حذف کانفیگ (با عودت وجه)", callback_data=f"acc:del_ask:{account_id}")
        kb.button(text="🔄 تغییر رمز اختصاصی", callback_data=f"acc:reset_id_ask:{account_id}")
        kb.button(text="🔁 تبدیل این اکانت به پروتکل دیگر", callback_data=f"acc:convert_ask:{account_id}")
        kb.button(text="🎁 هدیه دادن این اشتراک", callback_data=f"acc:gift_ask:{account_id}")
        kb.button(text="🔄 بروزرسانی وضعیت", callback_data=f"acc:view:{account_id}")
        kb.button(text="🔙 بازگشت به لیست اکانت‌ها", callback_data="acc:list")
        kb.adjust(1, 1, 2, 2, 1, 1, 1, 1, 1, 1)
    elif category == "system_l2tp":
        kb.button(text="📥 دانلود فایل OpenVPN (.ovpn)", callback_data=f"acc:dl_ovpn:{account_id}")
        kb.button(text="📱 کانفیگ‌های SlipNet (DNS / SSH / Tor)", callback_data=f"acc:slipnet_list:{account_id}")
        kb.button(text="📜 سرتیفیکیت Cisco", callback_data=f"acc:dl_cert:{account_id}:cisco")
        kb.button(text="📜 سرتیفیکیت IKEv2", callback_data=f"acc:dl_cert:{account_id}:ikev2")
        kb.button(text="📜 سرتیفیکیت SSTP", callback_data=f"acc:dl_cert:{account_id}:sstp")
        kb.button(text="📚 آموزش اتصال به سیسکو و OpenVPN", callback_data="tut:view:cisco")
        kb.button(text="🔄 تمدید اشتراک", callback_data=f"acc:renew_ask:{account_id}")
        kb.button(text="🚀 ارتقای پلن اشتراک", callback_data=f"acc:upgrade_ask:{account_id}")
        kb.button(text="✏️ تغییر نام دلخواه", callback_data=f"acc:set_name:{account_id}")
        kb.button(text="📁 دسته‌بندی و پوشه", callback_data=f"acc:set_cat:{account_id}")
        kb.button(text="🗑 لغو و حذف کانفیگ (با عودت وجه)", callback_data=f"acc:del_ask:{account_id}")
        kb.button(text="🔄 تغییر رمز عبور اکانت", callback_data=f"acc:reset_id_ask:{account_id}")
        kb.button(text="🔁 تبدیل این اکانت به پروتکل دیگر", callback_data=f"acc:convert_ask:{account_id}")
        kb.button(text="🎁 هدیه دادن این اشتراک", callback_data=f"acc:gift_ask:{account_id}")
        kb.button(text="🔄 بروزرسانی وضعیت", callback_data=f"acc:view:{account_id}")
        kb.button(text="🔙 بازگشت به لیست اکانت‌ها", callback_data="acc:list")
        kb.adjust(1, 1, 3, 1, 2, 2, 1, 1, 1, 1, 1, 1)
    elif category == "dnstt":
        kb.button(text="📱 کانفیگ‌های SlipNet (DNS / SSH / Tor)", callback_data=f"acc:slipnet_list:{account_id}")
        kb.button(text="📋 نمایش متنی تمام کانفیگ‌ها در چت", callback_data=f"acc:slp_text_all:{account_id}")
        kb.button(text="📥 دانلود تمام کانفیگ‌ها (.txt)", callback_data=f"acc:slp_dl_all:{account_id}")
        kb.button(text="📷 دریافت بارکد QR تانل", callback_data=f"acc:slp_qr:{account_id}")
        kb.button(text="🔄 تمدید اشتراک", callback_data=f"acc:renew_ask:{account_id}")
        kb.button(text="🚀 ارتقای پلن اشتراک", callback_data=f"acc:upgrade_ask:{account_id}")
        kb.button(text="✏️ تغییر نام دلخواه", callback_data=f"acc:set_name:{account_id}")
        kb.button(text="📁 دسته‌بندی و پوشه", callback_data=f"acc:set_cat:{account_id}")
        kb.button(text="🗑 لغو و حذف کانفیگ (با عودت وجه)", callback_data=f"acc:del_ask:{account_id}")
        kb.button(text="🔄 تغییر رمز عبور اکانت", callback_data=f"acc:reset_id_ask:{account_id}")
        kb.button(text="🔁 تبدیل این اکانت به پروتکل دیگر", callback_data=f"acc:convert_ask:{account_id}")
        kb.button(text="🎁 هدیه دادن این اشتراک", callback_data=f"acc:gift_ask:{account_id}")
        kb.button(text="🔄 بروزرسانی وضعیت", callback_data=f"acc:view:{account_id}")
        kb.button(text="🔙 بازگشت به لیست اکانت‌ها", callback_data="acc:list")
        kb.adjust(1, 1, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1)
    else:
        kb.button(text="🔄 تمدید اشتراک", callback_data=f"acc:renew_ask:{account_id}")
        kb.button(text="🚀 ارتقای پلن اشتراک", callback_data=f"acc:upgrade_ask:{account_id}")
        kb.button(text="✏️ تغییر نام دلخواه", callback_data=f"acc:set_name:{account_id}")
        kb.button(text="📁 دسته‌بندی و پوشه", callback_data=f"acc:set_cat:{account_id}")
        kb.button(text="🗑 لغو و حذف کانفیگ (با عودت وجه)", callback_data=f"acc:del_ask:{account_id}")
        kb.button(text="🔄 تغییر شناسه / رمز عبور", callback_data=f"acc:reset_id_ask:{account_id}")
        kb.button(text="🔁 تبدیل این اکانت به پروتکل دیگر", callback_data=f"acc:convert_ask:{account_id}")
        kb.button(text="🎁 هدیه دادن این اشتراک", callback_data=f"acc:gift_ask:{account_id}")
        kb.button(text="🔄 بروزرسانی وضعیت", callback_data=f"acc:view:{account_id}")
        kb.button(text="🔙 بازگشت به لیست اکانت‌ها", callback_data="acc:list")
        kb.adjust(2, 2, 1, 1, 1, 1, 1, 1)
    return kb.as_markup()
    return kb.as_markup()


# ── کیبوردهای پوشه‌بندی و دسته‌بندی‌های کاربر ──────────────────

def user_categories_menu_keyboard(categories: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """منوی مدیریت دسته‌بندی‌های شخصی کاربر."""
    kb = InlineKeyboardBuilder()
    for cat in categories:
        cnt = cat.get("accounts_count", 0)
        kb.button(
            text=f"📁 {cat.get('name')} ({to_fa(cnt)} کانفیگ)",
            callback_data=f"acc:user_cat_view:{cat.get('id')}",
        )
    kb.button(text="➕ ساخت دسته‌بندی جدید", callback_data="acc:user_cat_new")
    kb.button(text="🔙 بازگشت به اکانت‌های من", callback_data="acc:list")
    kb.adjust(1)
    return kb.as_markup()


def user_category_view_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """مشاهده جزئیات، ویرایش و حذف دسته‌بندی کاربر."""
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ ویرایش نام دسته", callback_data=f"acc:user_cat_rename:{category_id}")
    kb.button(text="🗑 حذف این دسته‌بندی", callback_data=f"acc:user_cat_del_ask:{category_id}")
    kb.button(text="🔙 بازگشت به دسته‌بندی‌ها", callback_data="acc:manage_user_cats")
    kb.adjust(1)
    return kb.as_markup()


def user_cat_delete_confirm_keyboard(category_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 بله، دسته‌بندی حذف شود", callback_data=f"acc:user_cat_del_confirm:{category_id}")
    kb.button(text="❌ انصراف و بازگشت", callback_data=f"acc:user_cat_view:{category_id}")
    kb.adjust(1)
    return kb.as_markup()


def user_assign_category_keyboard(
    account_id: int,
    categories: List[Dict[str, Any]],
    current_cat_id: Optional[int] = None,
) -> InlineKeyboardMarkup:
    """انتخاب دسته برای اختصاص دادن یک اکانت به آن."""
    kb = InlineKeyboardBuilder()
    for cat in categories:
        is_current = (current_cat_id == cat.get("id"))
        check = "✅ " if is_current else "📁 "
        kb.button(
            text=f"{check}{cat.get('name')}",
            callback_data=f"acc:assign_cat:{account_id}:{cat.get('id')}",
        )
    kb.button(text="🚫 بدون دسته‌بندی (حذف از دسته)", callback_data=f"acc:assign_cat:{account_id}:0")
    kb.button(text="➕ ساخت دسته جدید", callback_data=f"acc:user_cat_new_for:{account_id}")
    kb.button(text="🔙 بازگشت به مشخصات اکانت", callback_data=f"acc:view:{account_id}")
    kb.adjust(1)
    return kb.as_markup()


def account_delete_confirm_keyboard(account_id: int) -> InlineKeyboardMarkup:
    """کیبورد تایید حذف اکانت و عودت وجه."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 بله، تایید حذف و واریز به کیف پول", callback_data=f"acc:del_confirm:{account_id}")
    kb.button(text="❌ انصراف و بازگشت", callback_data=f"acc:view:{account_id}")
    kb.adjust(1)
    return kb.as_markup()


def account_gift_select_keyboard(accounts: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """انتخاب اکانت جهت هدیه دادن."""
    kb = InlineKeyboardBuilder()
    for acc in accounts:
        plan = acc.get("plan_name", "اشتراک")
        uname = acc.get("panel_username", "")
        kb.button(text=f"🎁 {plan} ({uname})", callback_data=f"acc:gift_ask:{acc.get('id')}")
    kb.button(text="🔙 بازگشت به اکانت‌های من", callback_data="acc:list")
    kb.adjust(1)
    return kb.as_markup()


def account_gift_confirm_keyboard(account_id: int, target_id: int) -> InlineKeyboardMarkup:
    """تأیید نهایی انتقال و هدیه اکانت."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🎁 بله، هدیه داده شود", callback_data=f"acc:gift_confirm:{account_id}:{target_id}")
    kb.button(text="❌ انصراف", callback_data=f"acc:gift_cancel:{account_id}")
    kb.adjust(1, 1)
    return kb.as_markup()


def config_search_result_keyboard(uid_or_query: str, account_id: Optional[int] = None, is_owner: bool = False) -> InlineKeyboardMarkup:
    """کیبورد نتیجه جستجوی کانفیگ بر اساس UID."""
    kb = InlineKeyboardBuilder()
    if account_id and is_owner:
        kb.button(text="⚡ دریافت کانفیگ‌های تکی", callback_data=f"acc:configs:{account_id}")
        kb.button(text="🎁 هدیه دادن این اشتراک", callback_data=f"acc:gift_ask:{account_id}")
        kb.button(text="📦 پنل کامل این اکانت", callback_data=f"acc:view:{account_id}")
    kb.button(text="🔄 بروزرسانی وضعیت", callback_data=f"acc:refresh_uid:{uid_or_query[:32]}")
    kb.button(text="🔍 استعلام کانفیگ دیگر", callback_data="acc:search_uid")
    kb.button(text="🔙 بازگشت به منوی اصلی", callback_data="menu:home")
    kb.adjust(1)
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


# ── تمدید و ارتقای اکانت ──────────────────────────────────────

def account_renew_plans_keyboard(
    account_id: int,
    plans: List[Dict[str, Any]],
    current_plan_name: str = "",
) -> InlineKeyboardMarkup:
    """کیبورد انتخاب پلن جهت تمدید اشتراک."""
    kb = InlineKeyboardBuilder()
    for p in plans:
        if p.get("is_active"):
            is_cur = (p.get("name") == current_plan_name)
            prefix = "⭐️ " if is_cur else "⚡ "
            suffix = " (پلن فعلی)" if is_cur else ""
            txt = f"{prefix}{p.get('name')}{suffix} ({p.get('traffic_gb')} GB / {p.get('duration_days')} روز) — {to_toman(p.get('price', 0))}"
            kb.button(text=txt, callback_data=f"acc:renew_sel:{account_id}:{p.get('id')}")
    kb.button(text="🔙 بازگشت به مشخصات اکانت", callback_data=f"acc:view:{account_id}")
    kb.adjust(1)
    return kb.as_markup()


def account_renew_confirm_keyboard(account_id: int, plan_id: int) -> InlineKeyboardMarkup:
    """کیبورد تأیید نهایی تمدید اشتراک."""
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ تأیید و پرداخت تمدید از کیف پول", callback_data=f"acc:renew_exec:{account_id}:{plan_id}")
    kb.button(text="🔙 بازگشت به لیست پلن‌ها", callback_data=f"acc:renew_ask:{account_id}")
    kb.adjust(1)
    return kb.as_markup()


def account_upgrade_plans_keyboard(
    account_id: int,
    remaining_value: int,
    plans: List[Dict[str, Any]],
    current_plan_name: str = "",
) -> InlineKeyboardMarkup:
    """کیبورد انتخاب پلن مقصد جهت ارتقای اکانت با کسر مصرف قبلی."""
    kb = InlineKeyboardBuilder()
    for p in plans:
        if p.get("is_active"):
            price = p.get("price", 0)
            upgrade_cost = max(0, price - remaining_value)
            is_cur = (p.get("name") == current_plan_name)
            prefix = "⭐️ " if is_cur else "🚀 "
            suffix = " (پلن فعلی)" if is_cur else ""
            cost_txt = f"+ {to_toman(upgrade_cost)}" if upgrade_cost > 0 else "بدون هزینه (رایگان)"
            txt = f"{prefix}{p.get('name')}{suffix} ({p.get('traffic_gb')}GB / {p.get('duration_days')}روز) — {cost_txt}"
            kb.button(text=txt, callback_data=f"acc:upg_sel:{account_id}:{p.get('id')}")
    kb.button(text="🔙 بازگشت به مشخصات اکانت", callback_data=f"acc:view:{account_id}")
    kb.adjust(1)
    return kb.as_markup()


def account_upgrade_confirm_keyboard(account_id: int, plan_id: int) -> InlineKeyboardMarkup:
    """کیبورد تأیید نهایی ارتقای اشتراک."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 تأیید نهایی و ارتقای اکانت", callback_data=f"acc:upg_exec:{account_id}:{plan_id}")
    kb.button(text="🔙 بازگشت به لیست پلن‌ها", callback_data=f"acc:upgrade_ask:{account_id}")
    kb.adjust(1)
    return kb.as_markup()


def build_tutorials_main_keyboard() -> InlineKeyboardMarkup:
    """منوی اصلی راهنماهای اتصال."""
    kb = InlineKeyboardBuilder()
    kb.button(text="📱 راهنمای اندروید (Android)", callback_data="tut:view:android")
    kb.button(text="🍏 راهنمای آیفون / آیپد (iOS)", callback_data="tut:view:ios")
    kb.button(text="💻 راهنمای ویندوز (Windows)", callback_data="tut:view:windows")
    kb.button(text="🛡️ آموزش AmneziaWG (ضد فیلتر)", callback_data="tut:view:amneziawg")
    kb.button(text="⚡ آموزش اتصال WireGuard", callback_data="tut:view:wireguard")
    kb.button(text="🛡️ آموزش Cisco AnyConnect", callback_data="tut:view:cisco")
    kb.button(text="🔒 آموزش OpenVPN", callback_data="tut:view:openvpn")
    kb.button(text="☁️ آموزش گوگل اسکریپت (GAS)", callback_data="tut:view:gas")
    kb.button(text="⚡ آموزش SSH Tunnel", callback_data="tut:view:ssh")
    kb.button(text="🌐 آموزش تانل SlowDNS", callback_data="tut:view:slowdns")
    kb.button(text="🔙 بستن راهنما", callback_data="tut:close")
    kb.adjust(2, 2, 2, 2, 2, 1)
    return kb.as_markup()


def build_tutorial_back_keyboard(tut_key: str = "", dl_links: Optional[Dict[str, str]] = None) -> InlineKeyboardMarkup:
    from utils.tutorials import CLIENT_DOWNLOADS
    dls = dl_links or CLIENT_DOWNLOADS
    kb = InlineKeyboardBuilder()

    if tut_key == "android":
        kb.button(text="📥 دانلود v2rayNG", url=dls.get("v2rayng_google_play", CLIENT_DOWNLOADS["v2rayng_google_play"]))
        kb.button(text="🛡️ دانلود AmneziaWG", url=dls.get("amnezia_android", CLIENT_DOWNLOADS.get("amnezia_android", "https://play.google.com/store/apps/details?id=org.amnezia.awg")))
        kb.button(text="📥 دانلود WireGuard", url=dls.get("wireguard_android", CLIENT_DOWNLOADS["wireguard_android"]))
        kb.button(text="📥 دانلود سیسکو (Google Play)", url=dls.get("cisco_android", CLIENT_DOWNLOADS["cisco_android"]))
        kb.button(text="📥 دانلود OpenVPN (Google Play)", url=dls.get("openvpn_android", CLIENT_DOWNLOADS["openvpn_android"]))
    elif tut_key == "ios":
        kb.button(text="📥 دانلود Streisand (App Store)", url=dls.get("streisand_ios", CLIENT_DOWNLOADS["streisand_ios"]))
        kb.button(text="🛡️ دانلود AmneziaWG (App Store)", url=dls.get("amnezia_ios", CLIENT_DOWNLOADS.get("amnezia_ios", "https://apps.apple.com/app/amneziawg/id6478942364")))
        kb.button(text="📥 دانلود WireGuard (App Store)", url=dls.get("wireguard_ios", CLIENT_DOWNLOADS["wireguard_ios"]))
        kb.button(text="📥 دانلود V2Box (App Store)", url=dls.get("v2box_ios", CLIENT_DOWNLOADS["v2box_ios"]))
        kb.button(text="📥 دانلود سیسکو (App Store)", url=dls.get("cisco_ios", CLIENT_DOWNLOADS["cisco_ios"]))
        kb.button(text="📥 دانلود OpenVPN (App Store)", url=dls.get("openvpn_ios", CLIENT_DOWNLOADS["openvpn_ios"]))
    elif tut_key == "windows":
        kb.button(text="📥 دانلود v2rayN", url=dls.get("v2rayn_windows", CLIENT_DOWNLOADS["v2rayn_windows"]))
        kb.button(text="🛡️ دانلود AmneziaWG ویندوز", url=dls.get("amnezia_windows", CLIENT_DOWNLOADS.get("amnezia_windows", "https://github.com/amnezia-vpn/amneziawg-windows-client/releases")))
        kb.button(text="📥 دانلود WireGuard ویندوز", url=dls.get("wireguard_windows", CLIENT_DOWNLOADS["wireguard_windows"]))
        kb.button(text="📥 دانلود سیسکو ویندوز", url=dls.get("cisco_windows", CLIENT_DOWNLOADS["cisco_windows"]))
        kb.button(text="📥 دانلود OpenVPN ویندوز", url=dls.get("openvpn_windows", CLIENT_DOWNLOADS["openvpn_windows"]))
    elif tut_key == "amneziawg":
        kb.button(text="🛡️ AmneziaWG اندروید", url=dls.get("amnezia_android", "https://play.google.com/store/apps/details?id=org.amnezia.awg"))
        kb.button(text="🛡️ AmneziaWG آیفون", url=dls.get("amnezia_ios", "https://apps.apple.com/app/amneziawg/id6478942364"))
        kb.button(text="🛡️ AmneziaWG ویندوز", url=dls.get("amnezia_windows", "https://github.com/amnezia-vpn/amneziawg-windows-client/releases"))
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
    kb.button(text="🛡️ وایرگارد پیشرفته (AmneziaWG)", callback_data="app:proto:amneziawg")
    kb.button(text="⚡ پروتکل وایرگارد (WireGuard)", callback_data="app:proto:wireguard")
    kb.button(text="🛡️ پروتکل‌های سیسکو و سیستمی", callback_data="app:proto:standard")
    kb.button(text="🌐 تانل ضد فیلتر SlowDNS", callback_data="app:proto:dnstt")
    kb.button(text="☁️ گوگل اسکریپت و کلودفلر (GAS)", callback_data="app:proto:gas")

    kb.button(text="🔙 بازگشت به منوی اصلی", callback_data="menu:home")
    kb.adjust(2, 2, 2, 2, 1)
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
    elif proto_key == "amneziawg":
        kb.button(text="🛡️ AmneziaWG اندروید", url=dls.get("amnezia_android", "https://play.google.com/store/apps/details?id=org.amnezia.awg"))
        kb.button(text="🛡️ AmneziaWG آیفون", url=dls.get("amnezia_ios", "https://apps.apple.com/app/amneziawg/id6478942364"))
        kb.button(text="🛡️ AmneziaWG ویندوز", url=dls.get("amnezia_windows", "https://github.com/amnezia-vpn/amneziawg-windows-client/releases"))
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


def wireguard_multiport_keyboard(account_id: int, configs: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """کیبورد انتخاب پورت‌های مختلف وایرگارد (چند پورته)."""
    kb = InlineKeyboardBuilder()
    for cfg in configs:
        port = cfg.get("port")
        is_main = cfg.get("is_main", False)
        txt = f"⚡ پورت {to_fa(port)} (اصلی)" if is_main else f"🔹 پورت {to_fa(port)}"
        kb.button(text=txt, callback_data=f"acc:wg_p_view:{account_id}:{port}")

    kb.button(text="📦 دانلود تمام پورت‌ها (فایل ZIP)", callback_data=f"acc:dl_wg_zip:{account_id}")
    kb.button(text="🔙 بازگشت به مشخصات اکانت", callback_data=f"acc:view:{account_id}")

    # چینش دوتایی برای پورت‌ها و تکی برای دکمه‌های پایانی
    num_ports = len(configs)
    ports_layout = [2] * (num_ports // 2)
    if num_ports % 2 != 0:
        ports_layout.append(1)
    layout = ports_layout + [1, 1]
    kb.adjust(*layout)
    return kb.as_markup()


def wireguard_single_port_keyboard(account_id: int, port: int) -> InlineKeyboardMarkup:
    """کیبورد عملیات روی یک پورت خاص وایرگارد."""
    kb = InlineKeyboardBuilder()
    kb.button(text="📥 دانلود فایل .conf این پورت", callback_data=f"acc:dl_wg_p_conf:{account_id}:{port}")
    kb.button(text="📷 بارکد QR این پورت", callback_data=f"acc:dl_wg_p_qr:{account_id}:{port}")
    kb.button(text="📋 مشاهده متن کانفیگ", callback_data=f"acc:dl_wg_p_txt:{account_id}:{port}")
    kb.button(text="🔙 بازگشت به لیست پورت‌ها", callback_data=f"acc:wg_multiport:{account_id}")
    kb.adjust(2, 1, 1)
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
    kb.button(text="📡 ارسال خودکار کانفیگ به کانال", callback_data="adm:autochannel")
    kb.button(text="🔒 عضویت اجباری و قفل سین", callback_data="adm:fsub_menu")
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
    kb.adjust(1, 2, 2, 2, 2, 2, 2, 2, 2, 1)
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
    kb.button(text="⏳ دسته‌بندی پلن‌ها بر اساس زمان (۱ و ۲ و ۳ ماهه)", callback_data="adm:plans_by_dur:0")
    layout.append(1)
    kb.button(text="📊 تفکیک کانفیگ‌های فعال بر اساس مدت زمان", callback_data="adm:accs_by_dur")
    layout.append(1)
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


def admin_plans_list_keyboard(plans: List[Dict[str, Any]], cat_key: str, selected_dur: int = 0) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    # تب‌های فیلتر زمان: ۱ ماهه، ۲ ماهه، ۳ ماهه، همه
    dur_filters = [
        (0, "🌟 همه"),
        (30, "۱ ماهه"),
        (60, "۲ ماهه"),
        (90, "۳ ماهه"),
    ]
    for dur_val, dur_title in dur_filters:
        txt = f"✅ {dur_title}" if selected_dur == dur_val else dur_title
        kb.button(text=txt, callback_data=f"adm:plans_list:{cat_key}:{dur_val}")

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

    layout = [4] + [1] * len(plans) + [1, 1]
    kb.adjust(*layout)
    return kb.as_markup()


def admin_plans_duration_menu_keyboard(duration_summaries: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """کیبورد منوی انتخاب بازه زمانی پلن‌ها در پنل مدیریت."""
    kb = InlineKeyboardBuilder()
    for item in duration_summaries:
        dur = item.get("duration_days", 30)
        cnt = item.get("count", 0)
        lbl = duration_label(dur)
        kb.button(
            text=f"📅 پلن‌های {lbl} — ({to_fa(cnt)} پلن)",
            callback_data=f"adm:plans_by_dur:{dur}:1",
        )
    kb.button(text="🔙 بازگشت به دسته‌بندی‌ها", callback_data="adm:categories")
    kb.adjust(1)
    return kb.as_markup()


def admin_plans_by_duration_keyboard(
    plans: List[Dict[str, Any]],
    selected_dur: int = 30,
    page: int = 1,
    per_page: int = 10,
    all_durs: Optional[List[int]] = None,
) -> InlineKeyboardMarkup:
    """کیبورد نمایش پلن‌های یک بازه زمانی خاص با قابلیت صفحه‌بندی و سوییچ سریع بازه."""
    kb = InlineKeyboardBuilder()

    dur_list = all_durs or [30, 60, 90]
    for d in dur_list:
        lbl = f"{d // 30} ماهه" if d % 30 == 0 else f"{d} روزه"
        btn_txt = f"✅ {lbl}" if d == selected_dur else f"📅 {lbl}"
        kb.button(text=btn_txt, callback_data=f"adm:plans_by_dur:{d}:1")

    total_plans = len(plans)
    total_pages = max(1, (total_plans + per_page - 1) // per_page)
    cur_page = max(1, min(page, total_pages))

    start_idx = (cur_page - 1) * per_page
    end_idx = start_idx + per_page
    page_plans = plans[start_idx:end_idx]

    for plan in page_plans:
        st = "🟢" if plan.get("is_active") else "🔴"
        name = plan.get("name", "پلن")
        pr = to_toman(plan.get("price", 0))
        cat = plan.get("category_key", "")
        kb.button(
            text=f"{st} [{cat}] {name} — {pr}",
            callback_data=f"adm:plan_view:{plan.get('id')}",
        )

    # دکمه‌های ناوبری صفحه‌بندی
    nav_row_count = 0
    if cur_page > 1:
        kb.button(text="⬅️ صفحه قبل", callback_data=f"adm:plans_by_dur:{selected_dur}:{cur_page - 1}")
        nav_row_count += 1
    kb.button(text=f"📄 {to_fa(cur_page)} از {to_fa(total_pages)}", callback_data="noop")
    nav_row_count += 1
    if cur_page < total_pages:
        kb.button(text="صفحه بعد ➡️", callback_data=f"adm:plans_by_dur:{selected_dur}:{cur_page + 1}")
        nav_row_count += 1

    kb.button(text="⏳ بازگشت به منوی زمان‌ها", callback_data="adm:plans_by_dur:0")
    kb.button(text="🔙 بازگشت به دسته‌بندی‌ها", callback_data="adm:categories")

    layout = [len(dur_list)] + [1] * len(page_plans) + [nav_row_count] + [1, 1]
    kb.adjust(*layout)
    return kb.as_markup()


def admin_plan_detail_keyboard(plan_id: int, cat_key: str, is_active: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ ویرایش مشخصات پلن", callback_data=f"adm:plan_edit:{plan_id}")
    toggle_txt = "🔴 غیرفعال‌سازی پلن" if is_active else "🟢 فعال‌سازی پلن"
    kb.button(text=toggle_txt, callback_data=f"adm:plan_toggle:{plan_id}")
    kb.button(text="🗑 حذف پلن", callback_data=f"adm:plan_del:{plan_id}")
    kb.button(text="🔙 بازگشت به پلن‌ها", callback_data=f"adm:plans_list:{cat_key}")
    kb.adjust(1)
    return kb.as_markup()


def admin_plan_edit_keyboard(plan_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🏷 ویرایش عنوان و نام پلن", callback_data=f"adm:plan_edit_field:{plan_id}:name")
    kb.button(text="📶 ویرایش سقف حجم ترافیک (GB)", callback_data=f"adm:plan_edit_field:{plan_id}:traffic")
    kb.button(text="⏱ ویرایش مدت زمان اعتبار (روز)", callback_data=f"adm:plan_edit_field:{plan_id}:days")
    kb.button(text="💰 ویرایش قیمت فروش (تومان)", callback_data=f"adm:plan_edit_field:{plan_id}:price")
    kb.button(text="🔙 بازگشت به مشخصات پلن", callback_data=f"adm:plan_view:{plan_id}")
    kb.adjust(1)
    return kb.as_markup()


# ── سایر کیبوردهای مدیریت و تست ──────────────────────────────

def trial_select_keyboard() -> InlineKeyboardMarkup:
    """کیبورد انتخاب نوع یا پروتکل اکانت تستی برای کاربر."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🌟 پکیج جامع (تست کلیه پروتکل‌ها به صورت یکجا)", callback_data="trial:mode:all")
    kb.button(text="🛡️ ۱. وایرگارد پیشرفته ضد فیلتر (AmneziaWG)", callback_data="trial:mode:amneziawg")
    kb.button(text="🚀 ۲. کانفیگ‌های Sing-box و V2Ray", callback_data="trial:mode:singbox")
    kb.button(text="⚡ ۳. وایرگارد معمولی (WireGuard)", callback_data="trial:mode:wireguard")
    kb.button(text="🛡️ ۴. سیسکو، اوپن‌وی‌پی‌ان و L2TP", callback_data="trial:mode:system_l2tp")
    kb.button(text="🌐 ۵. تانل ضد فیلتر DNS (SlipNet)", callback_data="trial:mode:dnstt")
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


# ── کیبوردهای ارسال خودکار کانفیگ به کانال (Auto Channel Post) ────

def admin_auto_channel_keyboard(conf: Dict[str, Any]) -> InlineKeyboardMarkup:
    """منوی اصلی تنظیمات ارسال خودکار کانفیگ به کانال مقصد."""
    kb = InlineKeyboardBuilder()

    is_on = conf.get("is_enabled", False)
    toggle_icon = "🟢 روشن (ارسال فعال)" if is_on else "🔴 خاموش (غیرفعال)"
    kb.button(text=f"وضعیت ارسال خودکار: {toggle_icon}", callback_data="adm:autochannel:toggle")

    ch_id = conf.get("channel_id") or "تنظیم نشده"
    kb.button(text=f"📢 کانال مقصد: {ch_id}", callback_data="adm:autochannel:set_target")
    kb.button(text="🔍 بررسی دسترسی ربات در کانال", callback_data="adm:autochannel:test_admin")

    # پروتکل انتخابی
    from utils.channel_poster import PROTO_TITLES
    proto_key = conf.get("protocol", "singbox")
    proto_name = PROTO_TITLES.get(proto_key, "Sing-box (Base64)")
    kb.button(text=f"🌐 پروتکل ارسالی: {proto_name}", callback_data="adm:autochannel:proto")

    days_cnt = len(conf.get("days_list", []))
    kb.button(text=f"📅 روزهای ارسال ({days_cnt} روز)", callback_data="adm:autochannel:days")

    times_str = conf.get("times_str") or "تنظیم نشده"
    kb.button(text=f"⏰ ساعات ارسال ({times_str})", callback_data="adm:autochannel:times")

    traffic = conf.get("traffic_gb", 1.0)
    duration = conf.get("duration_days", 1)
    kb.button(text=f"⚡ مشخصات کانفیگ: {traffic}GB / {duration} روز", callback_data="adm:autochannel:specs")

    qr_on = conf.get("send_qr", True)
    qr_icon = "🟢 بله (همراه با عکس QR)" if qr_on else "🔴 خیر (فقط متنی)"
    kb.button(text=f"📷 ارسال بارکد QR: {qr_icon}", callback_data="adm:autochannel:toggle_qr")

    has_custom_cap = bool(conf.get("caption", "").strip())
    cap_label = "📝 ویرایش کپشن (سفارشی)" if has_custom_cap else "📝 ویرایش متن کپشن پست"
    kb.button(text=cap_label, callback_data="adm:autochannel:caption")

    kb.button(text="🚀 ارسال فوری یک کانفیگ تست به کانال", callback_data="adm:autochannel:send_now")
    kb.button(text="🔙 بازگشت به منوی مدیریت", callback_data="adm:main")

    kb.adjust(1, 1, 1, 1, 2, 1, 1, 1, 1, 1)
    return kb.as_markup()


def admin_auto_channel_proto_keyboard(current_proto: str) -> InlineKeyboardMarkup:
    """کیبورد انتخاب پروتکل ارسالی به کانال."""
    kb = InlineKeyboardBuilder()
    protos = [
        ("singbox", "🚀 ۱. سوئیت Sing-box و V2Ray (ساب Base64)"),
        ("slipnet", "📱 ۲. تانل ضد فیلتر SlipNet (DNS / SSH / Tor)"),
        ("system_l2tp", "🛡️ ۳. پروتکل‌های استاندارد (Cisco / OpenVPN / L2TP)"),
        ("all", "🎁 ۴. پکیج کامل همگانی (ترکیبی)"),
    ]
    for key, label in protos:
        icon = "✅" if current_proto == key else "▫️"
        kb.button(text=f"{icon} {label}", callback_data=f"adm:autochannel:set_proto:{key}")
    kb.button(text="🔙 بازگشت به تنظیمات ارسال خودکار", callback_data="adm:autochannel")
    kb.adjust(1)
    return kb.as_markup()


def admin_auto_channel_days_keyboard(days_list: List[str]) -> InlineKeyboardMarkup:
    """کیبورد انتخاب روزهای هفته جهت ارسال خودکار کانفیگ."""
    kb = InlineKeyboardBuilder()

    all_days = [
        ("sat", "شنبه"),
        ("sun", "یک‌شنبه"),
        ("mon", "دوشنبه"),
        ("tue", "سه‌شنبه"),
        ("wed", "چهارشنبه"),
        ("thu", "پنج‌شنبه"),
        ("fri", "جمعه"),
    ]

    for code, name in all_days:
        status_icon = "✅" if code in days_list else "❌"
        kb.button(text=f"{status_icon} {name}", callback_data=f"adm:autochannel:toggle_day:{code}")

    kb.button(text="✅ انتخاب همه روزها", callback_data="adm:autochannel:days_all")
    kb.button(text="❌ پاک کردن همه", callback_data="adm:autochannel:days_none")
    kb.button(text="🔙 بازگشت به تنظیمات ارسال خودکار", callback_data="adm:autochannel")

    # ۲ تایی برای روزها و سپس دکمه‌های کنترلی
    kb.adjust(2, 2, 2, 1, 2, 1)
    return kb.as_markup()


def admin_auto_channel_caption_keyboard(has_custom: bool) -> InlineKeyboardMarkup:
    """عملیات تنظیم کپشن پست کانال."""
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ نوشتن کپشن سفارشی جدید", callback_data="adm:autochannel:caption_edit")
    if has_custom:
        kb.button(text="🔄 بازنشانی به متن استاندارد پیش‌فرض", callback_data="adm:autochannel:caption_reset")
    kb.button(text="🔙 بازگشت به تنظیمات ارسال خودکار", callback_data="adm:autochannel")
    kb.adjust(1)
    return kb.as_markup()


# ── کیبوردهای عضویت اجباری و قفل سین (Force Join & Seen Lock) ────

def admin_fsub_main_keyboard(is_fsub_on: bool, is_seen_on: bool, channels_count: int) -> InlineKeyboardMarkup:
    """منوی اصلی مدیریت عضویت اجباری و قفل سین."""
    kb = InlineKeyboardBuilder()

    fsub_icon = "🟢 روشن (فعال)" if is_fsub_on else "🔴 خاموش (غیرفعال)"
    kb.button(text=f"قفل عضویت اجباری: {fsub_icon}", callback_data="adm:fsub:toggle")

    kb.button(text=f"📢 کانال‌های عضویت اجباری ({channels_count} کانال)", callback_data="adm:fsub:channels")
    kb.button(text="➕ افزودن کانال اجباری جدید", callback_data="adm:fsub:add_channel")

    seen_icon = "🟢 روشن (فعال)" if is_seen_on else "🔴 خاموش (غیرفعال)"
    kb.button(text=f"👁 تنظیمات قفل سین / اسپانسر: {seen_icon}", callback_data="adm:seen:menu")

    kb.button(text="🔙 بازگشت به منوی مدیریت", callback_data="adm:main")
    kb.adjust(1, 1, 1, 1, 1)
    return kb.as_markup()


def admin_fsub_channels_list_keyboard(channels: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """نمایش لیست کانال‌های عضویت اجباری به همراه دکمه افزودن."""
    kb = InlineKeyboardBuilder()

    for ch in channels:
        ch_id = ch.get("id")
        title = ch.get("title", "کانال")
        is_active = ch.get("is_active", 1) == 1
        status_icon = "🟢" if is_active else "🔴"
        target = ch.get("channel_id", "")
        kb.button(text=f"{status_icon} {title} ({target})", callback_data=f"adm:fsub:view_ch:{ch_id}")

    kb.button(text="➕ افزودن کانال جدید", callback_data="adm:fsub:add_channel")
    kb.button(text="🔙 بازگشت به منوی عضویت اجباری", callback_data="adm:fsub_menu")
    kb.adjust(1)
    return kb.as_markup()


def admin_fsub_channel_detail_keyboard(channel_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """جزئیات و عملیات روی یک کانال عضویت اجباری."""
    kb = InlineKeyboardBuilder()

    toggle_txt = "🔴 غیرفعال‌سازی این کانال" if is_active else "🟢 فعال‌سازی مجدد این کانال"
    kb.button(text=toggle_txt, callback_data=f"adm:fsub:toggle_ch:{channel_id}")
    kb.button(text="🔍 تست دسترسی و ادمین بودن ربات", callback_data=f"adm:fsub:test_ch:{channel_id}")
    kb.button(text="🗑 حذف قطعی این کانال", callback_data=f"adm:fsub:del_ch:{channel_id}")
    kb.button(text="🔙 بازگشت به لیست کانال‌ها", callback_data="adm:fsub:channels")
    kb.adjust(1)
    return kb.as_markup()


def admin_seen_lock_keyboard(seen_data: Dict[str, Any]) -> InlineKeyboardMarkup:
    """منوی تنظیمات قفل سین پست تلگرام."""
    kb = InlineKeyboardBuilder()

    is_on = seen_data.get("is_enabled", False)
    toggle_icon = "🟢 روشن (قفل فعال)" if is_on else "🔴 خاموش (غیرفعال)"
    kb.button(text=f"وضعیت قفل سین: {toggle_icon}", callback_data="adm:seen:toggle")

    post_url = seen_data.get("post_url") or "تنظیم نشده"
    if len(post_url) > 30:
        post_url = post_url[:27] + "..."
    kb.button(text=f"🔗 لینک پست هدف: {post_url}", callback_data="adm:seen:set_url")

    kb.button(text="📝 ویرایش متن راهنمای قفل سین", callback_data="adm:seen:set_text")
    kb.button(text="🔄 بازنشانی متن به پیش‌فرض", callback_data="adm:seen:reset_text")
    kb.button(text="🔙 بازگشت به منوی عضویت اجباری", callback_data="adm:fsub_menu")

    kb.adjust(1)
    return kb.as_markup()


