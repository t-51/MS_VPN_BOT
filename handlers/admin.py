"""هندلر جامع پنل مدیریت (Admin Panel) ربات MS_VPN_BOT.

شامل:
  1) مدیریت تفکیک‌شده پروتکل‌های سرور (Sing-box/V2Ray، سیستمی L2TP/IKEv2، تانل DNS)
  2) مدیریت کامل دسته‌بندی‌ها و ایجاد دسته‌بندی جدید برای فروشگاه
  3) مدیریت پلن‌های هر دسته‌بندی (افزودن پلن، حذف و فعال/غیرفعال‌سازی)
  4) آمار و تحلیل فروش حرفه‌ای و مانیتورینگ منابع سخت‌افزاری MHPanel
  5) بررسی و تأیید/رد واریزی‌ها و فیش‌های کارت‌به‌کارت
  6) تنظیمات اکانت تستی و رفرال
  7) پاسخ‌گویی به تیکت‌های پشتیبانی
"""
import re
import secrets
import logging
import os
import asyncio
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, FSInputFile

from api import panel_api
from config import settings
from db import database
from utils.cert_manager import (
    get_ovpn_content,
    CISCO_CA_PATH,
    IKEV2_CA_PATH,
    SSTP_CA_PATH,
)
from keyboards.inline import (
    admin_main_keyboard,
    admin_server_configs_keyboard,
    admin_system_l2tp_keyboard,
    admin_categories_list_keyboard,
    admin_category_detail_keyboard,
    admin_cat_delete_confirm_keyboard,
    admin_category_proto_select_keyboard,
    admin_plans_list_keyboard,
    admin_plan_detail_keyboard,
    admin_bank_cards_list_keyboard,
    admin_bank_card_detail_keyboard,
    admin_broadcast_confirm_keyboard,
    admin_trial_keyboard,
    admin_referral_keyboard,
    admin_tx_keyboard,
    admin_ticket_keyboard,
    admin_users_menu_keyboard,
    admin_user_card_keyboard,
    admin_manage_admins_keyboard,
    admin_tutorials_list_keyboard,
    admin_tutorial_detail_keyboard,
    admin_downloads_list_keyboard,
    admin_download_detail_keyboard,
    admin_notifications_keyboard,
)
from keyboards.reply import cancel_keyboard, get_main_keyboard
from utils import trial_manager, notifier
from utils.tutorials import (
    TUTORIAL_TITLES,
    CLIENT_DOWNLOAD_TITLES,
    get_tutorial_text,
    set_tutorial_text,
    reset_tutorial_text,
    is_tutorial_customized,
    get_download_url,
    set_download_url,
    reset_download_url,
    is_download_customized,
)
from states.forms import (
    AdminActionStates,
    AdminCategoryStates,
    AdminPlanStates,
    AdminBroadcastStates,
    AdminCardStates,
    AdminUserStates,
    AdminManageStates,
    AdminTutorialStates,
)
from utils.formatters import (
    format_sales_stats,
    format_top_referrers,
    format_server_settings_info,
)
from utils.helpers import to_fa, to_toman

router = Router(name="admin")
logger = logging.getLogger(__name__)


def _is_admin(event: types.Message | types.CallbackQuery) -> bool:
    return settings.is_admin(event.from_user.id)


# ── ورود به پنل مدیریت ──────────────────────────────────────

@router.message(Command("admin"))
@router.message(F.text == "👑 پنل مدیریت")
async def show_admin_panel(message: types.Message):
    if not _is_admin(message):
        return await message.answer("⛔ شما به این بخش دسترسی ندارید.")

    welcome_text = (
        "👑 <b>به کنترل پنل مدیریت MS VPN خوش آمدید!</b>\n\n"
        "از طریق گزینه‌های زیر می‌توانید بر پروتکل‌های سرور، دسته‌بندی‌های فروشگاه، "
        "پلن‌ها، فیش‌های واریزی و آمار فروش نظارت و مدیریت کامل داشته باشید:"
    )
    await message.answer(welcome_text, reply_markup=admin_main_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "adm:main")
async def cb_admin_main(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    text = "👑 <b>منوی اصلی کنترل پنل مدیریت:</b>"
    await callback.message.edit_text(text, reply_markup=admin_main_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "adm:close")
async def cb_admin_close(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer(
        "پنل مدیریت بسته شد. از منوی زیر می‌توانید به کار با ربات ادامه دهید:",
        reply_markup=get_main_keyboard(True),
    )
    await callback.answer()


# ──────────────────────────────────────────────────────────────
#  مدیریت تفکیک‌شده پروتکل‌ها و کانفیگ سرور
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:server_configs")
async def cb_admin_server_configs_menu(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    text = (
        "⚙️ <b>مدیریت کانفیگ و پروتکل‌های سرور MHPanel</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "پروتکل‌های سرور به سه بخش مجزا و مستقل تفکیک شده‌اند:\n\n"
        "⚡ <b>۱. هسته سینگ‌باکس و V2Ray:</b> مدیریت ۲۳ اینباند Reality, VMess, Trojan, Hysteria 2 و TUIC.\n\n"
        "🛡️ <b>۲. پروتکل‌های استاندارد سیستمی:</b> مدیریت L2TP, IKEv2, Cisco AnyConnect و SSTP و تنظیم IPsec PSK.\n\n"
        "🌐 <b>۳. تانل‌های اضطراری DNS:</b> سرورهای SlowDNS / DNSTT، دامنه‌های نیم‌سرور و کلید عمومی.\n\n"
        "جهت مشاهده و تنظیم هر بخش، گزینه مورد نظر را انتخاب فرمایید:"
    )
    await callback.message.edit_text(text, reply_markup=admin_server_configs_keyboard(), parse_mode="HTML")
    await callback.answer()


# ── بخش ۱: Sing-box & V2Ray ──
@router.callback_query(F.data == "adm:srv_proto:singbox")
async def cb_admin_proto_singbox(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    await callback.answer("در حال دریافت وضعیت هسته Sing-box...")
    sys_status = await panel_api.get_system_status()
    users_res = await panel_api.get_all_users()
    users_cnt = users_res.get("count", 0) if users_res.get("success") else 0

    protos = sys_status.get("vpn_protocols", {}) if sys_status.get("success") else {}
    sb = protos.get("singbox", {})
    active_conn = sb.get("connections", 0)
    dom = await database.get_setting("server_domain", settings.SERVER_DOMAIN)

    text = (
        "⚡ <b>مشخصات هسته Sing-box & V2Ray Suite</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"▫️ وضعیت هسته: <b>{'🟢 فعال و پایدار' if sb.get('active', True) else '🔴 غیرفعال'}</b>\n"
        f"▫️ پورت اصلی هسته: <code>20443</code>\n"
        f"▫️ پروتکل‌های پرسرعت QUIC: Hysteria 2 (پورت ۱۱۴۴۳) | TUIC v5 (پورت ۷۴۴۳)\n"
        f"▫️ پروتکل‌های استاندارد TLS: Trojan (پورت ۱۲۴۴۳) | NaiveProxy (پورت ۱۳۴۴۳)\n"
        f"▫️ کل کاربران تعریف‌شده در هسته: <b>{to_fa(users_cnt)} کاربر</b>\n"
        f"▫️ اتصالات فعال بلادرنگ: <b>{to_fa(active_conn)} کاربر آنلاین</b>\n"
        f"▫️ دامنه سابسکریپشن هوشمند: <code>{dom}</code>\n"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 تست و بروزرسانی وضعیت", callback_data="adm:srv_proto:singbox")
    kb.button(text="🔙 بازگشت به پروتکل‌ها", callback_data="adm:server_configs")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")


# ── بخش ۲: پروتکل‌های استاندارد (Cisco, OpenVPN, L2TP, IKEv2, SSH, SSTP) ──
@router.callback_query(F.data == "adm:srv_proto:system")
async def cb_admin_proto_system(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    srv_ip = await database.get_setting("server_ip", settings.SERVER_IP)
    psk = await database.get_setting("ipsec_psk", settings.IPSEC_PSK)

    text = (
        "🛡️ <b>پروتکل‌های استاندارد و سیستمی</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "کاربران با خرید اکانت استاندارد، به طور همزمان به ۶ پروتکل زیر با یک یوزر و پسورد متصل می‌شوند:\n\n"
        f"▫️ <b>Cisco AnyConnect (ocserv):</b> 🟢 فعال (پورت ۱۰۴۴۳ TCP/UDP)\n"
        f"▫️ <b>OpenVPN Server:</b> 🟢 فعال (پورت ۱۱۹۴ UDP و TCP) + Speeder ۴۰۰۰\n"
        f"▫️ <b>L2TP / IPsec:</b> 🟢 فعال (پورت ۱۷۰۱ UDP | کلید PSK: <code>{psk}</code>)\n"
        f"▫️ <b>IKEv2:</b> 🟢 فعال (پورت‌های ۵۰۰ و ۴۵۰۰ UDP)\n"
        f"▫️ <b>SSH Tunnel:</b> 🟢 فعال (پورت‌های ۲۲ و ۲۰۵۳ TCP)\n"
        f"▫️ <b>SSTP Server:</b> 🟢 فعال (پورت ۴۴۳ TCP)\n\n"
        f"🌐 <b>آی‌پی سرور اصلی (Server IP):</b> <code>{srv_ip}</code>\n"
        f"🔐 <b>کلید Pre-Shared Key (PSK):</b> <code>{psk}</code>\n\n"
        "جهت تست و دریافت فایل‌های اتصال یا تغییر مقادیر سرور، از دکمه‌های زیر استفاده فرمایید:"
    )
    await callback.message.edit_text(text, reply_markup=admin_system_l2tp_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "adm:dl_test_ovpn")
async def cb_admin_dl_test_ovpn(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    srv_ip = await database.get_setting("server_ip", settings.SERVER_IP)
    ovpn_data = get_ovpn_content(server_ip=srv_ip)
    doc = BufferedInputFile(ovpn_data.encode("utf-8"), filename="MHPanel_OpenVPN_Master.ovpn")
    caption = (
        "🔒 <b>فایل کانفیگ مستر OpenVPN سرور</b>\n\n"
        f"🌐 آدرس سرور: <code>{srv_ip}:1194</code>\n"
        "▫️ پروتکل: UDP 1194 (همراه با گواهی Root CA و کلید tls-crypt)\n\n"
        "💡 این فایل نمونه‌ای از فایلی است که برای خریداران اشتراک صادر می‌شود."
    )
    await callback.message.answer_document(document=doc, caption=caption, parse_mode="HTML")
    await callback.answer("✅ فایل ارسال شد.")


@router.callback_query(F.data.startswith("adm:dl_admin_cert:"))
async def cb_admin_dl_cert(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    cert_type = callback.data.split(":")[2]
    cert_map = {
        "cisco": (CISCO_CA_PATH, "Cisco_AnyConnect_CA.crt", "گواهی Root CA سیسکو (Cisco AnyConnect)"),
        "ikev2": (IKEV2_CA_PATH, "IKEv2_IPsec_CA.crt", "گواهی Root CA پروتکل IKEv2 / IPsec"),
        "sstp": (SSTP_CA_PATH, "SSTP_CA.crt", "گواهی Root CA پروتکل SSTP"),
    }

    if cert_type not in cert_map:
        return await callback.answer("نوع سرتیفیکیت نامعتبر است.", show_alert=True)

    path, fname, title = cert_map[cert_type]
    if not os.path.exists(path):
        return await callback.answer("فایل سرتیفیکیت روی سرور موجود نیست.", show_alert=True)

    doc = FSInputFile(path=path, filename=fname)
    caption = f"📜 <b>{title}</b>\n\nمسیر فایل روی سرور:\n<code>{path}</code>"
    await callback.message.answer_document(document=doc, caption=caption, parse_mode="HTML")
    await callback.answer("✅ سرتیفیکیت ارسال شد.")


@router.callback_query(F.data == "adm:srv:tut_files")
async def cb_admin_srv_tut_files(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    srv_ip = await database.get_setting("server_ip", settings.SERVER_IP)
    text = (
        "📚 <b>فایل‌های اتصال و سرتیفیکیت‌های فعال سرور</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 آی‌پی سرور: <code>{srv_ip}</code>\n\n"
        "از طریق دکمه‌های زیر می‌توانید فایل کانفیگ OpenVPN یا سرتیفیکیت‌های روت پروتکل‌های سیسکو، IKEv2 و SSTP را مستقیماً از سرور دریافت و تست نمایید:"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="📥 دانلود کانفیگ OpenVPN (.ovpn)", callback_data="adm:dl_test_ovpn")
    kb.button(text="📜 سرتیفیکیت Cisco AnyConnect", callback_data="adm:dl_admin_cert:cisco")
    kb.button(text="📜 سرتیفیکیت IKEv2 / IPsec", callback_data="adm:dl_admin_cert:ikev2")
    kb.button(text="📜 سرتیفیکیت SSTP", callback_data="adm:dl_admin_cert:sstp")
    kb.button(text="🔙 بازگشت به پروتکل‌ها", callback_data="adm:server_configs")
    kb.adjust(1, 3, 1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "adm:srv:set_ip")
async def cb_admin_set_ip_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminActionStates.waiting_server_ip)
    await callback.message.answer(
        "🌐 لطفاً <b>آی‌پی جدید سرور (IPv4)</b> را ارسال فرمایید:",
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminActionStates.waiting_server_ip)
async def state_save_server_ip(message: types.Message, state: FSMContext):
    new_ip = message.text.strip()
    await database.set_setting("server_ip", new_ip)
    await state.clear()
    await message.answer(
        f"✅ آی‌پی سرور با موفقیت به <code>{new_ip}</code> به‌روزرسانی شد.",
        reply_markup=get_main_keyboard(True),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "adm:srv:set_psk")
async def cb_admin_set_psk_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminActionStates.waiting_server_psk)
    await callback.message.answer(
        "🔐 لطفاً <b>کلید اشتراکی جدید (IPsec Pre-Shared Key / Secret)</b> را ارسال فرمایید:",
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminActionStates.waiting_server_psk)
async def state_save_server_psk(message: types.Message, state: FSMContext):
    new_psk = message.text.strip()
    await database.set_setting("ipsec_psk", new_psk)
    await state.clear()
    await message.answer(
        f"✅ کلید PSK با موفقیت به <code>{new_psk}</code> تغییر یافت.",
        reply_markup=get_main_keyboard(True),
        parse_mode="HTML",
    )


# ── بخش ۳: تانل‌های اضطراری DNS ──
@router.callback_query(F.data == "adm:srv_proto:dns")
async def cb_admin_proto_dns(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    dnstt_dom = await database.get_setting("dnstt_domain", settings.DNSTT_DOMAIN)
    dnstt_pub = await database.get_setting("dnstt_pubkey", settings.DNSTT_PUBKEY)

    text = (
        "🌐 <b>تانل‌های ضد فیلتر و اضطراری DNS (SlowDNS / DNSTT)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "این تانل‌ها در شرایط فیلترینگ فوق‌العاده سنگین و اینترنت ملی از طریق کوئری‌های UDP پورت ۵۳ ترافیک را عبور می‌دهند.\n\n"
        "▫️ وضعیت DNSTT Server: <b>🟢 فعال (پورت ۵۳۰۰ UDP)</b>\n"
        "▫️ وضعیت Slipstream QUIC: <b>🟢 فعال (پورت ۵۳۵۴ UDP)</b>\n"
        "▫️ وضعیت NoizDNS Noise Proxy: <b>🟢 فعال (پورت ۵۳۵۵ UDP)</b>\n\n"
        f"📡 <b>دامنه نیم‌سرور تانل (DNS Domain):</b>\n<code>{dnstt_dom}</code>\n\n"
        f"🔑 <b>کلید عمومی سرور (Public Key):</b>\n<code>{dnstt_pub}</code>\n"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 بازگشت به پروتکل‌ها", callback_data="adm:server_configs")
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


# ──────────────────────────────────────────────────────────────
#  مدیریت پویا دسته‌بندی‌ها و پلن‌ها (Categories & Plans Engine)
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:categories")
async def cb_admin_categories_list(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    cats = await database.get_all_categories_admin()
    text = (
        "📁 <b>مدیریت دسته‌بندی‌ها و پلن‌های فروشگاه</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "کاربران در ربات دقیقاً این دسته‌بندی‌ها را مشاهده می‌کنند و با ورود به هر دسته، "
        "تنها پلن‌ها و پروتکل‌های تعریف‌شده در آن دسته را خریداری می‌کنند.\n\n"
        "جهت مدیریت پلن‌ها یا افزودن پلن جدید به هر دسته، روی آن کلیک کنید:"
    )
    await callback.message.edit_text(text, reply_markup=admin_categories_list_keyboard(cats), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adm:cat_view:"))
async def cb_admin_cat_view(callback: types.CallbackQuery):
    cat_key = callback.data.split(":")[2]
    cat = await database.get_category_by_key(cat_key)
    if not cat:
        return await callback.answer("دسته‌بندی یافت نشد.", show_alert=True)

    proto_names = {
        "v2ray": "⚡ پروتکل‌های اختصاصی V2Ray (VMess/VLESS)",
        "singbox": "🚀 سوئیت کامل Sing-box (تمام ۲۳ اینباند)",
        "reality": "🕶️ پروتکل اختصاصی VLESS Reality",
        "system_l2tp": "🛡️ پروتکل‌های سیستمی مستقیم (L2TP/IKEv2/IPsec)",
        "dnstt": "🌐 تانل اضطراری DNS (SlowDNS)",
    }
    proto_label = proto_names.get(cat.get("protocol_type"), cat.get("protocol_type"))
    status_str = "🟢 فعال (در فروشگاه نمایش داده می‌شود)" if cat.get("is_active") else "🔴 غیرفعال (مخفی)"

    plans = await database.get_plans_by_category(cat_key, active_only=False)

    text = (
        f"{cat.get('icon', '⚡')} <b>مدیریت دسته‌بندی: {cat.get('title')}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"▫️ کلید شناسه: <code>{cat.get('key')}</code>\n"
        f"▫️ نوع پروتکل و صدور: <b>{proto_label}</b>\n"
        f"▫️ وضعیت نمایش: <b>{status_str}</b>\n"
        f"▫️ توضیحات: <i>{cat.get('description', '—')}</i>\n"
        f"▫️ تعداد پلن‌های ثبت‌شده: <b>{to_fa(len(plans))} پلن</b>\n\n"
        "عملیات مورد نظر را انتخاب فرمایید:"
    )
    await callback.message.edit_text(text, reply_markup=admin_category_detail_keyboard(cat_key, bool(cat.get("is_active"))), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adm:cat_toggle_quick:"))
async def cb_admin_cat_toggle_quick(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    cat_key = callback.data.split(":")[2]
    new_state = await database.toggle_category(cat_key)
    st_text = "روشن شد (در فروشگاه فعال گردید)" if new_state else "خاموش شد (از فروشگاه مخفی گردید)"
    await callback.answer(f"✅ دسته‌بندی {st_text}", show_alert=True)
    cats = await database.get_all_categories_admin()
    await callback.message.edit_reply_markup(reply_markup=admin_categories_list_keyboard(cats))


@router.callback_query(F.data.startswith("adm:cat_toggle:"))
async def cb_admin_cat_toggle(callback: types.CallbackQuery):
    cat_key = callback.data.split(":")[2]
    new_state = await database.toggle_category(cat_key)
    st_text = "فعال شد" if new_state else "غیرفعال شد"
    await callback.answer(f"دسته‌بندی {st_text}.")
    await cb_admin_cat_view(callback)


@router.callback_query(F.data.startswith("adm:cat_del_ask:"))
@router.callback_query(F.data.startswith("adm:cat_del:"))
async def cb_admin_cat_del_ask(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    cat_key = callback.data.split(":")[2]
    cat = await database.get_category_by_key(cat_key)
    if not cat:
        return await callback.answer("دسته‌بندی یافت نشد.", show_alert=True)

    plans = await database.get_plans_by_category(cat_key, active_only=False)
    text = (
        f"⚠️ <b>آیا از حذف کامل دسته‌بندی «{cat.get('title')}» اطمینان دارید؟</b>\n\n"
        f"▫️ تعداد پلن‌های زیرمجموعه این دسته: <b>{to_fa(len(plans))} پلن</b>\n\n"
        "❗ <b>توجه مهم:</b> با تایید حذف، این دسته‌بندی و کلیه پلن‌های آن برای همیشه از ربات پاک خواهند شد و کاربران دیگر به آن دسترسی نخواهند داشت."
    )
    await callback.message.edit_text(text, reply_markup=admin_cat_delete_confirm_keyboard(cat_key), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adm:cat_del_confirm:"))
async def cb_admin_cat_del_confirm(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    cat_key = callback.data.split(":")[2]
    await database.delete_category(cat_key)
    await callback.answer("🗑 دسته‌بندی و تمام پلن‌های آن با موفقیت حذف شدند.", show_alert=True)

    cats = await database.get_all_categories_admin()
    text = (
        "📁 <b>مدیریت دسته‌بندی‌ها و پلن‌های فروشگاه</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "دسته‌بندی با موفقیت حذف شد. لیست دسته‌بندی‌های موجود:"
    )
    await callback.message.edit_text(text, reply_markup=admin_categories_list_keyboard(cats), parse_mode="HTML")


# ── افزودن دسته‌بندی جدید (FSM) ──
@router.callback_query(F.data == "adm:cat_add")
async def cb_admin_cat_add_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminCategoryStates.waiting_title)
    await callback.message.answer(
        "➕ <b>افزودن دسته‌بندی جدید برای فروشگاه</b>\n\n"
        "لطفاً <b>عنوان نمایشی دسته‌بندی</b> را ارسال فرمایید (مثلاً: کانفیگ اختصاصی V2Ray):",
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminCategoryStates.waiting_title)
async def state_cat_title(message: types.Message, state: FSMContext):
    title = message.text.strip()
    await state.update_data(title=title)
    await state.set_state(AdminCategoryStates.waiting_proto)

    await message.answer(
        f"✅ عنوان «{title}» ثبت شد.\n\n"
        "اکنون لطفاً <b>نوع پروتکل و هسته اجرایی</b> این دسته را از دکمه‌های زیر انتخاب فرمایید:",
        reply_markup=admin_category_proto_select_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(AdminCategoryStates.waiting_proto, F.data.startswith("adm:newcat_proto:"))
async def state_cat_proto(callback: types.CallbackQuery, state: FSMContext):
    proto = callback.data.split(":")[2]
    await state.update_data(proto=proto)
    await state.set_state(AdminCategoryStates.waiting_desc)

    await callback.message.answer(
        "📝 لطفاً یک <b>توضیح کوتاه و جذاب</b> برای نمایش زیر نام این دسته در فروشگاه ارسال فرمایید:\n"
        "(یا برای رد شدن عدد 0 را بفرستید)",
        reply_markup=cancel_keyboard,
    )
    await callback.answer()


@router.message(AdminCategoryStates.waiting_desc)
async def state_cat_desc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    title = data.get("title", "دسته جدید")
    proto = data.get("proto", "singbox")
    desc = message.text.strip()
    if desc == "0":
        desc = f"اشتراک اختصاصی {title}"

    # تولید کلید یکتای انگلیسی
    rand_id = secrets.token_hex(2)
    cat_key = f"{proto}_{rand_id}"

    proto_icons = {"v2ray": "⚡", "singbox": "🚀", "reality": "🕶️", "system_l2tp": "🛡️", "dnstt": "🌐"}
    icon = proto_icons.get(proto, "⚡")

    await database.create_category(
        key=cat_key,
        title=title,
        description=desc,
        protocol_type=proto,
        icon=icon,
    )
    await state.clear()

    await message.answer(
        f"🎉 <b>دسته‌بندی «{icon} {title}» با موفقیت ایجاد شد!</b>\n\n"
        f"کلید شناسه: <code>{cat_key}</code>\n"
        f"نوع پروتکل: <b>{proto}</b>\n\n"
        "اکنون از بخش مدیریت دسته‌بندی‌ها می‌توانید برای این دسته پلن‌های دلخواه تعریف کنید.",
        reply_markup=get_main_keyboard(True),
        parse_mode="HTML",
    )


# ── مدیریت پلن‌های یک دسته‌بندی ──
@router.callback_query(F.data.startswith("adm:plans_list:"))
async def cb_admin_plans_list(callback: types.CallbackQuery):
    cat_key = callback.data.split(":")[2]
    cat = await database.get_category_by_key(cat_key)
    plans = await database.get_plans_by_category(cat_key, active_only=False)

    text = (
        f"📋 <b>لیست پلن‌های دسته‌بندی {cat.get('title', cat_key)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"تعداد پلن‌ها: <b>{to_fa(len(plans))} پلن</b>\n\n"
        "جهت مشاهده، ویرایش یا حذف، روی پلن مورد نظر بزنید یا پلن جدید بسازید:"
    )
    await callback.message.edit_text(text, reply_markup=admin_plans_list_keyboard(plans, cat_key), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adm:plan_view:"))
async def cb_admin_plan_view(callback: types.CallbackQuery):
    plan_id = int(callback.data.split(":")[2])
    plan = await database.get_plan_by_id(plan_id)
    if not plan:
        return await callback.answer("پلن یافت نشد.", show_alert=True)

    traffic_desc = f"{to_fa(plan.get('traffic_gb'))} گیگابایت" if plan.get('traffic_gb') > 0 else "نامحدود"
    status_str = "🟢 فعال" if plan.get("is_active") else "🔴 غیرفعال"

    text = (
        f"📦 <b>مشخصات پلن #{plan.get('id')}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 عنوان پلن: <b>{plan.get('name')}</b>\n"
        f"📶 حجم ترافیک: <b>{traffic_desc}</b>\n"
        f"⏱ مدت اعتبار: <b>{to_fa(plan.get('duration_days'))} روز</b>\n"
        f"💰 قیمت فروش: <b>{to_toman(plan.get('price'))}</b>\n"
        f"📊 وضعیت پلن: <b>{status_str}</b>\n"
    )
    await callback.message.edit_text(text, reply_markup=admin_plan_detail_keyboard(plan_id, plan.get("category_key"), bool(plan.get("is_active"))), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adm:plan_toggle:"))
async def cb_admin_plan_toggle(callback: types.CallbackQuery):
    plan_id = int(callback.data.split(":")[2])
    new_state = await database.toggle_plan(plan_id)
    st = "فعال شد" if new_state else "غیرفعال شد"
    await callback.answer(f"پلن {st}.")
    await cb_admin_plan_view(callback)


@router.callback_query(F.data.startswith("adm:plan_del:"))
async def cb_admin_plan_del(callback: types.CallbackQuery):
    plan_id = int(callback.data.split(":")[2])
    plan = await database.get_plan_by_id(plan_id)
    cat_key = plan.get("category_key") if plan else "singbox"
    await database.delete_plan(plan_id)
    await callback.answer("پلن با موفقیت حذف شد.")
    # بازگشت به لیست پلن‌ها
    plans = await database.get_plans_by_category(cat_key, active_only=False)
    cat = await database.get_category_by_key(cat_key)
    text = f"📋 <b>لیست پلن‌های دسته‌بندی {cat.get('title', cat_key)}</b>"
    await callback.message.edit_text(text, reply_markup=admin_plans_list_keyboard(plans, cat_key), parse_mode="HTML")


# ── افزودن پلن جدید به دسته‌بندی (FSM) ──
@router.callback_query(F.data.startswith("adm:plan_add:"))
async def cb_admin_plan_add_start(callback: types.CallbackQuery, state: FSMContext):
    cat_key = callback.data.split(":")[2]
    await state.set_state(AdminPlanStates.waiting_name)
    await state.update_data(cat_key=cat_key)

    await callback.message.answer(
        "➕ <b>افزودن پلن جدید به این دسته‌بندی</b>\n\n"
        "لطفاً <b>عنوان پلن</b> را ارسال فرمایید (مثلاً: پلن ۱ ماهه ۳۰ گیگابایت):",
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminPlanStates.waiting_name)
async def state_plan_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(name=name)
    await state.set_state(AdminPlanStates.waiting_traffic)
    await message.answer(
        f"✅ عنوان «{name}» ثبت شد.\n\n"
        "📶 لطفاً <b>سقف حجم ترافیک (به گیگابایت)</b> را به صورت عدد وارد فرمایید:\n"
        "(برای نامحدود عدد 0 را ارسال کنید)",
        reply_markup=cancel_keyboard,
    )


@router.message(AdminPlanStates.waiting_traffic)
async def state_plan_traffic(message: types.Message, state: FSMContext):
    raw = message.text.strip().replace("/", ".")
    try:
        gb = float(raw)
        if gb < 0:
            raise ValueError
    except ValueError:
        return await message.answer("❌ لطفاً یک عدد معتبر (۰ یا مثبت) وارد فرمایید:")

    await state.update_data(traffic=gb)
    await state.set_state(AdminPlanStates.waiting_days)
    await message.answer(
        "⏱ لطفاً <b>مدت اعتبار پلن (به تعداد روز)</b> را وارد فرمایید (مثلاً: 30):",
        reply_markup=cancel_keyboard,
    )


@router.message(AdminPlanStates.waiting_days)
async def state_plan_days(message: types.Message, state: FSMContext):
    raw = message.text.strip()
    if not raw.isdigit() or int(raw) <= 0:
        return await message.answer("❌ لطفاً یک عدد صحیح مثبت برای روزها وارد نمایید:")

    await state.update_data(days=int(raw))
    await state.set_state(AdminPlanStates.waiting_price)
    await message.answer(
        "💰 لطفاً <b>مبلغ فروش پلن (به تومان)</b> را به صورت عدد وارد فرمایید (مثلاً: 65000):",
        reply_markup=cancel_keyboard,
    )


@router.message(AdminPlanStates.waiting_price)
async def state_plan_price(message: types.Message, state: FSMContext):
    raw = message.text.strip().replace(",", "").replace("،", "")
    if not raw.isdigit() or int(raw) < 1000:
        return await message.answer("❌ لطفاً مبلغ معتبر (حداقل ۱,۰۰۰ تومان) به عدد ارسال فرمایید:")

    price = int(raw)
    data = await state.get_data()
    cat_key = data.get("cat_key", "singbox")
    name = data.get("name", "پلن جدید")
    traffic = data.get("traffic", 30.0)
    days = data.get("days", 30)
    await state.clear()

    plan_id = await database.create_plan(
        category_key=cat_key,
        name=name,
        traffic_gb=traffic,
        duration_days=days,
        price=price,
    )

    await message.answer(
        "🎉 <b>پلن جدید با موفقیت ایجاد و فعال شد!</b>\n\n"
        f"🆔 شناسه پلن: #{plan_id}\n"
        f"🏷 عنوان: <b>{name}</b>\n"
        f"📶 حجم: <b>{to_fa(traffic)} گیگابایت</b>\n"
        f"⏱ مدت: <b>{to_fa(days)} روز</b>\n"
        f"💰 قیمت: <b>{to_toman(price)}</b>\n\n"
        "این پلن بلافاصله در فروشگاه برای کاربران قابل خریداری است.",
        reply_markup=get_main_keyboard(True),
        parse_mode="HTML",
    )


# ──────────────────────────────────────────────────────────────
#  آمار فروش، فیش‌های واریزی، تیکت‌ها و تست پنل
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:stats")
async def cb_admin_stats(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    await callback.answer("در حال ارزیابی سرور...")
    sales_data = await database.get_sales_stats()
    sys_data = await panel_api.get_system_status()

    text = format_sales_stats(sales_data, sys_data if sys_data.get("success") else None)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 بروزرسانی آمار", callback_data="adm:stats")
    kb.button(text="🔙 بازگشت به مدیریت", callback_data="adm:main")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "adm:pending_tx")
async def cb_admin_pending_tx(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    txs = await database.get_pending_transactions()
    if not txs:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        kb = InlineKeyboardBuilder()
        kb.button(text="🔙 بازگشت به مدیریت", callback_data="adm:main")
        return await callback.message.edit_text(
            "✅ <b>هیچ فیش واریزی در انتظار بررسی وجود ندارد!</b>\nتمامی درخواست‌ها بررسی شده‌اند.",
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )

    tx = txs[0]
    tx_id = tx["id"]
    u_name = f"@{tx['username']}" if tx.get("username") else str(tx["telegram_id"])
    u_first = tx.get("first_name", "کاربر")
    amount_str = to_toman(tx["amount"])
    tracking = tx.get("tracking_code", "—")
    date_str = str(tx.get("created_at", ""))[:19]
    has_photo = bool(tx.get("receipt_photo_id"))
    card_info = f"💳 واریز به کارت: <code>{tx.get('card_used')}</code>\n" if tx.get("card_used") else ""

    text = (
        f"💳 <b>فیش واریزی جدید (شماره #{tx_id})</b> [{to_fa(len(txs))} فیش در صف]\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 کاربر: <b>{u_first}</b> ({u_name})\n"
        f"🆔 شناسه تلگرام: <code>{tx['telegram_id']}</code>\n"
        f"💰 مبلغ واریزی: <b>{amount_str}</b>\n"
        f"🧾 کد/توضیح: <code>{tracking}</code>\n"
        f"{card_info}"
        f"📅 زمان ثبت: <i>{to_fa(date_str)}</i>\n"
        f"🖼 پیوست تصویر: <b>{'دارد (از دکمه زیر مشاهده کنید)' if has_photo else 'فقط متن/کد'}</b>\n\n"
        "آیا این پرداخت مورد تأیید است؟"
    )
    await callback.message.edit_text(text, reply_markup=admin_tx_keyboard(tx_id, has_photo=has_photo), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adm:tx_photo:"))
async def cb_admin_tx_photo(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    tx_id = int(callback.data.split(":")[2])
    tx = await database.get_transaction_by_id(tx_id)
    if not tx or not tx.get("receipt_photo_id"):
        return await callback.answer("تصویری برای این فیش ثبت نشده است.", show_alert=True)

    try:
        await callback.message.answer_photo(
            photo=tx["receipt_photo_id"],
            caption=f"🧾 <b>تصویر فیش واریزی تراکنش #{tx_id}</b>\n👤 کاربر: <code>{tx['telegram_id']}</code> | مبلغ: <b>{to_toman(tx['amount'])}</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        await callback.answer(f"خطا در ارسال تصویر: {e}", show_alert=True)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:tx_appr:"))
async def cb_admin_tx_approve(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    tx_id = int(callback.data.split(":")[2])
    tx_data = await database.approve_transaction(tx_id)
    if not tx_data:
        return await callback.answer("تراکنش یافت نشد یا قبلاً بررسی شده است.", show_alert=True)

    try:
        user_msg = (
            "✅ <b>فیش واریزی شما تأیید شد!</b>\n\n"
            f"💰 مبلغ <b>{to_toman(tx_data['amount'])}</b> به کیف پول شما اضافه شد.\n"
            "اکنون می‌توانید از بخش «🛒 خرید اشتراک» پلن مورد نظر خود را خریداری فرمایید."
        )
        await callback.bot.send_message(tx_data["telegram_id"], user_msg, parse_mode="HTML")
    except Exception:
        pass

    await callback.answer("✅ فیش تأیید و موجودی کاربر شارژ شد.")
    await cb_admin_pending_tx(callback)


@router.callback_query(F.data.startswith("adm:tx_rej:"))
async def cb_admin_tx_reject(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    tx_id = int(callback.data.split(":")[2])
    tx_data = await database.reject_transaction(tx_id)
    if not tx_data:
        return await callback.answer("تراکنش یافت نشد.", show_alert=True)

    try:
        user_msg = (
            "❌ <b>فیش واریزی شما رد شد!</b>\n\n"
            f"مبلغ: {to_toman(tx_data['amount'])}\n"
            "علت: مشخصات تراکنش یا کد رهگیری فیش ارسالی با حساب بانکی همخوانی نداشت.\n"
            "در صورت وجود ابهام، از بخش «🎫 تیکت‌ها» با پشتیبانی در ارتباط باشید."
        )
        await callback.bot.send_message(tx_data["telegram_id"], user_msg, parse_mode="HTML")
    except Exception:
        pass

    await callback.answer("❌ فیش واریزی رد شد.")
    await cb_admin_pending_tx(callback)


# ── تنظیمات اکانت تست ──
@router.callback_query(F.data == "adm:trial")
async def cb_admin_trial_menu(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    is_en = (await database.get_setting("trial_enabled", "1")) == "1"
    gb = await database.get_setting("trial_traffic_gb", str(settings.TRIAL_TRAFFIC_GB))
    days = await database.get_setting("trial_duration_days", str(settings.TRIAL_DURATION_DAYS))
    trial_mode = await database.get_setting("trial_mode", "menu")

    state_str = "🟢 فعال (کاربران می‌توانند تست بگیرند)" if is_en else "🔴 غیرفعال (توزیع تست متوقف شده)"
    mode_str = "📋 منوی انتخابی + پکیج کامل" if trial_mode == "menu" else "⚡ صدور مستقیم همه حالت‌ها بدون منو"

    active_trials = await database.get_all_trial_accounts()

    text = (
        "🎁 <b>مدیریت و تنظیمات اکانت تستی رایگان</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"▫️ وضعیت فعلی: <b>{state_str}</b>\n"
        f"▫️ حجم اکانت تست: <b>{to_fa(gb)} گیگابایت</b>\n"
        f"▫️ مدت اعتبار تست: <b>{to_fa(days)} روز</b> (پس از اولین اتصال)\n"
        f"▫️ نحوه توزیع تست: <b>{mode_str}</b>\n"
        f"▫️ اکانت‌های تست فعال در سیستم: <b>{to_fa(len(active_trials))} اکانت</b>\n\n"
        "💡 <i>اکانت‌های تستی پس از پایان اعتبار یا مصرف حجم، به صورت خودکار از پنل MHPanel حذف می‌گردند تا فضا اشغال نشود.</i>"
    )
    await callback.message.edit_text(text, reply_markup=admin_trial_keyboard(is_en, trial_mode), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "adm:trial:toggle")
async def cb_admin_trial_toggle(callback: types.CallbackQuery):
    is_en = (await database.get_setting("trial_enabled", "1")) == "1"
    new_state = "0" if is_en else "1"
    await database.set_setting("trial_enabled", new_state)
    await callback.answer("وضعیت تغییر یافت.")
    await cb_admin_trial_menu(callback)


@router.callback_query(F.data == "adm:trial:toggle_mode")
async def cb_admin_trial_toggle_mode(callback: types.CallbackQuery):
    cur_mode = await database.get_setting("trial_mode", "menu")
    new_mode = "direct_all" if cur_mode == "menu" else "menu"
    await database.set_setting("trial_mode", new_mode)
    await callback.answer("نحوه توزیع تست تغییر یافت.")
    await cb_admin_trial_menu(callback)


@router.callback_query(F.data == "adm:trial:cleanup")
async def cb_admin_trial_cleanup(callback: types.CallbackQuery):
    await callback.answer("⏳ در حال استعلام و پاکسازی تست‌های منقضی شده از پنل...")
    count = await trial_manager.check_and_cleanup_expired_trials(callback.bot)
    await callback.answer(f"✅ پاکسازی انجام شد: {count} اکانت منقضی شده از پنل حذف گردید.", show_alert=True)
    await cb_admin_trial_menu(callback)



@router.callback_query(F.data == "adm:trial:set_gb")
async def cb_admin_trial_set_gb(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminActionStates.waiting_trial_gb)
    await callback.message.answer(
        "📶 لطفاً <b>حجم اکانت تستی (به گیگابایت)</b> را به صورت عدد وارد فرمایید (مثلاً 1 یا 2):",
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminActionStates.waiting_trial_gb)
async def state_save_trial_gb(message: types.Message, state: FSMContext):
    raw = message.text.strip().replace("/", ".")
    try:
        val = float(raw)
        if val <= 0:
            raise ValueError
    except ValueError:
        return await message.answer("❌ لطفاً یک عدد مثبت وارد نمایید:")

    await database.set_setting("trial_traffic_gb", str(val))
    await state.clear()
    await message.answer(
        f"✅ حجم اکانت تستی به <b>{to_fa(val)} گیگابایت</b> تغییر یافت.",
        reply_markup=get_main_keyboard(True),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "adm:trial:set_days")
async def cb_admin_trial_set_days(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminActionStates.waiting_trial_days)
    await callback.message.answer(
        "⏱ لطفاً <b>مدت اعتبار اکانت تستی (به روز)</b> را وارد فرمایید (مثلاً 1 یا 2):",
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminActionStates.waiting_trial_days)
async def state_save_trial_days(message: types.Message, state: FSMContext):
    raw = message.text.strip()
    if not raw.isdigit() or int(raw) <= 0:
        return await message.answer("❌ لطفاً یک عدد صحیح مثبت وارد کنید:")

    await database.set_setting("trial_duration_days", raw)
    await state.clear()
    await message.answer(
        f"✅ مدت اعتبار اکانت تستی به <b>{to_fa(raw)} روز</b> تغییر یافت.",
        reply_markup=get_main_keyboard(True),
        parse_mode="HTML",
    )


# ── مدیریت رفرال ──
@router.callback_query(F.data == "adm:referral")
async def cb_admin_referral_menu(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    pct = await database.get_setting("referral_percent", str(settings.REFERRAL_PERCENT))
    text = (
        "👥 <b>مدیریت سیستم رفرال و بازاریابی</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"▫️ درصد پورسانت فعلی معرف‌ها: <b>{to_fa(pct)}٪ از هر پرداخت</b>\n\n"
        "می‌توانید درصد را تغییر داده یا برترین معرف‌ها را مشاهده فرمایید:"
    )
    await callback.message.edit_text(text, reply_markup=admin_referral_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "adm:ref:set_pct")
async def cb_admin_ref_set_pct(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminActionStates.waiting_referral_pct)
    await callback.message.answer(
        "🔢 لطفاً <b>درصد پورسانت معرف (از 0 تا 100)</b> را به صورت عدد وارد فرمایید:",
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminActionStates.waiting_referral_pct)
async def state_save_ref_pct(message: types.Message, state: FSMContext):
    raw = message.text.strip()
    if not raw.isdigit() or not (0 <= int(raw) <= 100):
        return await message.answer("❌ لطفاً عددی بین ۰ تا ۱۰۰ وارد نمایید:")

    await database.set_setting("referral_percent", raw)
    await state.clear()
    await message.answer(
        f"✅ درصد پورسانت بازاریابی به <b>{to_fa(raw)}٪</b> تغییر یافت.",
        reply_markup=get_main_keyboard(True),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "adm:ref:top")
async def cb_admin_ref_top(callback: types.CallbackQuery):
    top_list = await database.get_top_referrers(limit=10)
    text = format_top_referrers(top_list)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 بازگشت به رفرال", callback_data="adm:referral")
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


# ── تنظیمات اعلان‌های آن‌تایم مدیریت (Real-time Notifications) ──
@router.callback_query(F.data == "adm:notifications")
async def cb_admin_notifications_menu(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    is_buy_on = await notifier.is_purchase_notification_enabled()
    is_trial_on = await notifier.is_trial_notification_enabled()

    text = (
        "🔔 <b>مدیریت اعلان‌های آن‌تایم (لحظه‌ای) مدیریت</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "در این بخش می‌توانید مشخص کنید هنگام وقوع هریک از رویدادها، ربات به صورت لحظه‌ای به تمام مدیران اعلان ارسال کند یا خیر:\n\n"
        f"🛒 <b>اعلان خریدهای موفق:</b> {'🟢 فعال (ارسال می‌شود)' if is_buy_on else '🔴 غیرفعال (خاموش)'}\n"
        "<i>(شامل مشخصات خریدار، نوع محصول، پروتکل، مبلغ پرداختی و حجم)</i>\n\n"
        f"🎁 <b>اعلان دریافت اکانت تست:</b> {'🟢 فعال (ارسال می‌شود)' if is_trial_on else '🔴 غیرفعال (خاموش)'}\n"
        "<i>(شامل نام کاربری، شناسه کاربری، حالت انتخابی و اکانت‌های ساخته‌شده)</i>\n\n"
        "👇 جهت فعال یا غیرفعال‌سازی هر بخش روی دکمه مربوطه کلیک کنید:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_notifications_keyboard(is_buy_on, is_trial_on),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "adm:notify:toggle_buy")
async def cb_admin_notify_toggle_buy(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    new_val = await notifier.toggle_purchase_notification()
    status_text = "فعال شد 🟢" if new_val else "غیرفعال شد 🔴"
    await callback.answer(f"اعلان خرید {status_text}")
    await cb_admin_notifications_menu(callback)


@router.callback_query(F.data == "adm:notify:toggle_trial")
async def cb_admin_notify_toggle_trial(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    new_val = await notifier.toggle_trial_notification()
    status_text = "فعال شد 🟢" if new_val else "غیرفعال شد 🔴"
    await callback.answer(f"اعلان تست {status_text}")
    await cb_admin_notifications_menu(callback)


# ── پاسخ‌گویی به تیکت‌های پشتیبانی ──
@router.callback_query(F.data == "adm:tickets")
async def cb_admin_tickets_list(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    open_tks = await database.get_open_tickets_admin()
    if not open_tks:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        kb = InlineKeyboardBuilder()
        kb.button(text="🔙 بازگشت به مدیریت", callback_data="adm:main")
        return await callback.message.edit_text(
            "✅ <b>هیچ تیکت پشتیبانی بازی وجود ندارد!</b>",
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    for t in open_tks:
        kb.button(
            text=f"🎫 #{t['id']} — {t['subject']}",
            callback_data=f"adm:tk_view:{t['id']}",
        )
    kb.button(text="🔙 بازگشت به مدیریت", callback_data="adm:main")
    kb.adjust(1)
    await callback.message.edit_text("🎫 <b>لیست تیکت‌های باز کاربران:</b>", reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adm:tk_view:"))
async def cb_admin_tk_view(callback: types.CallbackQuery):
    ticket_id = int(callback.data.split(":")[2])
    t = await database.get_ticket(ticket_id)
    if not t:
        return await callback.answer("تیکت یافت نشد.", show_alert=True)

    text = (
        f"🎫 <b>تیکت پشتیبانی #{t['id']}</b>\n"
        f"👤 شناسه کاربر: <code>{t['telegram_id']}</code>\n"
        f"📝 موضوع: <b>{t['subject']}</b>\n\n"
        f"💬 <b>متن پیام کاربر:</b>\n{t['message']}\n"
    )
    replies = t.get("replies", [])
    if replies:
        text += "\n📬 <b>مکالمات پیشین:</b>\n"
        for r in replies:
            st = "مدیریت" if r["sender"] == "admin" else "کاربر"
            text += f"• <b>{st}:</b> {r['message']}\n"

    await callback.message.edit_text(text, reply_markup=admin_ticket_keyboard(ticket_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adm:tk_rep:"))
async def cb_admin_tk_reply_start(callback: types.CallbackQuery, state: FSMContext):
    ticket_id = int(callback.data.split(":")[2])
    await state.set_state(AdminActionStates.waiting_ticket_reply)
    await state.update_data(target_ticket_id=ticket_id)
    await callback.message.answer(
        f"💬 لطفاً پاسخ خود را برای تیکت #{ticket_id} ارسال فرمایید:",
        reply_markup=cancel_keyboard,
    )
    await callback.answer()


@router.message(AdminActionStates.waiting_ticket_reply)
async def state_save_ticket_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ticket_id = data.get("target_ticket_id")
    reply_text = message.text.strip()
    await state.clear()

    await database.reply_ticket(ticket_id, "admin", reply_text)
    t = await database.get_ticket(ticket_id)

    if t and t.get("telegram_id"):
        try:
            notif = (
                f"📬 <b>پاسخ جدید به تیکت شما (#{ticket_id})</b>\n\n"
                f"📝 موضوع: {t.get('subject')}\n"
                f"🛠 <b>پاسخ پشتیبانی:</b>\n{reply_text}\n\n"
                "جهت مشاهده مکالمات کامل وارد بخش «🎫 تیکت‌ها» شوید."
            )
            await message.bot.send_message(t["telegram_id"], notif, parse_mode="HTML")
        except Exception:
            pass

    await message.answer(f"✅ پاسخ با موفقیت برای کاربر تیکت #{ticket_id} ارسال شد.", reply_markup=get_main_keyboard(True))


@router.callback_query(F.data.startswith("adm:tk_close:"))
async def cb_admin_tk_close(callback: types.CallbackQuery):
    ticket_id = int(callback.data.split(":")[2])
    import aiosqlite
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("UPDATE tickets SET status = 'closed' WHERE id = ?", (ticket_id,))
        await db.commit()
    await callback.answer("تیکت بسته شد.")
    await cb_admin_tickets_list(callback)


# ── تست زنده ارتباط با پنل MHPanel ──
@router.callback_query(F.data == "adm:test_panel")
async def cb_admin_test_panel(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    await callback.answer("در حال تست اتصال زنده با هسته...")
    users_res = await panel_api.get_all_users()
    status_res = await panel_api.get_system_status()

    if users_res.get("success"):
        cnt = users_res.get("count", 0)
        sys_info = status_res.get("system", {}) if status_res.get("success") else {}
        cpu = sys_info.get("cpu_percent", "—")
        ram = sys_info.get("ram_percent", "—")
        disk = sys_info.get("disk_percent", "—")

        text = (
            "✅ <b>اتصال به API پنل MHPanel با موفقیت برقرار شد!</b>\n\n"
            f"👤 تعداد کاربران تعریف‌شده روی هسته Sing-box: <b>{to_fa(cnt)} کاربر</b>\n"
            f"🖥 پردازنده سرور: <b>{to_fa(cpu)}%</b>\n"
            f"🧠 مصرف رم سرور: <b>{to_fa(ram)}%</b>\n"
            f"💾 مصرف فضای دیسک: <b>{to_fa(disk)}%</b>\n\n"
            "هسته و سرویس‌های تانل در حالت پایدار قرار دارند."
        )
    else:
        text = f"❌ <b>خطا در برقراری اتصال با MHPanel:</b>\n{users_res.get('error', 'عدم دسترسی به پورت ۹۰۹۰')}"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 بازگشت به مدیریت", callback_data="adm:main")
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")


# ──────────────────────────────────────────────────────────────
#  مدیریت شماره کارت‌های بانکی گردون (Rotational Card Management)
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:card_settings")
async def cb_admin_card_settings(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    cards = await database.get_all_bank_cards_admin()
    active_count = sum(1 for c in cards if c.get("is_active"))

    text = (
        "💳 <b>مدیریت شماره کارت‌های بانکی گردون و چرخشی</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"▫️ تعداد کل کارت‌ها: <b>{to_fa(len(cards))} کارت</b>\n"
        f"▫️ کارت‌های فعال در گردونه: <b>{to_fa(active_count)} کارت</b>\n\n"
        "🎲 <b>مکانیزم چرخشی:</b> ربات در هر بار درخواست شارژ توسط کاربر، یکی از کارت‌های 🟢 روشن را به صورت کاملاً تصادفی انتخاب و نمایش می‌دهد.\n\n"
        "▫️ برای روشن/خاموش کردن هر کارت، روی دکمه وضعیت آن کلیک کنید.\n"
        "▫️ برای حذف کارت از گردونه، روی علامت 🗑 کلیک نمایید."
    )
    await callback.message.edit_text(text, reply_markup=admin_bank_cards_list_keyboard(cards), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adm:card_toggle:"))
async def cb_admin_card_toggle(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    card_id = int(callback.data.split(":")[2])
    new_state = await database.toggle_bank_card(card_id)
    st_text = "فعال شد (وارد گردونه شد)" if new_state else "غیرفعال شد (از گردونه خارج شد)"
    await callback.answer(f"کارت {st_text}.", show_alert=False)

    cards = await database.get_all_bank_cards_admin()
    await callback.message.edit_reply_markup(reply_markup=admin_bank_cards_list_keyboard(cards))


@router.callback_query(F.data.startswith("adm:card_del:"))
async def cb_admin_card_del(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    card_id = int(callback.data.split(":")[2])
    await database.delete_bank_card(card_id)
    await callback.answer("🗑 کارت بانکی با موفقیت حذف شد.", show_alert=True)

    cards = await database.get_all_bank_cards_admin()
    await callback.message.edit_reply_markup(reply_markup=admin_bank_cards_list_keyboard(cards))


@router.callback_query(F.data.startswith("adm:card_view:"))
async def cb_admin_card_view(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    card_id = int(callback.data.split(":")[2])
    card = await database.get_bank_card_by_id(card_id)
    if not card:
        return await callback.answer("کارت یافت نشد.", show_alert=True)

    st_str = "🟢 فعال (در گردونه انتخاب تصادفی)" if card.get("is_active") else "🔴 غیرفعال (موقتاً خاموش)"
    text = (
        "💳 <b>مشخصات کارت بانکی</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"▫️ شماره کارت: <code>{card.get('card_number')}</code>\n"
        f"▫️ نام دارنده حساب: <b>{card.get('card_holder')}</b>\n"
        f"▫️ بانک: <b>{card.get('bank_name', 'بانک')}</b>\n"
        f"▫️ وضعیت: <b>{st_str}</b>\n"
    )
    await callback.message.edit_text(text, reply_markup=admin_bank_card_detail_keyboard(card_id, bool(card.get("is_active"))), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "adm:card_add")
async def cb_admin_card_add_start(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    await state.set_state(AdminCardStates.waiting_card_number)
    await callback.message.answer(
        "➕ <b>افزودن کارت بانکی جدید به گردونه</b>\n\n"
        "لطفاً <b>شماره کارت ۱۶ رقمی</b> را ارسال نمایید:",
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminCardStates.waiting_card_number)
async def state_card_add_number(message: types.Message, state: FSMContext):
    raw_num = re.sub(r"\D", "", message.text.strip())
    if len(raw_num) != 16:
        return await message.answer(
            "⚠️ شماره کارت باید دقیقاً <b>۱۶ رقم</b> باشد. لطفاً مجدداً ارسال نمایید یا لغو کنید:",
            parse_mode="HTML",
        )

    await state.update_data(new_card_num=raw_num)
    await state.set_state(AdminCardStates.waiting_card_holder)
    await message.answer(
        f"💳 شماره کارت <code>{raw_num}</code> ثبت شد.\n\n"
        "اکنون لطفاً <b>نام و نام‌خانوادگی صاحب حساب</b> را ارسال فرمایید:",
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )


@router.message(AdminCardStates.waiting_card_holder)
async def state_card_add_holder(message: types.Message, state: FSMContext):
    holder = message.text.strip()
    if len(holder) < 3:
        return await message.answer("⚠️ لطفاً نام و نام‌خانوادگی معتبر ارسال نمایید:")

    data = await state.get_data()
    card_num = data.get("new_card_num")
    await state.clear()

    await database.add_bank_card(card_number=card_num, card_holder=holder)

    await message.answer(
        f"🎉 <b>کارت بانکی جدید با موفقیت به گردونه اضافه شد!</b>\n\n"
        f"▫️ شماره کارت: <code>{card_num}</code>\n"
        f"▫️ به نام: <b>{holder}</b>\n\n"
        "این کارت از همین لحظه به طور تصادفی به خریداران کارت‌به‌کارت نمایش داده خواهد شد.",
        reply_markup=get_main_keyboard(True),
        parse_mode="HTML",
    )


# ──────────────────────────────────────────────────────────────
#  ارسال اعلان و پیام همگانی به کاربران (Broadcast)
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:broadcast")
async def cb_admin_broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    user_ids = await database.get_all_user_ids()
    text = (
        "📢 <b>ارسال اعلان و پیام همگانی به تمام اعضای ربات</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 تعداد کاربران ثبت‌شده در سیستم: <b>{to_fa(len(user_ids))} کاربر</b>\n\n"
        "▫️ پیام ارسالی شما مستقیماً در چت خصوصی کاربران ارسال می‌شود و همزمان در بخش «🔔 اعلان‌ها» نیز ذخیره خواهد شد.\n"
        "▫️ می‌توانید هر نوع پیامی (متن ساده یا فرمت‌دار، عکس با کپشن و...) ارسال فرمایید.\n\n"
        "👇 لطفاً پیام مورد نظر خود را اکنون ارسال فرمایید (یا روی لغو بزنید):"
    )
    await state.set_state(AdminBroadcastStates.waiting_message)
    await callback.message.answer(text, reply_markup=cancel_keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(AdminBroadcastStates.waiting_message)
async def state_receive_broadcast_message(message: types.Message, state: FSMContext):
    await state.update_data(
        broadcast_msg_id=message.message_id,
        broadcast_from_chat=message.chat.id,
        broadcast_text=message.text or message.caption or "اعلان جدید مدیریت",
    )
    await state.set_state(AdminBroadcastStates.waiting_confirm)

    user_ids = await database.get_all_user_ids()
    await message.answer(
        f"📋 <b>پیش‌نمایش پیام ثبت شد!</b>\n\n"
        f"این اعلان برای <b>{to_fa(len(user_ids))} کاربر</b> ارسال خواهد شد.\n"
        "آیا برای شروع ارسال مطمئن هستید؟",
        reply_markup=admin_broadcast_confirm_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "adm:broadcast:cancel")
async def cb_admin_broadcast_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ عملیات ارسال پیام همگانی لغو شد.")
    await callback.answer("لغو شد.")


@router.callback_query(F.data == "adm:broadcast:send")
async def cb_admin_broadcast_send(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    data = await state.get_data()
    msg_id = data.get("broadcast_msg_id")
    from_chat = data.get("broadcast_from_chat")
    b_text = data.get("broadcast_text", "اعلان جدید مدیریت")
    await state.clear()

    if not msg_id or not from_chat:
        return await callback.message.edit_text("❌ پیام نامعتبر است یا منقضی شده است.")

    user_ids = await database.get_all_user_ids()
    if not user_ids:
        return await callback.message.edit_text("⚠️ هنوز کاربری در دیتابیس ربات ثبت نشده است.")

    await database.create_broadcast_notification(b_text)

    status_msg = await callback.message.edit_text(
        f"⏳ در حال ارسال پیام همگانی به {to_fa(len(user_ids))} کاربر... لطفاً صبور باشید."
    )

    success_cnt = 0
    fail_cnt = 0

    for uid in user_ids:
        try:
            await callback.bot.copy_message(chat_id=uid, from_chat_id=from_chat, message_id=msg_id)
            success_cnt += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail_cnt += 1

    report = (
        "📢 <b>گزارش ارسال پیام و اعلان همگانی:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 کل کاربران هدف: <b>{to_fa(len(user_ids))}</b>\n"
        f"✅ ارسال موفق: <b>{to_fa(success_cnt)}</b>\n"
        f"⚠️ ناموفق (بلاک ربات یا اکانت دیلیت‌شده): <b>{to_fa(fail_cnt)}</b>\n\n"
        "پیام همگانی در بخش اعلان‌های کاربران نیز ثبت گردید."
    )
    await status_msg.edit_text(report, parse_mode="HTML")
    await callback.message.answer("منوی اصلی ادمین:", reply_markup=get_main_keyboard(True))


# ──────────────────────────────────────────────────────────────
#  مدیریت کاربران (User Management: جستجو، شارژ، صدور، فاکتور، پیام)
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:users_menu")
async def cb_admin_users_menu(callback: types.CallbackQuery, state: FSMContext):
    """منوی اصلی مدیریت کاربران."""
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    await state.clear()
    text = (
        "👥 <b>مرکز مدیریت جامع کاربران ربات</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "از طریق این بخش می‌توانید:\n"
        "▫️ جستجو بر اساس شناسه عددی، نام یا نام کاربری\n"
        "▫️ افزایش یا کسر از موجودی کیف پول کاربر\n"
        "▫️ صدور و فعال‌سازی مستقیم اشتراک بدون پرداخت\n"
        "▫️ صدور فاکتور دستی و ارسال پیام اختصاصی به کاربر\n"
        "▫️ مشاهده اکانت‌های فعال و بررسی رسیدهای واریزی کاربر\n\n"
        "👇 لطفاً یکی از گزینه‌های زیر را انتخاب فرمایید:"
    )
    await callback.message.edit_text(text, reply_markup=admin_users_menu_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "adm:u_search")
async def cb_admin_users_search_start(callback: types.CallbackQuery, state: FSMContext):
    """درخواست آیدی یا یوزرنیم جهت جستجو."""
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    await state.set_state(AdminUserStates.waiting_search_query)
    text = (
        "🔍 <b>جستجوی کاربر:</b>\n\n"
        "لطفاً <b>شناسه عددی تلگرام (Telegram ID)</b> یا <b>یوزرنیم (@username)</b> "
        "یا نام کاربر را ارسال نمایید:"
    )
    await callback.message.answer(text, reply_markup=cancel_keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(AdminUserStates.waiting_search_query)
async def process_admin_user_search(message: types.Message, state: FSMContext):
    """پردازش متن جستجوی کاربر و نمایش نتایج."""
    if not _is_admin(message):
        return
    query = (message.text or "").strip()
    if query == "❌ لغو":
        await state.clear()
        return await message.answer("❌ عملیات جستجو لغو شد.", reply_markup=get_main_keyboard(True))

    users = await database.search_users(query)
    await state.clear()

    if not users:
        return await message.answer(
            f"❌ کاربری با مشخصات «{query}» در پایگاه داده یافت نشد.",
            reply_markup=get_main_keyboard(True),
        )

    if len(users) == 1:
        u = users[0]
        return await _show_user_card(message, u.get("telegram_id"))

    # اگر چند نتیجه یافت شد
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    for u in users[:15]:
        uname = f"@{u.get('username')}" if u.get("username") else "بدون یوزرنیم"
        kb.button(
            text=f"👤 {u.get('first_name', 'کاربر')} ({uname})",
            callback_data=f"adm:u_view:{u.get('telegram_id')}",
        )
    kb.button(text="🔙 بازگشت به مدیریت کاربران", callback_data="adm:users_menu")
    kb.adjust(1)

    await message.answer(
        f"🔍 <b>نتایج جستجو برای «{query}» ({len(users)} کاربر):</b>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "adm:u_recent")
async def cb_admin_users_recent(callback: types.CallbackQuery):
    """نمایش لیست ۲۰ کاربر اخیر ثبت‌نامی."""
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    users = await database.get_recent_users(20)
    if not users:
        return await callback.answer("هیچ کاربری یافت نشد.", show_alert=True)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    for u in users:
        uname = f"@{u.get('username')}" if u.get("username") else str(u.get("telegram_id"))
        kb.button(
            text=f"👤 {u.get('first_name', 'کاربر')[:15]} ({uname})",
            callback_data=f"adm:u_view:{u.get('telegram_id')}",
        )
    kb.button(text="🔙 بازگشت به منوی کاربران", callback_data="adm:users_menu")
    kb.adjust(1)

    await callback.message.edit_text(
        "📋 <b>لیست ۲۰ کاربر اخیر ثبت‌نامی در ربات:</b>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:u_view:"))
async def cb_admin_user_view(callback: types.CallbackQuery):
    """نمایش پروفایل کاربری و اکشن‌های مدیریتی."""
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    target_uid = int(callback.data.split(":")[2])
    await _show_user_card(callback.message, target_uid, is_edit=True)
    await callback.answer()


async def _show_user_card(message: types.Message, target_uid: int, is_edit: bool = False):
    u = await database.get_user(target_uid)
    if not u:
        return await message.answer("❌ کاربر یافت نشد.")

    acc_count = await database.get_user_accounts_count(target_uid)
    ref_stats = await database.get_referral_stats(target_uid)
    uname = f"@{u.get('username')}" if u.get("username") else "ندارد"

    card_text = (
        "👤 <b>پروفایل و مشخصات کاربر در سامانه</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 شناسه تلگرام: <code>{target_uid}</code>\n"
        f"👤 نام: <b>{u.get('first_name', '—')}</b>\n"
        f"📎 نام کاربری: <b>{uname}</b>\n"
        f"💰 موجودی کیف پول: <b>{to_toman(u.get('wallet_balance', 0))}</b>\n"
        f"📦 تعداد اکانت‌های فعال: <b>{to_fa(acc_count)} عدد</b>\n"
        f"👥 تعداد زیرمجموعه‌ها: <b>{to_fa(ref_stats.get('total_referrals', 0))} نفر</b>\n"
        f"💵 درآمد معرف: <b>{to_toman(ref_stats.get('total_commission', 0))}</b>\n"
        f"🎁 اکانت تستی: <b>{'استفاده شده' if u.get('trial_used') else 'استفاده نشده'}</b>\n"
        f"📅 تاریخ ثبت‌نام: <i>{str(u.get('created_at', '—'))[:19]}</i>\n\n"
        "👇 عملیات مورد نظر روی این کاربر را انتخاب فرمایید:"
    )

    kb = admin_user_card_keyboard(target_uid)
    if is_edit:
        await message.edit_text(card_text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(card_text, reply_markup=kb, parse_mode="HTML")


# ── افزایش موجودی کیف پول توسط مدیر ──
@router.callback_query(F.data.startswith("adm:u_bal_add:"))
async def cb_admin_user_bal_add_start(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    target_uid = int(callback.data.split(":")[2])
    await state.set_state(AdminUserStates.waiting_balance_add)
    await state.update_data(target_uid=target_uid)
    await callback.message.answer(
        f"💰 <b>افزایش موجودی کاربر {target_uid}</b>\n\nلطفاً مبلغ مورد نظر به <b>تومان</b> را ارسال فرمایید:",
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminUserStates.waiting_balance_add)
async def process_admin_user_bal_add(message: types.Message, state: FSMContext):
    if not _is_admin(message):
        return
    text = (message.text or "").strip()
    if text == "❌ لغو":
        await state.clear()
        return await message.answer("❌ عملیات لغو شد.", reply_markup=get_main_keyboard(True))

    data = await state.get_data()
    target_uid = data.get("target_uid")
    await state.clear()

    try:
        amount = int(text.replace(",", ""))
        if amount <= 0:
            raise ValueError()
    except Exception:
        return await message.answer("❌ مبلغ نامعتبر است.", reply_markup=get_main_keyboard(True))

    new_bal = await database.update_wallet_balance(target_uid, amount)
    await database.create_transaction(target_uid, amount, "admin_deposit", "admin", status="approved")

    # ارسال اعلان برای کاربر
    try:
        await message.bot.send_message(
            target_uid,
            f"🎉 <b>کیف پول شما توسط مدیریت شارژ گردید!</b>\n\n"
            f"💰 مبلغ افزوده شده: <b>{to_toman(amount)}</b>\n"
            f"💳 موجودی جدید: <b>{to_toman(new_bal)}</b>",
            parse_mode="HTML",
        )
    except Exception:
        pass

    await message.answer(
        f"✅ موجودی کاربر <code>{target_uid}</code> به میزان <b>{to_toman(amount)}</b> افزایش یافت.\n"
        f"موجودی جدید: <b>{to_toman(new_bal)}</b>",
        reply_markup=get_main_keyboard(True),
        parse_mode="HTML",
    )


# ── کسر از موجودی کیف پول توسط مدیر ──
@router.callback_query(F.data.startswith("adm:u_bal_sub:"))
async def cb_admin_user_bal_sub_start(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    target_uid = int(callback.data.split(":")[2])
    await state.set_state(AdminUserStates.waiting_balance_sub)
    await state.update_data(target_uid=target_uid)
    await callback.message.answer(
        f"💸 <b>کسر از موجودی کاربر {target_uid}</b>\n\nلطفاً مبلغ کسر به <b>تومان</b> را وارد فرمایید:",
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminUserStates.waiting_balance_sub)
async def process_admin_user_bal_sub(message: types.Message, state: FSMContext):
    if not _is_admin(message):
        return
    text = (message.text or "").strip()
    if text == "❌ لغو":
        await state.clear()
        return await message.answer("❌ لغو شد.", reply_markup=get_main_keyboard(True))

    data = await state.get_data()
    target_uid = data.get("target_uid")
    await state.clear()

    try:
        amount = int(text.replace(",", ""))
        if amount <= 0:
            raise ValueError()
    except Exception:
        return await message.answer("❌ مبلغ نامعتبر است.", reply_markup=get_main_keyboard(True))

    new_bal = await database.update_wallet_balance(target_uid, -amount)
    await database.create_transaction(target_uid, amount, "admin_deduct", "admin", status="approved")

    try:
        await message.bot.send_message(
            target_uid,
            f"ℹ️ <b>کسر از موجودی کیف پول توسط مدیریت</b>\n\n"
            f"💸 مبلغ کسر شده: <b>{to_toman(amount)}</b>\n"
            f"💳 موجودی جدید: <b>{to_toman(new_bal)}</b>",
            parse_mode="HTML",
        )
    except Exception:
        pass

    await message.answer(
        f"✅ مبلغ <b>{to_toman(amount)}</b> از موجودی کاربر <code>{target_uid}</code> کسر گردید.\n"
        f"موجودی جدید: <b>{to_toman(new_bal)}</b>",
        reply_markup=get_main_keyboard(True),
        parse_mode="HTML",
    )


# ── ارسال پیام مستقیم / تیکت به کاربر توسط مدیر ──
@router.callback_query(F.data.startswith("adm:u_msg:"))
async def cb_admin_user_msg_start(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    target_uid = int(callback.data.split(":")[2])
    await state.set_state(AdminUserStates.waiting_direct_message)
    await state.update_data(target_uid=target_uid)
    await callback.message.answer(
        f"💬 <b>ارسال پیام مستقیم به کاربر {target_uid}</b>\n\nمتن پیام خود را تایپ و ارسال فرمایید:",
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminUserStates.waiting_direct_message)
async def process_admin_user_msg(message: types.Message, state: FSMContext):
    if not _is_admin(message):
        return
    text = (message.text or "").strip()
    if text == "❌ لغو":
        await state.clear()
        return await message.answer("❌ عملیات ارسال پیام لغو شد.", reply_markup=get_main_keyboard(True))

    data = await state.get_data()
    target_uid = data.get("target_uid")
    await state.clear()

    try:
        await message.bot.send_message(
            target_uid,
            f"📩 <b>پیام اختصاصی از طرف پشتیبانی و مدیریت:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{text}",
            parse_mode="HTML",
        )
        await message.answer(f"✅ پیام شما با موفقیت برای کاربر <code>{target_uid}</code> ارسال شد.", reply_markup=get_main_keyboard(True))
    except Exception as e:
        await message.answer(f"❌ خطا در ارسال پیام به کاربر (احتمالاً ربات را بلاک کرده است): {e}", reply_markup=get_main_keyboard(True))


# ── صدور فاکتور دستی برای کاربر ──
@router.callback_query(F.data.startswith("adm:u_inv:"))
async def cb_admin_user_inv_start(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    target_uid = int(callback.data.split(":")[2])
    await state.set_state(AdminUserStates.waiting_invoice_amount)
    await state.update_data(target_uid=target_uid)
    await callback.message.answer(
        f"🧾 <b>صدور فاکتور / تراکنش پرداخت برای کاربر {target_uid}</b>\n\n"
        "لطفاً مبلغ فاکتور به <b>تومان</b> و توضیحات را به صورت <code>مبلغ,توضیحات</code> ارسال فرمایید:\n"
        "مثال: <code>75000,اشتراک ماهانه VIP</code>",
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminUserStates.waiting_invoice_amount)
async def process_admin_user_inv(message: types.Message, state: FSMContext):
    if not _is_admin(message):
        return
    text = (message.text or "").strip()
    if text == "❌ لغو":
        await state.clear()
        return await message.answer("❌ صدور فاکتور لغو شد.", reply_markup=get_main_keyboard(True))

    data = await state.get_data()
    target_uid = data.get("target_uid")
    await state.clear()

    parts = text.split(",", 1)
    try:
        amount = int(parts[0].strip().replace(",", ""))
        desc = parts[1].strip() if len(parts) > 1 else "فاکتور صادره مدیریت"
    except Exception:
        return await message.answer("❌ فرمت ورودی نامعتبر است.", reply_markup=get_main_keyboard(True))

    tx_id = await database.create_transaction(target_uid, amount, "invoice", "admin", status="pending")
    card = await database.get_random_bank_card()

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 پرداخت و ارسال فیش واریز", callback_data="wllt:card")

    try:
        await message.bot.send_message(
            target_uid,
            f"🧾 <b>فاکتور جدید صادر شد!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"بابت: <b>{desc}</b>\n"
            f"💰 مبلغ فاکتور: <b>{to_toman(amount)}</b>\n"
            f"شماره تراکنش: <code>#{tx_id}</code>\n\n"
            f"💳 کارت جهت واریز:\n<code>{card.get('card_number')}</code>\nبه نام: <b>{card.get('card_holder')}</b>",
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass

    await message.answer(
        f"✅ فاکتور شماره #{tx_id} به مبلغ <b>{to_toman(amount)}</b> برای کاربر <code>{target_uid}</code> ارسال شد.",
        reply_markup=get_main_keyboard(True),
    )


# ── صدور و فعال‌سازی مستقیم اکانت توسط مدیر ──
@router.callback_query(F.data.startswith("adm:u_acc_cat:"))
async def cb_admin_user_acc_cat(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    target_uid = int(callback.data.split(":")[2])
    cats = await database.get_active_categories()

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    for c in cats:
        kb.button(text=f"{c.get('icon', '📦')} {c.get('title')}", callback_data=f"adm:u_acc_p_list:{target_uid}:{c.get('key')}")
    kb.button(text="🔙 بازگشت به مشخصات کاربر", callback_data=f"adm:u_view:{target_uid}")
    kb.adjust(1)

    await callback.message.edit_text(
        f"📦 <b>صدور مستقیم اکانت برای کاربر {target_uid}</b>\n\nدسته‌بندی مورد نظر را انتخاب فرمایید:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:u_acc_p_list:"))
async def cb_admin_user_acc_plist(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    parts = callback.data.split(":")
    target_uid = int(parts[2])
    cat_key = parts[3]
    plans = await database.get_plans_by_category(cat_key)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    for p in plans:
        kb.button(text=f"🎁 صدور: {p.get('name')}", callback_data=f"adm:u_acc_make:{target_uid}:{p.get('id')}")
    kb.button(text="🔙 بازگشت", callback_data=f"adm:u_acc_cat:{target_uid}")
    kb.adjust(1)

    await callback.message.edit_text("پلن مورد نظر جهت فعال‌سازی رایگان را انتخاب فرمایید:", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("adm:u_acc_make:"))
async def cb_admin_user_acc_make(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    parts = callback.data.split(":")
    target_uid = int(parts[2])
    plan_id = int(parts[3])
    plan = await database.get_plan_by_id(plan_id)
    if not plan:
        return await callback.answer("پلن یافت نشد.", show_alert=True)

    await callback.answer("در حال ساخت اکانت در پنل...")
    cat = plan.get("category_key", "singbox")
    rand_suffix = secrets.token_hex(2)

    if cat == "wireguard":
        u_name = f"ms_wg_{target_uid}_{rand_suffix}"
        res = await panel_api.create_wireguard_account(name=u_name, traffic_limit_gb=plan.get("traffic_gb", 30), validity_days=plan.get("duration_days", 30))
        acc_id = await database.save_account(target_uid, u_name, plan.get("name"), category="wireguard", panel_password=res.get("public_key"), server_info=res.get("config", ""), traffic_gb=plan.get("traffic_gb"), duration_days=plan.get("duration_days"))
    elif cat in ["system_l2tp", "dnstt"]:
        u_name = f"ms_sys_{target_uid}_{rand_suffix}"
        pwd = f"Ms{secrets.token_hex(3)}"
        await panel_api.create_l2tp_user(u_name, pwd, plan.get("traffic_gb", 30), plan.get("duration_days", 30))
        acc_id = await database.save_account(target_uid, u_name, plan.get("name"), category=cat, panel_password=pwd, server_info=settings.SERVER_IP, traffic_gb=plan.get("traffic_gb"), duration_days=plan.get("duration_days"))
    else:
        u_name = f"ms_sb_{target_uid}_{rand_suffix}"
        res = await panel_api.create_user(u_name, traffic_limit_gb=plan.get("traffic_gb", 30), validity_days=plan.get("duration_days", 30))
        u_data = res.get("user", {})
        sub_tok = u_data.get("sub_token", "")
        sub_url = u_data.get("sub_url", f"{settings.PANEL_SUB_URL}/{sub_tok}")
        acc_id = await database.save_account(target_uid, u_name, plan.get("name"), category=cat, sub_token=sub_tok, sub_url=sub_url, traffic_gb=plan.get("traffic_gb"), duration_days=plan.get("duration_days"))

    try:
        await callback.bot.send_message(
            target_uid,
            f"🎉 <b>یک اشتراک جدید توسط مدیریت برای شما فعال شد!</b>\n\n"
            f"🏷 پلن: <b>{plan.get('name')}</b>\n"
            f"👤 نام کاربری: <code>{u_name}</code>\n\n"
            "جهت مشاهده جزئیات اتصال و لینک‌ها، وارد بخش «📦 اکانت‌های من» شوید.",
            parse_mode="HTML",
        )
    except Exception:
        pass

    await callback.message.edit_text(
        f"✅ اکانت <b>{plan.get('name')}</b> با موفقیت برای کاربر <code>{target_uid}</code> فعال شد و به ایشان اطلاع‌رسانی گردید.",
        reply_markup=admin_users_menu_keyboard(),
        parse_mode="HTML",
    )


# ── بررسی تراکنش‌های کاربر توسط مدیر ──
@router.callback_query(F.data.startswith("adm:u_txs:"))
async def cb_admin_user_txs(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    target_uid = int(callback.data.split(":")[2])
    txs = await database.get_user_transactions(target_uid, 15)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    if not txs:
        kb.button(text="🔙 بازگشت به مشخصات کاربر", callback_data=f"adm:u_view:{target_uid}")
        return await callback.message.edit_text("📭 هیچ تراکنشی برای این کاربر ثبت نشده است.", reply_markup=kb.as_markup())

    lines = [f"💳 <b>تراکنش‌های اخیر کاربر {target_uid}:</b>\n"]
    for t in txs:
        status_icon = "✅" if t.get("status") == "approved" else ("❌" if t.get("status") == "rejected" else "⏳")
        lines.append(f"{status_icon} تراکنش #{t.get('id')} — {to_toman(t.get('amount'))} [{t.get('type')}]")
        if t.get("status") == "pending":
            kb.button(text=f"🔍 بررسی فیش #{t.get('id')}", callback_data=f"adm:tx_view:{t.get('id')}")

    kb.button(text="🔙 بازگشت به مشخصات کاربر", callback_data=f"adm:u_view:{target_uid}")
    kb.adjust(1)
    await callback.message.edit_text("\n".join(lines), reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


# ── بررسی اکانت‌های کاربر توسط مدیر ──
@router.callback_query(F.data.startswith("adm:u_accs:"))
async def cb_admin_user_accs(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    target_uid = int(callback.data.split(":")[2])
    accs = await database.get_user_accounts(target_uid)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    if not accs:
        kb.button(text="🔙 بازگشت به مشخصات کاربر", callback_data=f"adm:u_view:{target_uid}")
        return await callback.message.edit_text("📭 این کاربر هیچ اکانتی ندارد.", reply_markup=kb.as_markup())

    lines = [f"📦 <b>اشتراک‌های فعال کاربر {target_uid}:</b>\n"]
    for a in accs:
        lines.append(f"▫️ #{a.get('id')} - {a.get('plan_name')} (<code>{a.get('panel_username')}</code>) [{a.get('category')}]")
        kb.button(text=f"🗑 حذف اکانت #{a.get('id')}", callback_data=f"adm:u_acc_del:{target_uid}:{a.get('id')}")

    kb.button(text="🔙 بازگشت به مشخصات کاربر", callback_data=f"adm:u_view:{target_uid}")
    kb.adjust(1)
    await callback.message.edit_text("\n".join(lines), reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adm:u_acc_del:"))
async def cb_admin_user_acc_delete(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    parts = callback.data.split(":")
    target_uid = int(parts[2])
    acc_id = int(parts[3])

    account = await database.get_account_by_id(acc_id)
    if account:
        cat = account.get("category", "singbox")
        uname = account.get("panel_username", "")
        try:
            if cat in ["singbox", "v2ray", "reality"]:
                await panel_api.delete_user(uname)
            elif cat in ["system_l2tp", "dnstt"]:
                await panel_api.delete_l2tp_user(uname)
            elif cat == "wireguard":
                await panel_api.delete_wireguard_account(account.get("panel_password", ""))
        except Exception:
            pass
        await database.delete_account(acc_id)

    await callback.answer("اکانت حذف شد.", show_alert=True)
    await _show_user_card(callback.message, target_uid, is_edit=True)


# ──────────────────────────────────────────────────────────────
#  مدیریت مدیران ربات (Bot Admins Management)
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:admins_menu")
async def cb_admin_manage_admins(callback: types.CallbackQuery):
    """نمایش لیست مدیران و دکمه افزودن مدیر جدید."""
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    admins = await database.get_all_admins()
    lines = [
        "👑 <b>لیست مدیران ربات MS VPN:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
    ]
    for a in admins:
        uid = a.get("telegram_id")
        name = a.get("first_name") or a.get("username") or "—"
        is_owner = uid in settings.ADMIN_IDS
        badge = "⭐️ مدیر اصلی" if is_owner else "🔹 مدیر فرعی"
        lines.append(f"{badge}: <b>{name}</b> (<code>{uid}</code>)")

    lines.append("\n💡 جهت افزودن دسترسی مدیریت به یک کاربر، دکمه زیر را لمس نمایید:")
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=admin_manage_admins_keyboard(admins, settings.ADMIN_IDS),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "adm:admin_add")
async def cb_admin_add_start(callback: types.CallbackQuery, state: FSMContext):
    """شروع افزودن مدیر جدید."""
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    await state.set_state(AdminManageStates.waiting_new_admin_id)
    await callback.message.answer(
        "➕ <b>افزودن مدیر جدید به ربات:</b>\n\nلطفاً <b>شناسه عددی تلگرام (Telegram ID)</b> مدیر جدید را ارسال فرمایید:",
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminManageStates.waiting_new_admin_id)
async def process_admin_add(message: types.Message, state: FSMContext):
    """پردازش شناسه عددی مدیر جدید و ذخیره در دیتابیس."""
    if not _is_admin(message):
        return
    text = (message.text or "").strip()
    if text == "❌ لغو":
        await state.clear()
        return await message.answer("❌ عملیات لغو شد.", reply_markup=get_main_keyboard(True))

    try:
        new_adm_id = int(text)
        if new_adm_id <= 1000:
            raise ValueError()
    except Exception:
        return await message.answer("❌ شناسه عددی نامعتبر است. لطفاً یک عدد صحیح معتبر ارسال فرمایید.")

    await state.clear()
    ok = await database.add_bot_admin(new_adm_id, added_by=message.from_user.id)
    if not ok:
        return await message.answer("⚠️ این کاربر قبلاً در لیست مدیران بوده است.", reply_markup=get_main_keyboard(True))

    # ارسال پیام تبریک به مدیر جدید
    try:
        await message.bot.send_message(
            new_adm_id,
            "🎉 <b>دسترسی مدیریت ربات MS VPN به شما اعطا گردید!</b>\n\n"
            "از هم‌اکنون منوی 👑 <b>پنل مدیریت</b> برای شما فعال شده و می‌توانید بر سیستم نظارت داشته باشید.",
            reply_markup=get_main_keyboard(True),
            parse_mode="HTML",
        )
    except Exception:
        pass

    await message.answer(
        f"✅ کاربر با شناسه <code>{new_adm_id}</code> با موفقیت به عنوان مدیر به ربات افزوده شد.",
        reply_markup=get_main_keyboard(True),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm:admin_del:"))
async def cb_admin_del(callback: types.CallbackQuery):
    """حذف دسترسی مدیریت از کاربر."""
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    target_uid = int(callback.data.split(":")[2])
    if target_uid in settings.ADMIN_IDS:
        return await callback.answer("امکان حذف مدیر اصلی وجود ندارد.", show_alert=True)

    await database.remove_bot_admin(target_uid)
    await callback.answer(f"دسترسی مدیریت {target_uid} حذف شد.", show_alert=True)

    admins = await database.get_all_admins()
    await callback.message.edit_reply_markup(reply_markup=admin_manage_admins_keyboard(admins, settings.ADMIN_IDS))


# ──────────────────────────────────────────────────────────────
#  مدیریت و ویرایش آموزش‌ها (Tutorials Management)
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:tutorials")
async def cb_admin_tutorials_menu(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    await state.clear()
    text = (
        "📚 <b>مدیریت و ویرایش آموزش‌ها و راهنماهای اتصال</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "در این بخش می‌توانید متن هر یک از آموزش‌های ربات (اندروید، آیفون، ویندوز، وایرگارد، سیسکو و...) "
        "را به دلخواه خود ویرایش فرمایید یا به متن پیش‌فرض بازگردانید.\n\n"
        "👇 لطفاً آموزش مورد نظر جهت ویرایش را انتخاب فرمایید:"
    )
    await callback.message.edit_text(text, reply_markup=admin_tutorials_list_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adm:tut_view:"))
async def cb_admin_tut_view(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    if state:
        await state.clear()
    tut_key = callback.data.split(":")[2]
    title = TUTORIAL_TITLES.get(tut_key, tut_key)
    current_text = await get_tutorial_text(tut_key)
    is_custom = await is_tutorial_customized(tut_key)
    status_str = "🟡 سفارشی (ویرایش‌شده توسط مدیر)" if is_custom else "🟢 پیش‌فرض سیستم"

    preview = (
        f"📚 <b>آموزش: {title}</b>\n"
        f"▫️ وضعیت فعلی: <b>{status_str}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📝 <b>متن فعلی آموزش:</b>\n\n"
        f"{current_text}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👇 جهت ویرایش یا بازنشانی، از دکمه‌های زیر استفاده فرمایید:"
    )
    await callback.message.edit_text(
        preview,
        reply_markup=admin_tutorial_detail_keyboard(tut_key, is_custom),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:tut_edit:"))
async def cb_admin_tut_edit(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    tut_key = callback.data.split(":")[2]
    title = TUTORIAL_TITLES.get(tut_key, tut_key)
    await state.set_state(AdminTutorialStates.waiting_tutorial_text)
    await state.update_data(target_tut_key=tut_key)
    await callback.message.answer(
        f"✏️ <b>ویرایش آموزش: {title}</b>\n\n"
        "لطفاً متن جدید آموزش را ارسال فرمایید.\n"
        "💡 می‌توانید از تگ‌های HTML مانند <code>&lt;b&gt;</code>، <code>&lt;code&gt;</code> و <code>&lt;a href='...'&gt;</code> استفاده فرمایید.",
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminTutorialStates.waiting_tutorial_text)
async def state_save_tutorial_text(message: types.Message, state: FSMContext):
    if not _is_admin(message):
        return
    text = (message.text or message.caption or "").strip()
    if text == "❌ لغو":
        await state.clear()
        return await message.answer("❌ عملیات ویرایش آموزش لغو شد.", reply_markup=get_main_keyboard(True))

    data = await state.get_data()
    tut_key = data.get("target_tut_key")
    if not tut_key:
        await state.clear()
        return await message.answer("خطا در بازیابی کلید آموزش.", reply_markup=get_main_keyboard(True))

    await set_tutorial_text(tut_key, text)
    title = TUTORIAL_TITLES.get(tut_key, tut_key)
    await state.clear()
    await message.answer(
        f"✅ <b>متن آموزش «{title}» با موفقیت ذخیره و به‌روزرسانی شد!</b>\n\n"
        "از هم‌اکنون تمامی کاربران متن جدید را در بخش راهنما مشاهده خواهند کرد.",
        reply_markup=get_main_keyboard(True),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm:tut_reset:"))
async def cb_admin_tut_reset(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    tut_key = callback.data.split(":")[2]
    await reset_tutorial_text(tut_key)
    await callback.answer("✅ متن آموزش به حالت پیش‌فرض بازنشانی شد.", show_alert=True)
    await cb_admin_tut_view(callback, None)


# ──────────────────────────────────────────────────────────────
#  مدیریت دانلود نرم‌افزارها (App Downloads Management)
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:downloads")
async def cb_admin_downloads_menu(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    await state.clear()
    text = (
        "📲 <b>مدیریت لینک‌های دانلود نرم‌افزارها</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "در این بخش می‌توانید لینک دانلود مستقیم هر یک از کلاینت‌ها (اندروید، iOS، ویندوز و...) "
        "را تغییر داده و لینک‌های دلخواه، کانال تلگرام یا هاست اختصاصی خود را جایگزین فرمایید.\n\n"
        "👇 لطفاً نرم‌افزار مورد نظر را انتخاب فرمایید:"
    )
    await callback.message.edit_text(text, reply_markup=admin_downloads_list_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adm:dl_view:"))
async def cb_admin_dl_view(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    if state:
        await state.clear()
    dl_key = callback.data.split(":")[2]
    title = CLIENT_DOWNLOAD_TITLES.get(dl_key, dl_key)
    current_url = await get_download_url(dl_key)
    is_custom = await is_download_customized(dl_key)
    status_str = "🟡 سفارشی (ویرایش‌شده توسط مدیر)" if is_custom else "🟢 پیش‌فرض رسمی"

    text = (
        f"📲 <b>نرم‌افزار: {title}</b>\n"
        f"▫️ وضعیت: <b>{status_str}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔗 <b>لینک فعلی دانلود:</b>\n"
        f"<code>{current_url}</code>\n\n"
        "جهت تغییر این لینک، دکمه «✏️ تغییر لینک دانلود» را لمس کنید:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_download_detail_keyboard(dl_key, is_custom),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:dl_edit:"))
async def cb_admin_dl_edit(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    dl_key = callback.data.split(":")[2]
    title = CLIENT_DOWNLOAD_TITLES.get(dl_key, dl_key)
    await state.set_state(AdminTutorialStates.waiting_download_url)
    await state.update_data(target_dl_key=dl_key)
    await callback.message.answer(
        f"✏️ <b>تغییر لینک دانلود: {title}</b>\n\n"
        "لطفاً لینک جدید را ارسال فرمایید (حتماً با <code>https://</code> یا <code>http://</code> یا <code>tg://</code> شروع شود):",
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminTutorialStates.waiting_download_url)
async def state_save_download_url(message: types.Message, state: FSMContext):
    if not _is_admin(message):
        return
    text = (message.text or "").strip()
    if text == "❌ لغو":
        await state.clear()
        return await message.answer("❌ عملیات تغییر لینک لغو شد.", reply_markup=get_main_keyboard(True))

    if not (text.startswith("http://") or text.startswith("https://") or text.startswith("tg://")):
        return await message.answer("❌ لینک نامعتبر است! لطفاً لینکی ارسال فرمایید که با https:// شروع شود:")

    data = await state.get_data()
    dl_key = data.get("target_dl_key")
    if not dl_key:
        await state.clear()
        return await message.answer("خطا در بازیابی کلید نرم‌افزار.", reply_markup=get_main_keyboard(True))

    await set_download_url(dl_key, text)
    title = CLIENT_DOWNLOAD_TITLES.get(dl_key, dl_key)
    await state.clear()
    await message.answer(
        f"✅ <b>لینک دانلود «{title}» با موفقیت به‌روزرسانی شد!</b>\n\n"
        f"🔗 لینک جدید: <code>{text}</code>",
        reply_markup=get_main_keyboard(True),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm:dl_reset:"))
async def cb_admin_dl_reset(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    dl_key = callback.data.split(":")[2]
    await reset_download_url(dl_key)
    await callback.answer("✅ لینک دانلود به حالت پیش‌فرض بازنشانی شد.", show_alert=True)
    await cb_admin_dl_view(callback, None)

