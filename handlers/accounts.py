"""هندلر مدیریت اکانت‌ها: نمایش تفکیک‌شده بر اساس پروتکل (Sing-box, L2TP, WireGuard, GAS, DNS Tunnel)."""
import io
import os
import re
import json
import base64
import logging
import secrets
import uuid
import zipfile
import qrcode
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from api import panel_api
from config import settings
from db import database
from filters.auth import IsAuthorized
from keyboards.inline import (
    build_accounts_keyboard,
    account_details_keyboard,
    account_configs_keyboard,
    slipnet_protocols_keyboard,
    account_reset_confirm_keyboard,
    account_convert_categories_keyboard,
    account_convert_plans_keyboard,
    account_convert_confirm_keyboard,
    account_renew_plans_keyboard,
    account_renew_confirm_keyboard,
    account_upgrade_plans_keyboard,
    account_upgrade_confirm_keyboard,
    account_gift_select_keyboard,
    account_gift_confirm_keyboard,
    config_search_result_keyboard,
    user_categories_menu_keyboard,
    user_category_view_keyboard,
    user_cat_delete_confirm_keyboard,
    user_assign_category_keyboard,
    account_delete_confirm_keyboard,
    wireguard_multiport_keyboard,
    wireguard_single_port_keyboard,
)
from keyboards.reply import main_menu_keyboard, cancel_keyboard
from states.forms import ConfigSearchStates, AccountGiftStates, UserAccountManageStates
from utils.formatters import format_accounts_list, format_account_details, format_searched_config
from utils.helpers import (
    api_error_text,
    to_toman,
    to_fa,
    calculate_account_refund,
    make_qr_code_file,
    sanitize_wireguard_conf,
    make_clean_wg_filename,
    format_config_with_brand,
)
from utils.cert_manager import (
    get_ovpn_content,
    CISCO_CA_PATH,
    IKEV2_CA_PATH,
    SSTP_CA_PATH,
)

logger = logging.getLogger("MS_VPN_BOT.accounts")
router = Router(name="accounts")
router.message.filter(IsAuthorized())
router.callback_query.filter(IsAuthorized())

V2RAY_INBOUNDS = [
    "vmess-in", "vmess-ws-tls", "vmess-grpc-tls", "vmess-upgrade-tls",
    "vless-ws-in", "vless-grpc-tls", "vless-upgrade-tls", "vless-tcp-tls"
]

REALITY_INBOUNDS = [
    "vless-reality-in", "vless-reality-grpc", "vless-reality-upgrade"
]


@router.message(F.text == "📦 اکانت‌های من")
async def show_my_accounts(message: types.Message):
    telegram_id = message.from_user.id
    categories = await database.get_user_categories(telegram_id)
    accounts = await database.get_user_accounts(telegram_id)

    text = format_accounts_list(accounts)
    kb = build_accounts_keyboard(accounts, user_categories=categories) if (accounts or categories) else None
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "acc:list")
async def cb_accounts_list(callback: types.CallbackQuery):
    telegram_id = callback.from_user.id
    categories = await database.get_user_categories(telegram_id)
    accounts = await database.get_user_accounts(telegram_id)

    text = format_accounts_list(accounts)
    kb = build_accounts_keyboard(accounts, user_categories=categories) if (accounts or categories) else None
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("acc:filter:"))
async def cb_accounts_filter(callback: types.CallbackQuery):
    cat_arg = callback.data.split(":")[2]
    telegram_id = callback.from_user.id
    categories = await database.get_user_categories(telegram_id)

    if cat_arg == "all":
        current_cat_id = None
        accounts = await database.get_user_accounts(telegram_id)
        header = ""
    else:
        current_cat_id = int(cat_arg)
        accounts = await database.get_user_accounts(telegram_id, user_category_id=current_cat_id)
        selected_cat = next((c for c in categories if c.get("id") == current_cat_id), None)
        cat_title = selected_cat.get("name") if selected_cat else "دسته انتخابی"
        header = f"📁 <b>اکانت‌های پوشه «{cat_title}» ({to_fa(len(accounts))} عدد):</b>\n\n"

    text = format_accounts_list(accounts)
    if header and accounts:
        text = header + text
    elif header and not accounts:
        text = f"📭 هیچ اکانتی در پوشه «{cat_title}» قرار ندارد."

    kb = build_accounts_keyboard(accounts, user_categories=categories, current_cat_id=current_cat_id)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("acc:view:"))
async def cb_view_account(callback: types.CallbackQuery):
    """مشاهده مشخصات و وضعیت اتصال اکانت."""
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    cat = account.get("category", "singbox")
    panel_user = account.get("panel_username")

    srv_ip = await database.get_setting("server_ip", settings.SERVER_IP)
    psk = await database.get_setting("ipsec_psk", settings.IPSEC_PSK)

    live_data = None
    if cat in ("singbox", "v2ray", "reality"):
        live_data = await panel_api.get_user_details(panel_user)
        if account.get("is_trial") and live_data and live_data.get("success"):
            u_info = live_data.get("user", {})
            if u_info.get("is_expired") or u_info.get("is_quota_exceeded"):
                from utils.trial_manager import delete_trial_from_panel
                await delete_trial_from_panel(account)
                await database.delete_account(account_id)
                return await callback.message.edit_text(
                    "⏳ <b>مهلت استفاده از این اکانت تستی به پایان رسیده است.</b>\n\n"
                    "این اکانت جهت بهینه‌سازی منابع سرور به صورت خودکار از پنل حذف گردید.\n"
                    "جهت تهیه اشتراک دائمی و پرسرعت، از بخش «🛒 خرید اشتراک» اقدام فرمایید.",
                    parse_mode="HTML"
                )
    elif cat == "wireguard":
        live_data = await panel_api.get_wireguard_peer_details(account.get("panel_password") or panel_user)
    elif cat == "amneziawg":
        live_data = await panel_api.get_amneziawg_peer_details(account.get("panel_password") or panel_user)

    text = format_account_details(account, live_data if (live_data and live_data.get("success")) else None, server_ip=srv_ip, psk=psk)
    sub_url = account.get("sub_url") or (live_data.get("sub_url") if live_data else "")

    await callback.message.edit_text(
        text,
        reply_markup=account_details_keyboard(account_id, category=cat, sub_url=sub_url),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("acc:configs:"))
async def cb_account_configs(callback: types.CallbackQuery):
    """دریافت کانفیگ‌های تکی هسته Sing-box."""
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    live_data = await panel_api.get_user_details(account.get("panel_username"))
    if not live_data.get("success"):
        return await callback.answer(f"خطا در دریافت کانفیگ‌ها: {api_error_text(live_data)}", show_alert=True)

    configs = live_data.get("configs", [])
    if not configs:
        return await callback.answer("هیچ کانفیگی برای این اکانت یافت نشد.", show_alert=True)

    text = (
        f"⚡ <b>کانفیگ‌های مجزای اکانت {account.get('panel_username')}</b>\n\n"
        "جهت کپی لینک اتصال مستقیم، پروتکل مورد نظر را انتخاب فرمایید:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=account_configs_keyboard(account_id, configs),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("acc:cfg_view:"))
async def cb_single_config_view(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    account_id = int(parts[2])
    cfg_idx = int(parts[3])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    live_data = await panel_api.get_user_details(account.get("panel_username"))
    configs = live_data.get("configs", [])
    if cfg_idx >= len(configs):
        return await callback.answer("کانفیگ نامعتبر است.", show_alert=True)

    cfg = configs[cfg_idx]
    tag = cfg.get("tag", "کانفیگ")
    proto = cfg.get("type", "").upper()
    link = cfg.get("share_link", "")

    brand_name = await database.get_setting("brand_name", "MS VPN")
    inc_user = (await database.get_setting("brand_include_username", "1")) == "1"
    branded_link = format_config_with_brand(link, brand_name=brand_name, username=account.get("panel_username", ""), include_username=inc_user)

    cfg_text = (
        f"🔑 <b>کانفیگ تکی {proto} ({tag})</b>\n\n"
        f"<code>{branded_link}</code>\n\n"
        "💡 با لمس متن بالا، کانفیگ کپی خواهد شد."
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 بازگشت به لیست کانفیگ‌ها", callback_data=f"acc:configs:{account_id}")
    await callback.message.edit_text(cfg_text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("acc:view_qr:"))
async def cb_account_view_qr(callback: types.CallbackQuery):
    """تولید و ارسال بارکد QR سابسکریپشن جهت اسکن مستقیم کاربر."""
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    sub_url = account.get("sub_url")
    if not sub_url:
        live_data = await panel_api.get_user_details(account.get("panel_username"))
        if live_data and live_data.get("success"):
            sub_url = live_data.get("sub_url", "")

    if not sub_url:
        return await callback.answer("لینک سابسکریپشن برای این اکانت یافت نشد.", show_alert=True)

    uname = account.get("panel_username", "user")
    cname = account.get("custom_name")
    pname = account.get("plan_name", "اشتراک")
    title = f"{cname} ({pname})" if cname else pname

    qr_file = make_qr_code_file(sub_url, filename=f"qr_{uname}.png")
    caption = (
        f"📷 <b>بارکد QR اتصال به اشتراک {title}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 نام کاربری: <code>{uname}</code>\n\n"
        "🔗 <b>لینک هوشمند سابسکریپشن:</b>\n"
        f"<code>{sub_url}</code>\n\n"
        "💡 <i>جهت اتصال سریع، تصویر بارکد بالا را با دوربین موبایل یا داخل نرم‌افزار (v2rayNG, Sing-box, SlipNet) اسکن فرمایید.</i>"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 بازگشت به مشخصات اکانت", callback_data=f"acc:view:{account_id}")
    await callback.message.answer_photo(qr_file, caption=caption, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer("✅ بارکد QR ارسال شد.")


@router.callback_query(F.data.startswith("acc:dl_all_cfgs:"))
async def cb_download_all_configs(callback: types.CallbackQuery):
    """دانلود کلیه کانفیگ‌های تکی V2Ray / Sing-box در قالب یک فایل متنی (.txt)."""
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    await callback.answer("⏳ در حال ساخت فایل جامع کانفیگ‌ها...")
    live_data = await panel_api.get_user_details(account.get("panel_username"))
    configs = live_data.get("configs", []) if live_data else []
    if not configs:
        return await callback.message.answer("❌ هیچ کانفیگی در پنل برای این اکانت یافت نشد.")

    u = live_data.get("user", {}) if live_data else {}
    sub_url = account.get("sub_url") or (live_data.get("sub_url", "") if live_data else "")
    sub_b64 = account.get("sub_b64_url") or (live_data.get("sub_b64_url", "") if live_data else "")

    brand_name = await database.get_setting("brand_name", "MS VPN")
    inc_user = (await database.get_setting("brand_include_username", "1")) == "1"

    lines = [
        "=========================================",
        f"  {brand_name} - Configurations",
        f"  Username: {account.get('panel_username')}",
        f"  UUID: {u.get('uuid', '—')}",
        f"  Traffic Limit: {account.get('traffic_gb', 0)} GB",
        f"  Duration Days: {account.get('duration_days', 0)} Days",
        f"  Subscription URL: {sub_url}",
        f"  Base64 URL: {sub_b64}",
        "=========================================\n",
    ]
    for idx, cfg in enumerate(configs, 1):
        tag = cfg.get("tag", f"Config-{idx}")
        proto = cfg.get("type", "").upper()
        port = cfg.get("port", "")
        link = cfg.get("share_link", "")
        branded_link = format_config_with_brand(link, brand_name=brand_name, username=account.get("panel_username", ""), include_username=inc_user)
        lines.append(f"## {idx}. {proto} - {tag} (Port {port})\n{branded_link}\n")

    txt_content = "\n".join(lines)
    file_bytes = txt_content.encode("utf-8")
    clean_brand = re.sub(r'[^a-zA-Z0-9_\-]', '_', brand_name).strip('_') or "VPN"
    doc = BufferedInputFile(file_bytes, filename=f"{clean_brand}_{account.get('panel_username')}.txt")

    caption = (
        f"📦 <b>فایل جامع کانفیگ‌های اشتراک {account.get('panel_username')}</b>\n\n"
        f"تعداد کانفیگ‌ها: <b>{to_fa(len(configs))} عدد</b>\n"
        "شامل Reality, VMess, VLESS, Trojan, Hysteria 2 و TUIC.\n\n"
        "💡 می‌توانید این فایل را در کلاینت‌های دلخواه (v2rayNG, v2rayN, SlipNet) ایمپورت فرمایید."
    )
    await callback.message.answer_document(doc, caption=caption, parse_mode="HTML")


# ── دانلود فایل کانفیگ OpenVPN ──
@router.callback_query(F.data.startswith("acc:dl_ovpn:"))
async def cb_download_ovpn(callback: types.CallbackQuery):
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    uname = account.get("panel_username", "user")
    pwd = account.get("panel_password", "")
    srv_ip = await database.get_setting("server_ip", settings.SERVER_IP)
    brand_name = await database.get_setting("brand_name", "MS VPN")
    clean_brand = re.sub(r'[^a-zA-Z0-9_\-]', '_', brand_name).strip('_') or "VPN"

    ovpn_data = get_ovpn_content(server_ip=srv_ip, username=uname, password=pwd)
    filename = f"{clean_brand}_OpenVPN_{uname}.ovpn"

    doc = BufferedInputFile(ovpn_data.encode("utf-8"), filename=filename)
    caption = (
        f"🔒 <b>فایل کانفیگ اختصاصی OpenVPN</b>\n\n"
        f"👤 نام کاربری: <code>{uname}</code>\n"
        f"🔑 رمز عبور: <code>{pwd}</code>\n"
        f"🌐 آدرس سرور: <code>{srv_ip}:1194</code>\n\n"
        "💡 این فایل را در نرم‌افزار <b>OpenVPN Connect</b> وارد فرمایید و متصل شوید."
    )
    await callback.message.answer_document(document=doc, caption=caption, parse_mode="HTML")
    await callback.answer("✅ فایل کانفیگ OpenVPN ارسال شد.")


# ── دانلود سرتیفیکیت‌ها ──
@router.callback_query(F.data.startswith("acc:dl_cert:"))
async def cb_download_cert(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    account_id = int(parts[2])
    cert_type = parts[3]
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    cert_map = {
        "cisco": (CISCO_CA_PATH, "Cisco_AnyConnect_CA.crt", "گواهی امنیتی سیسکو (Cisco AnyConnect)"),
        "ikev2": (IKEV2_CA_PATH, "IKEv2_IPsec_CA.crt", "گواهی امنیتی پروتکل IKEv2 / IPsec"),
        "sstp": (SSTP_CA_PATH, "SSTP_CA.crt", "گواهی امنیتی پروتکل SSTP"),
    }

    if cert_type not in cert_map:
        return await callback.answer("نوع سرتیفیکیت نامعتبر است.", show_alert=True)

    path, fname, title = cert_map[cert_type]
    if not os.path.exists(path):
        return await callback.answer("فایل سرتیفیکیت در سرور یافت نشد.", show_alert=True)

    doc = FSInputFile(path=path, filename=fname)
    caption = (
        f"📜 <b>فایل سرتیفیکیت: {title}</b>\n\n"
        "💡 در صورت نیاز سیستم‌عامل به نصب دستی گواهی امنیتی، فایل بالا را در بخش Certificates سیستم‌عامل یا کلاینت خود نصب فرمایید."
    )
    await callback.message.answer_document(document=doc, caption=caption, parse_mode="HTML")
    await callback.answer("✅ سرتیفیکیت ارسال شد.")


# ── دانلود فایل کانفیگ WireGuard (.conf) ──
@router.callback_query(F.data.startswith("acc:dl_wg_conf:"))
async def cb_download_wg_conf(callback: types.CallbackQuery):
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    uname = account.get("panel_username", "wireguard")
    conf_content = account.get("server_info", "")
    if not conf_content:
        return await callback.answer("محتوای کانفیگ برای این اکانت ثبت نشده است.", show_alert=True)

    clean_conf = sanitize_wireguard_conf(conf_content)
    clean_filename = make_clean_wg_filename(uname)
    doc = BufferedInputFile(clean_conf.encode("utf-8"), filename=clean_filename)
    caption = (
        f"⚡ <b>فایل کانفیگ اختصاصی وایرگارد (WireGuard)</b>\n\n"
        f"👤 نام اکانت: <code>{uname}</code>\n"
        f"📄 نام استاندارد تانل: <code>{clean_filename[:-5]}</code>\n\n"
        "💡 فایل فوق با استانداردهای رسمی WireGuard بهینه‌سازی شده و در تمام نسخه‌های اندروید، iOS و ویندوز بدون خطای نام قابل استفاده است."
    )
    await callback.message.answer_document(document=doc, caption=caption, parse_mode="HTML")
    await callback.answer("✅ فایل کانفیگ وایرگارد ارسال شد.")


# ── دریافت بارکد QR کانفیگ WireGuard ──
@router.callback_query(F.data.startswith("acc:dl_wg_qr:"))
async def cb_download_wg_qr(callback: types.CallbackQuery):
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    uname = account.get("panel_username", "wireguard")
    conf_content = account.get("server_info", "")
    if not conf_content:
        return await callback.answer("محتوای کانفیگ یافت نشد.", show_alert=True)

    clean_conf = sanitize_wireguard_conf(conf_content)
    qr_filename = make_clean_wg_filename(f"qr_{uname}")[:-5] + ".png"
    photo = make_qr_code_file(clean_conf, filename=qr_filename)
    caption = (
        f"📷 <b>بارکد اختصاصی WireGuard جهت اسکن با گوشی</b>\n\n"
        f"👤 نام اکانت: <code>{uname}</code>\n"
        "💡 در نرم‌افزار رسمی WireGuard دکمه + را زده و گزینه <b>Scan from QR code</b> را انتخاب فرمایید."
    )
    await callback.message.answer_photo(photo=photo, caption=caption, parse_mode="HTML")
    await callback.answer("✅ بارکد QR ارسال شد.")


# ── مشاهده متن کانفیگ WireGuard ──
@router.callback_query(F.data.startswith("acc:view_wg_text:"))
async def cb_view_wg_text(callback: types.CallbackQuery):
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    uname = account.get("panel_username", "wireguard")
    conf_content = account.get("server_info", "")
    clean_conf = sanitize_wireguard_conf(conf_content)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 بازگشت به مشخصات اکانت", callback_data=f"acc:view:{account_id}")

    text = (
        f"📋 <b>متن کانفیگ وایرگارد ({uname})</b>\n\n"
        f"<pre>{clean_conf}</pre>\n\n"
        "💡 با لمس کادر بالا، کل متن کانفیگ کپی خواهد شد."
    )
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


# ── مدیریت پورت‌های چندگانه وایرگارد و AmneziaWG (Multiport) ──
@router.callback_query(F.data.startswith("acc:wg_multiport:"))
async def cb_wg_multiport(callback: types.CallbackQuery):
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    cat = account.get("category", "wireguard")
    is_awg = (cat == "amneziawg")

    if is_awg:
        configs = await panel_api.get_amneziawg_client_multiport(
            public_key=account.get("panel_password", ""),
            base_conf=account.get("server_info", ""),
        )
        proto_title = "وایرگارد پیشرفته (AmneziaWG)"
    else:
        configs = await panel_api.get_wireguard_client_multiport(
            public_key=account.get("panel_password", ""),
            base_conf=account.get("server_info", ""),
        )
        proto_title = "وایرگارد معمولی (WireGuard)"

    if not configs:
        return await callback.answer("کانفیگ‌های مولتی‌پورت در دسترس نیست.", show_alert=True)

    uname = account.get("panel_username", "wireguard")
    custom_name = account.get("custom_name")
    disp_name = f"{custom_name} ({uname})" if custom_name else uname

    text = (
        f"🔀 <b>پورت‌های اختصاصی اتصال {proto_title}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 نام اکانت: <b>{disp_name}</b>\n"
        f"📊 تعداد پورت‌های فعال: <b>{to_fa(len(configs))} پورت</b>\n\n"
        "💡 <i>این سرویس دارای چندین پورت فعال بر روی سرور می‌باشد. "
        "در صورتی که اینترنت شما بر روی یک پورت دچار اختلال یا افت سرعت شد، "
        "می‌توانید به راحتی از پورت‌های جایگزین زیر استفاده فرمایید.</i>\n\n"
        "👇 لطفاً پورت مورد نظر را جهت دریافت فایل یا بارکد انتخاب کنید:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=wireguard_multiport_keyboard(account_id, configs),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("acc:wg_p_view:"))
async def cb_wg_single_port_view(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    account_id = int(parts[2])
    port = int(parts[3])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    cat = account.get("category", "wireguard")
    is_awg = (cat == "amneziawg")
    uname = account.get("panel_username", "wireguard")
    clean_fname = make_clean_wg_filename(uname, port=port)
    proto_title = "وایرگارد پیشرفته (AmneziaWG)" if is_awg else "وایرگارد معمولی"

    text = (
        f"⚡ <b>کانفیگ {proto_title} — پورت {to_fa(port)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 نام کاربری: <code>{uname}</code>\n"
        f"📄 نام تانل استاندارد: <code>{clean_fname[:-5]}</code>\n"
        f"🔌 پورت اتصال: <code>{port}</code>\n\n"
        "👇 لطفاً یکی از گزینه‌های زیر را انتخاب فرمایید:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=wireguard_single_port_keyboard(account_id, port),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("acc:dl_wg_p_conf:"))
async def cb_dl_wg_port_conf(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    account_id = int(parts[2])
    port = int(parts[3])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    cat = account.get("category", "wireguard")
    is_awg = (cat == "amneziawg")

    if is_awg:
        configs = await panel_api.get_amneziawg_client_multiport(
            public_key=account.get("panel_password", ""),
            base_conf=account.get("server_info", ""),
        )
    else:
        configs = await panel_api.get_wireguard_client_multiport(
            public_key=account.get("panel_password", ""),
            base_conf=account.get("server_info", ""),
        )

    cfg_obj = next((c for c in configs if c.get("port") == port), None)
    conf_text = cfg_obj.get("config") if cfg_obj else sanitize_wireguard_conf(account.get("server_info", ""), port=port)

    uname = account.get("panel_username", "wireguard")
    clean_fname = make_clean_wg_filename(uname, port=port)
    doc = BufferedInputFile(conf_text.encode("utf-8"), filename=clean_fname)
    proto_title = "AmneziaWG" if is_awg else "WireGuard"

    caption = (
        f"⚡ <b>فایل کانفیگ اختصاصی {proto_title} — پورت {to_fa(port)}</b>\n\n"
        f"👤 نام کاربری: <code>{uname}</code>\n"
        f"📄 تانل: <code>{clean_fname[:-5]}</code>\n"
        f"🔌 پورت: <code>{port}</code>\n\n"
        "💡 فایل فوق با استانداردهای رسمی بهینه‌سازی شده و در تمام نسخه‌های اندروید، iOS و ویندوز بدون خطای نام قابل استفاده است."
    )
    await callback.message.answer_document(document=doc, caption=caption, parse_mode="HTML")
    await callback.answer(f"✅ فایل کانفیگ پورت {port} ارسال شد.")


@router.callback_query(F.data.startswith("acc:dl_wg_p_qr:"))
async def cb_dl_wg_port_qr(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    account_id = int(parts[2])
    port = int(parts[3])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    cat = account.get("category", "wireguard")
    is_awg = (cat == "amneziawg")

    if is_awg:
        configs = await panel_api.get_amneziawg_client_multiport(
            public_key=account.get("panel_password", ""),
            base_conf=account.get("server_info", ""),
        )
    else:
        configs = await panel_api.get_wireguard_client_multiport(
            public_key=account.get("panel_password", ""),
            base_conf=account.get("server_info", ""),
        )

    cfg_obj = next((c for c in configs if c.get("port") == port), None)
    conf_text = cfg_obj.get("config") if cfg_obj else sanitize_wireguard_conf(account.get("server_info", ""), port=port)

    uname = account.get("panel_username", "wireguard")
    clean_fname = make_clean_wg_filename(uname, port=port)
    photo = make_qr_code_file(conf_text, filename=f"qr_{clean_fname[:-5]}.png")
    proto_title = "AmneziaWG" if is_awg else "WireGuard"

    caption = (
        f"📷 <b>بارکد اختصاصی {proto_title} — پورت {to_fa(port)}</b>\n\n"
        f"👤 کاربر: <code>{uname}</code> | 🔌 پورت: <code>{port}</code>\n"
        "💡 در اپلیکیشن دکمه + را زده و گزینه <b>Scan from QR code</b> را انتخاب فرمایید."
    )
    await callback.message.answer_photo(photo=photo, caption=caption, parse_mode="HTML")
    await callback.answer(f"✅ بارکد QR پورت {port} ارسال شد.")


@router.callback_query(F.data.startswith("acc:dl_wg_p_txt:"))
async def cb_dl_wg_port_txt(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    account_id = int(parts[2])
    port = int(parts[3])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    cat = account.get("category", "wireguard")
    is_awg = (cat == "amneziawg")

    if is_awg:
        configs = await panel_api.get_amneziawg_client_multiport(
            public_key=account.get("panel_password", ""),
            base_conf=account.get("server_info", ""),
        )
    else:
        configs = await panel_api.get_wireguard_client_multiport(
            public_key=account.get("panel_password", ""),
            base_conf=account.get("server_info", ""),
        )

    cfg_obj = next((c for c in configs if c.get("port") == port), None)
    conf_text = cfg_obj.get("config") if cfg_obj else sanitize_wireguard_conf(account.get("server_info", ""), port=port)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 بازگشت به پورت", callback_data=f"acc:wg_p_view:{account_id}:{port}")
    kb.button(text="🔀 لیست تمام پورت‌ها", callback_data=f"acc:wg_multiport:{account_id}")
    proto_title = "AmneziaWG" if is_awg else "وایرگارد"

    text = (
        f"📋 <b>متن کانفیگ {proto_title} — پورت {to_fa(port)}</b>\n\n"
        f"<pre>{conf_text}</pre>\n\n"
        "💡 با لمس کادر بالا، متن کانفیگ کپی خواهد شد."
    )
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("acc:dl_wg_zip:"))
async def cb_dl_wg_zip(callback: types.CallbackQuery):
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    cat = account.get("category", "wireguard")
    is_awg = (cat == "amneziawg")

    if is_awg:
        configs = await panel_api.get_amneziawg_client_multiport(
            public_key=account.get("panel_password", ""),
            base_conf=account.get("server_info", ""),
        )
        proto_title = "AmneziaWG (وایرگارد پیشرفته)"
        tag = "awg"
    else:
        configs = await panel_api.get_wireguard_client_multiport(
            public_key=account.get("panel_password", ""),
            base_conf=account.get("server_info", ""),
        )
        proto_title = "وایرگارد معمولی"
        tag = "wg"

    if not configs:
        return await callback.answer("کانفیگ‌های پورت‌ها یافت نشد.", show_alert=True)

    uname = account.get("panel_username", "wireguard")
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for c in configs:
            p = c.get("port")
            cfg_text = c.get("config", "")
            fname = make_clean_wg_filename(uname, port=p)
            zf.writestr(fname, cfg_text.encode("utf-8"))

    zip_buffer.seek(0)
    zip_filename = f"{make_clean_wg_filename(uname)[:-5]}_{tag}_all_ports.zip"
    zip_doc = BufferedInputFile(zip_buffer.getvalue(), filename=zip_filename)

    caption = (
        f"📦 <b>پکیج کامل کلیه پورت‌های {proto_title} (فایل ZIP)</b>\n\n"
        f"👤 نام اکانت: <code>{uname}</code>\n"
        f"📊 شامل: <b>{to_fa(len(configs))} فایل کانفیگ .conf مجزا</b>\n\n"
        "💡 این فایل فشرده شامل تک‌تک پورت‌های فعال سرور است. با خارج کردن آن از حالت زیپ، می‌توانید هر کدام از پورت‌ها را وارد نرم‌افزار WireGuard / AmneziaWG فرمایید."
    )
    await callback.message.answer_document(document=zip_doc, caption=caption, parse_mode="HTML")
    await callback.answer("✅ پکیج تمام پورت‌ها ارسال شد.")


# ── جزئیات اکانت گوگل اسکریپت (GAS) ──
@router.callback_query(F.data.startswith("acc:gas_info:"))
async def cb_gas_info(callback: types.CallbackQuery):
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    uname = account.get("panel_username", "gas_user")
    dep_id = account.get("server_info", "—")
    secret = account.get("panel_password", "—")
    webapp = account.get("sub_url", "—")
    goose = account.get("sub_b64_url", "—")

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="📖 آموزش اتصال GAS", callback_data="tut:view:gas")
    kb.button(text="🔙 بازگشت به مشخصات اکانت", callback_data=f"acc:view:{account_id}")
    kb.adjust(1)

    text = (
        "☁️ <b>اطلاعات اتصال به تونل گوگل اسکریپت و کلودفلر (GAS)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 نام اکانت: <code>{uname}</code>\n"
        f"🔑 رمز تونل (Secret): <code>{secret}</code>\n"
        f"🆔 شناسه استقرار (Deployment ID):\n<code>{dep_id}</code>\n\n"
        "🔗 <b>آدرس وب‌اپ گوگل (WebApp URL):</b>\n"
        f"<code>{webapp}</code>\n\n"
        "🚀 <b>لینک اتصال مستقیم در Goose VPN (Goose URI):</b>\n"
        f"<code>{goose}</code>\n\n"
        "💡 جهت مشاهده نرم‌افزارهای سازگار و آموزش راه‌اندازی، روی دکمه آموزش اتصال کلیک فرمایید."
    )
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


# ──────────────────────────────────────────────────────────────
#  پشتیبانی کامل تانل‌های DNS و SlipNet (VayDNS, DNSTT, Tor, DoH)
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("acc:slipnet_list:"))
async def cb_slipnet_list(callback: types.CallbackQuery):
    """نمایش لیست پروتکل‌های سازگار با کلاینت SlipNet و تونل‌های DNS."""
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    uname = account.get("panel_username", "user")
    pwd = account.get("panel_password", "")

    text = (
        "📱 <b>کانفیگ‌های اختصاصی کلاینت SlipNet (پروتکل‌های ضد فیلتر DNS و Tor)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 نام کاربری (Radius/SSH): <code>{uname}</code>\n"
        f"🔑 رمز عبور: <code>{pwd}</code>\n\n"
        "⚡ <b>پروتکل‌های فعال روی این اکانت:</b>\n"
        "▫️ <b>DNSTT (SlowDNS):</b> تونل پایدار DNS از طریق پورت ۵۳\n"
        "▫️ <b>Slipstream:</b> تونل مدرن مبتنی بر پروتکل QUIC DNS\n"
        "▫️ <b>VayDNS:</b> تونل فوق پرسرعت با کمترین پینگ DNS\n"
        "▫️ <b>MasterDNS:</b> سیستم تونل چندتکه‌ای Chunked DNS\n"
        "▫️ <b>NoizDNS:</b> تونل نویزدار ضد سیستم فیلترینگ هوشمند\n"
        "▫️ <b>DoH:</b> تونل دی‌ان‌اس ابری کلودفلر (DNS over HTTPS)\n"
        "▫️ <b>Tor Bridge:</b> پل اختصاصی ضد سانسور Tor obfs4\n\n"
        "👇 جهت دریافت لینک اتصال مستقیم <code>slipnet://</code>، پروتکل مورد نظر را لمس فرمایید:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=slipnet_protocols_keyboard(account_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("acc:slp_v:"))
async def cb_slipnet_single_view(callback: types.CallbackQuery):
    """دریافت لینک اتصال مستقیم slipnet:// برای یک پروتکل خاص."""
    parts = callback.data.split(":")
    account_id = int(parts[2])
    proto = parts[3]
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    uname = account.get("panel_username", "user")
    pwd = account.get("panel_password", "")

    await callback.answer("⏳ در حال استخراج کانفیگ SlipNet...")
    res = await panel_api.get_slipnet_config(proto=proto, username=uname, password=pwd)
    uri = res.get("uri", "")

    if not uri:
        return await callback.message.answer("❌ خطا در ایجاد لینک کانفیگ روی سرور.")

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="📷 دریافت بارکد QR این کانفیگ", callback_data=f"acc:slp_proto_qr:{account_id}:{proto}")
    kb.button(text="🔙 بازگشت به لیست تانل‌های SlipNet", callback_data=f"acc:slipnet_list:{account_id}")
    kb.adjust(1)

    proto_names = {
        "dnstt": "DNSTT (SlowDNS)",
        "slipstream": "Slipstream (QUIC DNS)",
        "vaydns": "VayDNS Ultra",
        "masterdnsvpn": "MasterDNS Chunked",
        "noizdns": "NoizDNS Anti-DPI",
        "doh": "DNS over HTTPS (DoH)",
        "tor": "پل ضد سانسور Tor (obfs4)",
    }
    label = proto_names.get(proto, proto.upper())

    text = (
        f"⚡ <b>لینک اتصال مستقیم {label} مخصوص کلاینت SlipNet</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"<code>{uri}</code>\n\n"
        "💡 <b>نحوه اتصال در نرم‌افزار SlipNet:</b>\n"
        "۱. متن لینک بالا را با یک لمس کپی کنید.\n"
        "۲. در نرم‌افزار <b>SlipNet</b> علامت + را زده و گزینه <b>Import from Clipboard</b> را لمس کنید.\n"
        "۳. دکمه اتصال را بزنید."
    )
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("acc:slp_proto_qr:"))
async def cb_slipnet_proto_qr(callback: types.CallbackQuery):
    """ارسال بارکد QR اختصاصی برای یک پروتکل خاص SlipNet."""
    parts = callback.data.split(":")
    account_id = int(parts[2])
    proto = parts[3]
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    await callback.answer("⏳ در حال ساخت تصویر بارکد QR...")
    uname = account.get("panel_username", "user")
    pwd = account.get("panel_password", "")

    res = await panel_api.get_slipnet_config(proto=proto, username=uname, password=pwd)
    uri = res.get("uri", "")
    if not uri:
        return await callback.message.answer("❌ خطا در استعلام لینک کانفیگ از سرور.")

    try:
        qr = qrcode.QRCode(box_size=8, border=3)
        qr.add_data(uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        bio = io.BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)
        qr_photo = BufferedInputFile(bio.getvalue(), filename=f"slipnet_qr_{proto}_{uname}.png")
        await callback.message.answer_photo(
            photo=qr_photo,
            caption=(
                f"📷 <b>بارکد QR اختصاصی {proto.upper()} در کلاینت SlipNet</b>\n\n"
                f"👤 نام کاربری: <code>{uname}</code>\n"
                "💡 جهت اتصال، در نرم‌افزار SlipNet این بارکد را اسکن فرمایید."
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        await callback.message.answer(f"❌ خطا در تولید بارکد: {e}")


@router.callback_query(F.data.startswith("acc:slp_qr:"))
async def cb_slipnet_main_qr(callback: types.CallbackQuery):
    """ارسال بارکد QR کانفیگ اصلی تانل DNS (SlipNet)."""
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    await callback.answer("⏳ در حال تولید بارکد QR تانل...")
    uname = account.get("panel_username", "user")
    pwd = account.get("panel_password", "")

    all_uris = await panel_api.get_all_dns_slipnet_uris(username=uname, password=pwd)
    primary_uri = all_uris.get("vaydns", {}).get("uri") or all_uris.get("dnstt", {}).get("uri") or ""
    if not primary_uri:
        return await callback.message.answer("❌ خطایی در اتصال به سرور جهت دریافت کانفیگ رخ داد.")

    try:
        qr = qrcode.QRCode(box_size=8, border=3)
        qr.add_data(primary_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        bio = io.BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)
        qr_photo = BufferedInputFile(bio.getvalue(), filename=f"slipnet_qr_main_{uname}.png")
        await callback.message.answer_photo(
            photo=qr_photo,
            caption=(
                f"📷 <b>بارکد QR اتصال سریع به تانل DNS (کلاینت SlipNet)</b>\n\n"
                f"👤 کاربر: <code>{uname}</code> | 🔑 رمز: <code>{pwd}</code>\n"
                "💡 جهت اتصال سریع، این بارکد را در اپلیکیشن SlipNet اسکن نمایید."
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        await callback.message.answer(f"❌ خطا در ساخت تصویر بارکد: {e}")


@router.callback_query(F.data.startswith("acc:slp_text_all:"))
async def cb_slipnet_text_all(callback: types.CallbackQuery):
    """ارسال تمامی کانفیگ‌های تانل DNS و SlipNet به صورت پیام متنی تفکیک‌شده در چت."""
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    await callback.answer("⏳ در حال استخراج و چیدمان کانفیگ‌ها...")
    uname = account.get("panel_username", "user")
    pwd = account.get("panel_password", "")

    all_uris = await panel_api.get_all_dns_slipnet_uris(username=uname, password=pwd)
    if not all_uris:
        return await callback.message.answer("❌ خطایی در دریافت کانفیگ‌ها از سرور رخ داد.")

    cfg_blocks = [
        "🌐 <b>کلیه کانفیگ‌های کلاینت SlipNet و تانل‌های ضد فیلتر DNS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 نام کاربری: <code>{uname}</code>\n"
        f"🔑 رمز عبور: <code>{pwd}</code>\n\n"
        "💡 <i>با لمس روی هر کادر، کد کانفیگ کپی خواهد شد:</i>\n"
    ]
    for p_key, p_info in all_uris.items():
        lbl = p_info.get("label", p_key.upper())
        uri = p_info.get("uri", "")
        cfg_blocks.append(f"⚡ <b>{lbl}:</b>\n<code>{uri}</code>")

    cfg_blocks.append(
        "📱 <b>آموزش اتصال سریع در برنامه SlipNet:</b>\n"
        "۱. یکی از لینک‌های <code>slipnet://</code> بالا را کپی کنید.\n"
        "۲. در برنامه <b>SlipNet</b> علامت + را لمس کرده و گزینه <b>Import from Clipboard</b> را بزنید.\n"
        "۳. دکمه اتصال (Connect) را لمس فرمایید."
    )
    full_text = "\n\n".join(cfg_blocks)
    await callback.message.answer(full_text, parse_mode="HTML")


@router.callback_query(F.data.startswith("acc:slp_dl_all:"))
async def cb_slipnet_download_all(callback: types.CallbackQuery):
    """دانلود یکپارچه تمامی کانفیگ‌های SlipNet به صورت فایل متنی .txt."""
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    uname = account.get("panel_username", "user")
    pwd = account.get("panel_password", "")

    await callback.answer("⏳ در حال تولید فایل تجمیعی کانفیگ‌های DNS...")
    all_uris = await panel_api.get_all_dns_slipnet_uris(username=uname, password=pwd)

    if not all_uris:
        return await callback.message.answer("❌ کانفیگی از سرور دریافت نشد. لطفاً چند لحظه دیگر تلاش فرمایید.")

    lines = [
        "==================================================",
        " MS VPN - Complete SlipNet & DNS Tunnel Configs",
        f" Username: {uname}",
        f" Password: {pwd}",
        f" Traffic: {account.get('traffic_gb', 0)} GB",
        f" Validity: {account.get('duration_days', 30)} Days",
        "==================================================\n",
    ]
    for p_key, p_info in all_uris.items():
        lines.append(f"## {p_info.get('label')}")
        lines.append(f"{p_info.get('uri')}\n")

    content = "\n".join(lines)
    doc = BufferedInputFile(content.encode("utf-8"), filename=f"MS_SlipNet_All_{uname}.txt")
    caption = (
        f"📁 <b>فایل جامع کلیه کانفیگ‌های تانل DNS و SlipNet</b>\n\n"
        f"👤 نام کاربری: <code>{uname}</code>\n"
        f"🔑 رمز عبور: <code>{pwd}</code>\n"
        f"تعداد پروتکل‌ها: <b>{to_fa(len(all_uris))} عدد</b> (VayDNS, DNSTT, Slipstream, MasterDNS, NoizDNS, DoH, Tor)\n\n"
        "💡 فایل بالا را دانلود کرده و کدهای slipnet:// داخل آن را در نرم‌افزار وارد نمایید."
    )
    await callback.message.answer_document(document=doc, caption=caption, parse_mode="HTML")


# ──────────────────────────────────────────────────────────────
#  تغییر شناسه اتصال (UUID / رمز عبور) جهت قطع دسترسی دیگران
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("acc:reset_id_ask:"))
async def cb_account_reset_id_ask(callback: types.CallbackQuery):
    """استعلام تأیید برای بازنشانی و تغییر شناسه اتصال یا رمز عبور."""
    account_id = int(callback.data.split(":")[2])
    text = (
        "⚠️ <b>آیا از تغییر شناسه اتصال (UUID / پسورد) اطمینان دارید؟</b>\n\n"
        "با تغییر شناسه، اتصال کلیه دستگاه‌هایی که قبلاً این اکانت یا کانفیگ را داشته‌اند "
        "<b>فوراً قطع خواهد شد</b> و شناسه اتصال جدید برای شما صادر می‌گردد."
    )
    await callback.message.edit_text(text, reply_markup=account_reset_confirm_keyboard(account_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("acc:reset_id_do:"))
async def cb_account_reset_id_execute(callback: types.CallbackQuery):
    """اجرای تغییر شناسه / رمز عبور و اعمال در پنل و دیتابیس."""
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    cat = account.get("category", "singbox")
    uname = account.get("panel_username", "")

    # ۱. هسته Sing-box / V2Ray / Reality -> تغییر UUID
    if cat in ["singbox", "v2ray", "reality"]:
        new_uuid = str(uuid.uuid4())
        res = await panel_api.reset_singbox_uuid(uname, new_uuid)
        if not res.get("success"):
            return await callback.answer(f"خطا در تغییر شناسه: {api_error_text(res)}", show_alert=True)

        live = await panel_api.get_user_details(uname)
        new_sub = live.get("sub_url", account.get("sub_url"))
        new_b64 = live.get("sub_b64_url", account.get("sub_b64_url"))
        await database.update_account_credentials(
            account_id,
            new_sub_url=new_sub,
            new_sub_b64_url=new_b64,
        )
        msg_text = (
            "✅ <b>شناسه اتصال (UUID) با موفقیت تغییر کرد!</b>\n\n"
            "دستگاه‌های قبلی قطع شدند. لطفاً لینک سابسکریپشن خود را در نرم‌افزار Update فرمایید:\n\n"
            f"🔗 <code>{new_sub}</code>"
        )

    # ۲. پروتکل‌های استاندارد سیستمی یا DNS -> تغییر رمز عبور در Radius
    elif cat in ["system_l2tp", "dnstt"]:
        new_pwd = f"Ms{secrets.token_hex(4)}"
        res = await panel_api.create_l2tp_user(
            username=uname,
            password=new_pwd,
            traffic_limit_gb=account.get("traffic_gb", 30),
            validity_days=account.get("duration_days", 30),
        )
        if not res.get("success"):
            return await callback.answer(f"خطا در تغییر رمز: {api_error_text(res)}", show_alert=True)

        await database.update_account_credentials(account_id, new_password=new_pwd)
        msg_text = (
            "✅ <b>رمز عبور اکانت با موفقیت تغییر کرد!</b>\n\n"
            f"👤 نام کاربری: <code>{uname}</code>\n"
            f"🔑 <b>رمز عبور جدید:</b> <code>{new_pwd}</code>\n\n"
            "اتصال دستگاه‌های قبلی با رمز قدیمی متوقف شد."
        )

    # ۳. وایرگارد -> بازسازی و کلید جدید
    elif cat == "wireguard":
        await panel_api.delete_wireguard_account(account.get("panel_password", ""))
        new_res = await panel_api.create_wireguard_account(
            name=uname,
            traffic_limit_gb=account.get("traffic_gb", 30),
            validity_days=account.get("duration_days", 30),
        )
        if not new_res.get("success"):
            return await callback.answer(f"خطا در ایجاد کلید جدید وایرگارد: {api_error_text(new_res)}", show_alert=True)

        new_conf = new_res.get("config", "")
        new_pubkey = new_res.get("public_key", "")
        await database.update_account_credentials(
            account_id,
            new_password=new_pubkey,
            new_server_info=new_conf,
        )
        msg_text = (
            "✅ <b>کلیدها و کانفیگ وایرگارد با موفقیت بازسازی شد!</b>\n\n"
            "فایل و بارکد قبلی باطل شد. فایل کانفیگ و بارکد جدید در بخش اکانت‌های من در دسترس است."
        )

    else:
        msg_text = "✅ شناسه اتصال با موفقیت بروزرسانی شد."

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 بازگشت به مشخصات اکانت", callback_data=f"acc:view:{account_id}")
    await callback.message.edit_text(msg_text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer("شناسه با موفقیت تغییر یافت.")


# ──────────────────────────────────────────────────────────────
#  تمدید اکانت بدون تغییر در مشخصات اتصال (Renew Account)
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("acc:renew_ask:"))
async def cb_account_renew_ask(callback: types.CallbackQuery):
    """شروع فرآیند تمدید اکانت: نمایش پلن‌های قابل تمدید."""
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    if account.get("is_trial"):
        return await callback.answer("⚠️ اکانت‌های تستی قابلیت تمدید ندارند. لطفاً برای خرید اشتراک دائم از بخش خرید اقدام فرمایید.", show_alert=True)

    cat = account.get("category", "singbox")
    plans = await database.get_plans_by_category(cat)
    if not plans:
        return await callback.answer("هیچ پلن فعالی در این دسته‌بندی یافت نشد.", show_alert=True)

    user = await database.get_user(telegram_id)
    balance = user.get("wallet_balance", 0) if user else 0

    text = (
        "🔄 <b>تمدید اشتراک اکانت</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 نام کاربری اکانت: <code>{account.get('panel_username')}</code>\n"
        f"🏷 پلن فعلی: <b>{account.get('plan_name')}</b>\n"
        f"💰 موجودی کیف پول شما: <b>{to_toman(balance)}</b>\n\n"
        "✨ <b>مزایای تمدید اکانت:</b>\n"
        "▫️ تمام لینک‌های سابسکریپشن، UUID و کانفیگ‌ها <b>بدون تغییر</b> فعال می‌مانند.\n"
        "▫️ نیازی به کپی یا تغییر تنظیمات در نرم‌افزارهای اتصال نیست.\n"
        "▫️ ترافیک مصرفی صفر شده و سقف پلن انتخابی مجدداً شارژ می‌شود.\n"
        "▫️ روزهای اعتبار پلن به مهلت اکانت شما افزوده خواهد شد.\n\n"
        "👇 لطفاً پلن مد نظر جهت تمدید را انتخاب فرمایید:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=account_renew_plans_keyboard(account_id, plans, current_plan_name=account.get("plan_name", "")),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("acc:renew_sel:"))
async def cb_account_renew_select(callback: types.CallbackQuery):
    """انتخاب پلن تمدید و نمایش پیش‌فاکتور مالی."""
    parts = callback.data.split(":")
    account_id = int(parts[2])
    plan_id = int(parts[3])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    plan = await database.get_plan_by_id(plan_id)
    user = await database.get_user(telegram_id)

    if not account or not plan:
        return await callback.answer("اطلاعات اکانت یا پلن نامعتبر است.", show_alert=True)

    balance = user.get("wallet_balance", 0) if user else 0
    price = plan.get("price", 0)

    if balance < price:
        shortage = price - balance
        kb = InlineKeyboardBuilder()
        kb.button(text="💰 افزایش موجودی کیف پول", callback_data="wallet:topup")
        kb.button(text="🔙 بازگشت به لیست پلن‌ها", callback_data=f"acc:renew_ask:{account_id}")
        kb.adjust(1)
        return await callback.message.edit_text(
            f"❌ <b>موجودی کیف پول شما کافی نیست!</b>\n\n"
            f"مبلغ مورد نیاز برای تمدید پلن «{plan.get('name')}»: <b>{to_toman(price)}</b>\n"
            f"موجودی فعلی شما: <b>{to_toman(balance)}</b>\n"
            f"کسری موجودی: <b>{to_toman(shortage)}</b>\n\n"
            "لطفاً ابتدا کیف پول خود را شارژ کرده و سپس مجدداً اقدام فرمایید.",
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )

    rem_bal = balance - price
    confirm_text = (
        "📋 <b>پیش‌فاکتور تمدید اشتراک:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 نام اکانت: <code>{account.get('panel_username')}</code>\n"
        f"📦 پلن انتخابی تمدید: <b>{plan.get('name')}</b>\n"
        f"📊 حجم ترافیک شارژ: <b>{plan.get('traffic_gb')} گیگابایت</b>\n"
        f"⏳ مدت اعتبار اضافه: <b>{plan.get('duration_days')} روز</b>\n\n"
        f"💳 <b>مبلغ قابل پرداخت:</b> <b>{to_toman(price)}</b>\n"
        f"💰 موجودی فعلی کیف پول شما: <b>{to_toman(balance)}</b>\n"
        f"💵 موجودی پس از تمدید: <b>{to_toman(rem_bal)}</b>\n\n"
        "💡 <i>توجه: پس از تأیید، کلیه مشخصات اتصال (لینک ساب، UUID و کلیدها) کاملاً ثابت مانده و سرویس شما بلافاصله تمدید می‌شود.</i>"
    )
    await callback.message.edit_text(
        confirm_text,
        reply_markup=account_renew_confirm_keyboard(account_id, plan_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("acc:renew_exec:"))
async def cb_account_renew_execute(callback: types.CallbackQuery):
    """اجرای عملیات تمدید اکانت در پنل و کسر از کیف پول."""
    parts = callback.data.split(":")
    account_id = int(parts[2])
    plan_id = int(parts[3])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    plan = await database.get_plan_by_id(plan_id)
    user = await database.get_user(telegram_id)

    if not account or not plan:
        return await callback.answer("اکانت یا پلن تمدید یافت نشد.", show_alert=True)

    balance = user.get("wallet_balance", 0) if user else 0
    price = plan.get("price", 0)
    if balance < price:
        return await callback.answer(f"موجودی ناکافی است. مبلغ مورد نیاز: {to_toman(price)}", show_alert=True)

    await callback.answer("⏳ در حال تمدید اشتراک در سرور...")

    cat = account.get("category", "singbox")
    uname = account.get("panel_username")
    plan_days = int(plan.get("duration_days", 30))
    plan_traffic = float(plan.get("traffic_gb", 30.0))

    # ۱. اعمال تمدید روی سرور پنل
    if cat in ["singbox", "v2ray", "reality"]:
        live_data = await panel_api.get_user_details(uname)
        new_expire = None
        reset_first = False
        if live_data and live_data.get("success"):
            u_info = live_data.get("user", {})
            if u_info.get("is_waiting_first_use") or not u_info.get("first_connected_at"):
                new_expire = f"پس از اولین اتصال ({plan_days} روزه)"
                reset_first = True
            else:
                cur_exp_str = str(u_info.get("expire_date") or "").strip()
                cur_exp_dt = None
                if cur_exp_str:
                    try:
                        cur_exp_dt = datetime.strptime(cur_exp_str.split()[0], "%Y-%m-%d").date()
                    except Exception:
                        cur_exp_dt = None
                today = datetime.now().date()
                if cur_exp_dt and cur_exp_dt >= today:
                    new_exp_dt = cur_exp_dt + timedelta(days=plan_days)
                else:
                    new_exp_dt = today + timedelta(days=plan_days)
                new_expire = new_exp_dt.strftime("%Y-%m-%d")

        edit_res = await panel_api.edit_user(
            username=uname,
            traffic_limit_gb=plan_traffic,
            validity_days=plan_days,
            expire_date=new_expire if new_expire else None,
            reset_traffic=True,
            reset_first_connection=reset_first,
            enabled=True,
        )
        if not edit_res.get("success"):
            return await callback.message.answer(f"❌ خطا در تمدید اکانت در سرور:\n{api_error_text(edit_res)}")

    elif cat in ["wireguard", "amneziawg"]:
        pk = account.get("panel_password") or uname
        if cat == "wireguard":
            res_rn = await panel_api.renew_wireguard_account(public_key=pk, days=plan_days, reset_traffic=True)
            await panel_api.edit_wireguard_account(public_key=pk, name=uname, limit_gb=plan_traffic, expire_days=plan_days, active=True)
        else:
            res_rn = await panel_api.renew_amneziawg_account(public_key=pk, days=plan_days, reset_traffic=True)
            await panel_api.edit_amneziawg_account(public_key=pk, name=uname, limit_gb=plan_traffic, expire_days=plan_days, active=True)
        if not res_rn.get("success"):
            return await callback.message.answer(f"❌ خطا در تمدید اکانت وایرگارد در سرور:\n{api_error_text(res_rn)}")

    elif cat in ["system_l2tp", "dnstt"]:
        res_l2 = await panel_api.create_l2tp_user(
            username=uname,
            password=account.get("panel_password", ""),
            traffic_limit_gb=plan_traffic,
            validity_days=plan_days,
        )
        if not res_l2.get("success"):
            return await callback.message.answer(f"❌ خطا در تمدید اکانت در سرور:\n{api_error_text(res_l2)}")

    # ۲. کسر هزینه از کیف پول و ثبت تراکنش
    await database.update_wallet_balance(telegram_id, -price)
    await database.create_transaction(telegram_id, price, "renew_pay", "wallet", status="approved")

    # ۳. بروزرسانی در دیتابیس محلی ربات
    await database.update_account_plan(
        account_id=account_id,
        plan_name=plan.get("name"),
        traffic_gb=plan_traffic,
        duration_days=plan_days,
        price=price,
    )

    new_user = await database.get_user(telegram_id)
    new_bal = new_user.get("wallet_balance", 0) if new_user else 0

    succ_text = (
        "🎉 <b>اشتراک شما با موفقیت تمدید شد!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 نام اکانت: <code>{uname}</code>\n"
        f"📦 پلن تمدید شده: <b>{plan.get('name')}</b>\n"
        f"📊 حجم ترافیک مجاز: <b>{plan_traffic:g} گیگابایت</b> (مصرف ریست شد)\n"
        f"⏳ مدت اعتبار اضافه: <b>{plan_days} روز</b>\n"
        f"💰 مبلغ کسر شده: <b>{to_toman(price)}</b>\n"
        f"💼 موجودی فعلی کیف پول: <b>{to_toman(new_bal)}</b>\n\n"
        "✅ <b>لینک هوشمند سابسکریپشن، UUID و تنظیمات اتصال شما بدون کوچک‌ترین تغییری باقی ماند. نیازی به هیچ تغییری در نرم‌افزار خود ندارید.</b>"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="📦 مشاهده مشخصات اکانت", callback_data=f"acc:view:{account_id}")
    kb.button(text="🔙 بازگشت به لیست اکانت‌ها", callback_data="acc:list")
    kb.adjust(1)
    await callback.message.edit_text(succ_text, reply_markup=kb.as_markup(), parse_mode="HTML")


# ──────────────────────────────────────────────────────────────
#  ارتقای پلن اکانت با کسر مصرف قبلی (Upgrade Account Plan)
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("acc:upgrade_ask:"))
async def cb_account_upgrade_ask(callback: types.CallbackQuery):
    """شروع فرآیند ارتقای اکانت: محاسبه ارزش باقیمانده و نمایش پلن‌های مقصد."""
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    if account.get("is_trial"):
        return await callback.answer("⚠️ اکانت‌های تستی امکان ارتقا ندارند. لطفاً برای خرید اشتراک دائم اقدام فرمایید.", show_alert=True)

    cat = account.get("category", "singbox")
    plans = await database.get_plans_by_category(cat)
    if not plans:
        return await callback.answer("هیچ پلن فعالی در این دسته‌بندی یافت نشد.", show_alert=True)

    uname = account.get("panel_username")
    live_data = None
    if cat in ("singbox", "v2ray", "reality"):
        live_data = await panel_api.get_user_details(uname)
    elif cat == "wireguard":
        live_data = await panel_api.get_wireguard_peer_details(account.get("panel_password") or uname)
    elif cat == "amneziawg":
        live_data = await panel_api.get_amneziawg_peer_details(account.get("panel_password") or uname)

    # برآورد قیمت پایه فعلی
    cur_price = account.get("price") or 0
    if cur_price <= 0:
        for p in plans:
            if p.get("name") == account.get("plan_name"):
                cur_price = p.get("price", 0)
                break
        if cur_price <= 0:
            cur_price = plans[0].get("price", 60000)

    refund_amount, breakdown = calculate_account_refund(
        account,
        live_data if (live_data and live_data.get("success")) else None,
        plan_price=cur_price,
    )
    remaining_value = refund_amount
    used_cost = breakdown.get("price", cur_price) - remaining_value

    user = await database.get_user(telegram_id)
    balance = user.get("wallet_balance", 0) if user else 0

    text = (
        "🚀 <b>ارتقای پلن اشتراک (بدون تغییر اطلاعات اکانت)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 نام اکانت: <code>{uname}</code>\n"
        f"🏷 پلن فعلی: <b>{account.get('plan_name')}</b>\n"
        f"💰 ارزش پایه پلن فعلی: <b>{to_toman(breakdown.get('price', cur_price))}</b>\n\n"
        "📊 <b>گزارش مصرف و محاسبه ارزش باقیمانده:</b>\n"
        f"▫️ حجم مصرف شده: <b>{to_fa(breakdown.get('used_gb', 0.0))} GB</b> از {to_fa(breakdown.get('total_gb', 0.0))} GB\n"
        f"▫️ روزهای مصرف شده: <b>{to_fa(breakdown.get('used_days', 0.0))} روز</b> از {to_fa(breakdown.get('total_days', 30))} روز\n"
        f"▫️ هزینه خدمات مصرف شده: <b>{to_toman(used_cost)}</b>\n"
        f"💎 <b>اعتبار باقیمانده شما (تخفیف ارتقا):</b> <b>{to_toman(remaining_value)}</b>\n\n"
        f"💰 موجودی فعلی کیف پول شما: <b>{to_toman(balance)}</b>\n\n"
        "💡 <b>نحوه عملکرد ارتقا:</b>\n"
        "ارزش باقیمانده سرویس فعلی شما از قیمت پلن انتخابی کسر می‌شود و فقط مابه‌التفاوت آن را پرداخت می‌نمایید.\n"
        "<b>کلیه لینک‌های اتصال و مشخصات اکانت شما دست‌نخورده باقی خواهد ماند.</b>\n\n"
        "👇 لطفاً پلن مقصد مورد نظر خود جهت ارتقا را انتخاب نمایید:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=account_upgrade_plans_keyboard(
            account_id,
            remaining_value,
            plans,
            current_plan_name=account.get("plan_name", ""),
        ),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("acc:upg_sel:"))
async def cb_account_upgrade_select(callback: types.CallbackQuery):
    """انتخاب پلن ارتقا و نمایش پیش‌فاکتور با کسر اعتبار باقیمانده."""
    parts = callback.data.split(":")
    account_id = int(parts[2])
    target_plan_id = int(parts[3])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    target_plan = await database.get_plan_by_id(target_plan_id)
    user = await database.get_user(telegram_id)

    if not account or not target_plan:
        return await callback.answer("اطلاعات اکانت یا پلن نامعتبر است.", show_alert=True)

    cat = account.get("category", "singbox")
    uname = account.get("panel_username")
    live_data = None
    if cat in ("singbox", "v2ray", "reality"):
        live_data = await panel_api.get_user_details(uname)
    elif cat == "wireguard":
        live_data = await panel_api.get_wireguard_peer_details(account.get("panel_password") or uname)
    elif cat == "amneziawg":
        live_data = await panel_api.get_amneziawg_peer_details(account.get("panel_password") or uname)

    cur_price = account.get("price") or 0
    if cur_price <= 0:
        all_plans = await database.get_plans_by_category(cat)
        for p in all_plans:
            if p.get("name") == account.get("plan_name"):
                cur_price = p.get("price", 0)
                break
        if cur_price <= 0:
            cur_price = target_plan.get("price", 60000)

    refund_amount, breakdown = calculate_account_refund(
        account,
        live_data if (live_data and live_data.get("success")) else None,
        plan_price=cur_price,
    )
    remaining_value = refund_amount

    target_price = target_plan.get("price", 0)
    upgrade_cost = max(0, target_price - remaining_value)
    balance = user.get("wallet_balance", 0) if user else 0

    if upgrade_cost > 0 and balance < upgrade_cost:
        shortage = upgrade_cost - balance
        kb = InlineKeyboardBuilder()
        kb.button(text="💰 افزایش موجودی کیف پول", callback_data="wallet:topup")
        kb.button(text="🔙 بازگشت به لیست پلن‌ها", callback_data=f"acc:upgrade_ask:{account_id}")
        kb.adjust(1)
        return await callback.message.edit_text(
            f"❌ <b>موجودی کیف پول شما کافی نیست!</b>\n\n"
            f"مبلغ قابل پرداخت جهت ارتقا: <b>{to_toman(upgrade_cost)}</b>\n"
            f"موجودی فعلی شما: <b>{to_toman(balance)}</b>\n"
            f"کسری موجودی: <b>{to_toman(shortage)}</b>\n\n"
            "لطفاً ابتدا کیف پول خود را شارژ فرمایید.",
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )

    rem_bal = balance - upgrade_cost
    cost_label = to_toman(upgrade_cost) if upgrade_cost > 0 else "رایگان (بدون هزینه اضافی)"

    confirm_text = (
        "📋 <b>پیش‌فاکتور ارتقای اشتراک:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 نام اکانت: <code>{uname}</code>\n"
        f"🏷 پلن فعلی: <b>{account.get('plan_name')}</b>\n"
        f"🚀 <b>پلن ارتقا یافته:</b> <b>{target_plan.get('name')}</b>\n"
        f"📊 حجم ترافیک جدید: <b>{target_plan.get('traffic_gb')} گیگابایت</b>\n"
        f"⏳ مدت اعتبار جدید: <b>{target_plan.get('duration_days')} روز</b>\n\n"
        f"💵 قیمت پلن جدید: <b>{to_toman(target_price)}</b>\n"
        f"💎 کسر اعتبار باقیمانده فعلی: <b>- {to_toman(remaining_value)}</b>\n"
        f"💳 <b>مبلغ خالص پرداختی شما:</b> <b>{cost_label}</b>\n\n"
        f"💰 موجودی فعلی کیف پول: <b>{to_toman(balance)}</b>\n"
        f"💵 موجودی پس از ارتقا: <b>{to_toman(rem_bal)}</b>\n\n"
        "⚠️ <i>توجه: لینک اتصال، شناسه UUID و تمامی تنظیمات شما کاملاً دست نخورده باقی مانده و اکانت با پلن جدید فعال خواهد شد.</i>"
    )
    await callback.message.edit_text(
        confirm_text,
        reply_markup=account_upgrade_confirm_keyboard(account_id, target_plan_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("acc:upg_exec:"))
async def cb_account_upgrade_execute(callback: types.CallbackQuery):
    """اجرای عملیات ارتقای پلن اکانت در پنل و دیتابیس."""
    parts = callback.data.split(":")
    account_id = int(parts[2])
    target_plan_id = int(parts[3])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    target_plan = await database.get_plan_by_id(target_plan_id)
    user = await database.get_user(telegram_id)

    if not account or not target_plan:
        return await callback.answer("اکانت یا پلن مقصد یافت نشد.", show_alert=True)

    cat = account.get("category", "singbox")
    uname = account.get("panel_username")
    live_data = None
    if cat in ("singbox", "v2ray", "reality"):
        live_data = await panel_api.get_user_details(uname)
    elif cat == "wireguard":
        live_data = await panel_api.get_wireguard_peer_details(account.get("panel_password") or uname)
    elif cat == "amneziawg":
        live_data = await panel_api.get_amneziawg_peer_details(account.get("panel_password") or uname)

    cur_price = account.get("price") or 0
    if cur_price <= 0:
        all_plans = await database.get_plans_by_category(cat)
        for p in all_plans:
            if p.get("name") == account.get("plan_name"):
                cur_price = p.get("price", 0)
                break
        if cur_price <= 0:
            cur_price = target_plan.get("price", 60000)

    refund_amount, _ = calculate_account_refund(
        account,
        live_data if (live_data and live_data.get("success")) else None,
        plan_price=cur_price,
    )
    remaining_value = refund_amount

    target_price = target_plan.get("price", 0)
    upgrade_cost = max(0, target_price - remaining_value)
    balance = user.get("wallet_balance", 0) if user else 0

    if upgrade_cost > 0 and balance < upgrade_cost:
        return await callback.answer(f"موجودی ناکافی است. مبلغ مورد نیاز: {to_toman(upgrade_cost)}", show_alert=True)

    await callback.answer("⏳ در حال ارتقای پلن در سرور...")

    plan_days = int(target_plan.get("duration_days", 30))
    plan_traffic = float(target_plan.get("traffic_gb", 30.0))

    # ۱. اعمال تغییرات روی سرور بدون تغییر نام کاربری یا UUID
    if cat in ["singbox", "v2ray", "reality"]:
        new_expire = None
        reset_first = False
        if live_data and live_data.get("success"):
            u_info = live_data.get("user", {})
            if u_info.get("is_waiting_first_use") or not u_info.get("first_connected_at"):
                new_expire = f"پس از اولین اتصال ({plan_days} روزه)"
                reset_first = True
            else:
                today = datetime.now().date()
                new_exp_dt = today + timedelta(days=plan_days)
                new_expire = new_exp_dt.strftime("%Y-%m-%d")

        edit_res = await panel_api.edit_user(
            username=uname,
            traffic_limit_gb=plan_traffic,
            validity_days=plan_days,
            expire_date=new_expire if new_expire else None,
            reset_traffic=True,
            reset_first_connection=reset_first,
            enabled=True,
        )
        if not edit_res.get("success"):
            return await callback.message.answer(f"❌ خطا در ارتقای اکانت در سرور:\n{api_error_text(edit_res)}")

    elif cat in ["wireguard", "amneziawg"]:
        pk = account.get("panel_password") or uname
        if cat == "wireguard":
            res_rn = await panel_api.renew_wireguard_account(public_key=pk, days=plan_days, reset_traffic=True)
            await panel_api.edit_wireguard_account(public_key=pk, name=uname, limit_gb=plan_traffic, expire_days=plan_days, active=True)
        else:
            res_rn = await panel_api.renew_amneziawg_account(public_key=pk, days=plan_days, reset_traffic=True)
            await panel_api.edit_amneziawg_account(public_key=pk, name=uname, limit_gb=plan_traffic, expire_days=plan_days, active=True)
        if not res_rn.get("success"):
            return await callback.message.answer(f"❌ خطا در ارتقای اکانت وایرگارد در سرور:\n{api_error_text(res_rn)}")

    elif cat in ["system_l2tp", "dnstt"]:
        res_l2 = await panel_api.create_l2tp_user(
            username=uname,
            password=account.get("panel_password", ""),
            traffic_limit_gb=plan_traffic,
            validity_days=plan_days,
        )
        if not res_l2.get("success"):
            return await callback.message.answer(f"❌ خطا در ارتقای اکانت در سرور:\n{api_error_text(res_l2)}")

    # ۲. کسر هزینه در صورت وجود مابه‌التفاوت و ثبت تراکنش
    if upgrade_cost > 0:
        await database.update_wallet_balance(telegram_id, -upgrade_cost)
        await database.create_transaction(telegram_id, upgrade_cost, "upgrade_pay", "wallet", status="approved")

    # ۳. بروزرسانی اطلاعات پلن در دیتابیس ربات
    await database.update_account_plan(
        account_id=account_id,
        plan_name=target_plan.get("name"),
        traffic_gb=plan_traffic,
        duration_days=plan_days,
        price=target_price,
    )

    new_user = await database.get_user(telegram_id)
    new_bal = new_user.get("wallet_balance", 0) if new_user else 0

    succ_text = (
        "🎉 <b>اکانت شما با موفقیت به پلن جدید ارتقا یافت!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 نام اکانت: <code>{uname}</code>\n"
        f"🚀 پلن جدید: <b>{target_plan.get('name')}</b>\n"
        f"📊 سقف ترافیک جدید: <b>{plan_traffic:g} گیگابایت</b>\n"
        f"⏳ مهلت اعتبار جدید: <b>{plan_days} روز</b>\n"
        f"💳 مبلغ پرداختی (با کسر باقیمانده قبلی): <b>{to_toman(upgrade_cost) if upgrade_cost > 0 else 'رایگان'}</b>\n"
        f"💼 موجودی فعلی کیف پول: <b>{to_toman(new_bal)}</b>\n\n"
        "✅ <b>کلیه اطلاعات اکانت (لینک سابسکریپشن، شناسه UUID و کانفیگ‌ها) کاملاً حفظ شده و نیازی به تغییر تنظیمات نرم‌افزار نیست.</b>"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="📦 مشاهده مشخصات اکانت", callback_data=f"acc:view:{account_id}")
    kb.button(text="🔙 بازگشت به لیست اکانت‌ها", callback_data="acc:list")
    kb.adjust(1)
    await callback.message.edit_text(succ_text, reply_markup=kb.as_markup(), parse_mode="HTML")


# ──────────────────────────────────────────────────────────────
#  تبدیل اکانت به پروتکل دیگر با محاسبه مابه‌التفاوت مالی
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("acc:convert_ask:"))
async def cb_account_convert_ask(callback: types.CallbackQuery):
    """شروع فرآیند تبدیل اکانت: نمایش دسته‌بندی‌های مقصد."""
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    current_cat = account.get("category", "singbox")
    cats = await database.get_active_categories()

    text = (
        "🔁 <b>تبدیل اکانت به پروتکل دیگر (تعویض سرویس)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"اکانت فعلی شما: <b>{account.get('plan_name')}</b>\n"
        f"دسته فعلی: <code>{current_cat}</code>\n\n"
        "💡 <b>نحوه عملکرد تبدیل:</b>\n"
        "۱. اکانت فعلی شما با اکانت مقصد تعویض می‌شود.\n"
        "۲. در صورتی که پلن مقصد گران‌تر باشد، مابه‌التفاوت از کیف پول کسر می‌شود.\n"
        "۳. در صورتی که پلن مقصد ارزان‌تر باشد، مابه‌التفاوت به کیف پول شما برگشت داده می‌شود.\n\n"
        "👇 لطفاً دسته‌بندی جدیدی که مایلید به آن تغییر دهید را انتخاب فرمایید:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=account_convert_categories_keyboard(account_id, current_cat, cats),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("acc:conv_cat:"))
async def cb_account_convert_select_category(callback: types.CallbackQuery):
    """نمایش پلن‌های دسته‌بندی مقصد با محاسبه مابه‌التفاوت."""
    parts = callback.data.split(":")
    account_id = int(parts[2])
    target_cat = parts[3]
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    # برآورد قیمت پلن فعلی
    plans = await database.get_plans_by_category(target_cat)
    if not plans:
        return await callback.answer("هیچ پلن فعالی در این دسته یافت نشد.", show_alert=True)

    # قیمت تقریبی پلن فعلی بر اساس نام یا میانگین
    cur_price = 65000
    all_cur_plans = await database.get_plans_by_category(account.get("category", "singbox"))
    for cp in all_cur_plans:
        if cp.get("name") == account.get("plan_name"):
            cur_price = cp.get("price", 65000)
            break

    text = (
        f"📦 <b>انتخاب پلن جدید در دسته {target_cat}</b>\n\n"
        f"قیمت پایه اکانت فعلی شما: <b>{to_toman(cur_price)}</b>\n\n"
        "👇 پلن مقصد مورد نظر خود را انتخاب فرمایید (مابه‌التفاوت روی هر گزینه درج شده است):"
    )
    await callback.message.edit_text(
        text,
        reply_markup=account_convert_plans_keyboard(account_id, cur_price, plans),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("acc:conv_plan:"))
async def cb_account_convert_plan_confirm(callback: types.CallbackQuery):
    """تأیید نهایی پیش از کسر/افزایش موجودی و حذف اکانت قدیمی."""
    parts = callback.data.split(":")
    account_id = int(parts[2])
    target_plan_id = int(parts[3])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    target_plan = await database.get_plan_by_id(target_plan_id)
    user = await database.get_user(telegram_id)

    if not account or not target_plan:
        return await callback.answer("اطلاعات نامعتبر است.", show_alert=True)

    cur_price = 65000
    all_cur_plans = await database.get_plans_by_category(account.get("category", "singbox"))
    for cp in all_cur_plans:
        if cp.get("name") == account.get("plan_name"):
            cur_price = cp.get("price", 65000)
            break

    target_price = target_plan.get("price", 0)
    diff = target_price - cur_price
    balance = user.get("wallet_balance", 0) if user else 0

    if diff > 0:
        fin_text = f"🔴 مبلغ قابل پرداخت (مابه‌التفاوت): <b>{to_toman(diff)}</b> (از کیف پول کسر می‌شود)"
        if balance < diff:
            return await callback.message.edit_text(
                f"❌ <b>موجودی کیف پول شما کافی نیست!</b>\n\n"
                f"مبلغ مابه‌التفاوت مورد نیاز: <b>{to_toman(diff)}</b>\n"
                f"موجودی فعلی شما: <b>{to_toman(balance)}</b>\n\n"
                "لطفاً ابتدا از بخش «💰 کیف پول» حساب خود را شارژ نمایید.",
                reply_markup=account_details_keyboard(account_id, category=account.get("category")),
                parse_mode="HTML",
            )
    elif diff < 0:
        fin_text = f"🟢 مبلغ عودت به کیف پول شما: <b>{to_toman(abs(diff))}</b>"
    else:
        fin_text = "⚪ بدون هزینه اضافی (قیمت برابر)"

    confirm_text = (
        "🔄 <b>پیش‌نمایش تبدیل اشتراک:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"اکانت فعلی: <b>{account.get('plan_name')}</b> ({account.get('category')})\n"
        f"اکانت جدید: <b>{target_plan.get('name')}</b> ({target_plan.get('category_key')})\n\n"
        f"{fin_text}\n"
        f"موجودی کیف پول شما: <b>{to_toman(balance)}</b>\n\n"
        "⚠️ <i>با زدن دکمه تأیید، اکانت فعلی در سرور حذف شده و اکانت جدید فوراً ساخته می‌شود.</i>"
    )
    await callback.message.edit_text(
        confirm_text,
        reply_markup=account_convert_confirm_keyboard(account_id, target_plan_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("acc:conv_exec:"))
async def cb_account_convert_execute(callback: types.CallbackQuery):
    """اجرای عملیات تبدیل اکانت، بررسی موجودی، صدور روی سرور و تحویل اطلاعات."""
    parts = callback.data.split(":")
    account_id = int(parts[2])
    target_plan_id = int(parts[3])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    target_plan = await database.get_plan_by_id(target_plan_id)
    user = await database.get_user(telegram_id)

    if not account or not target_plan:
        return await callback.answer("اکانت یا پلن مقصد یافت نشد.", show_alert=True)

    target_cat = target_plan.get("category_key", "singbox")

    # محاسبه مابه‌التفاوت قیمت
    cur_price = 65000
    all_cur_plans = await database.get_plans_by_category(account.get("category", "singbox"))
    for cp in all_cur_plans:
        if cp.get("name") == account.get("plan_name"):
            cur_price = cp.get("price", 65000)
            break

    target_price = target_plan.get("price", 0)
    diff = target_price - cur_price

    # بررسی موجودی قبل از هر اقدامی
    balance = user.get("wallet_balance", 0) if user else 0
    if diff > 0 and balance < diff:
        return await callback.answer(
            f"❌ موجودی کیف پول کافی نیست.\nمبلغ مورد نیاز: {to_toman(diff)} | موجودی فعلی: {to_toman(balance)}",
            show_alert=True,
        )

    await callback.answer("⏳ در حال صدور سرویس جدید روی سرور...")

    rand_suffix = secrets.token_hex(2)

    # ۱. صدور سرویس در سرور پنل (پیش از هرگونه حذف یا کسر موجودی)
    if target_cat == "wireguard":
        new_u = f"ms_wg_{telegram_id}_{rand_suffix}"
        res = await panel_api.create_wireguard_account(
            name=new_u,
            traffic_limit_gb=target_plan.get("traffic_gb", 30),
            validity_days=target_plan.get("duration_days", 30),
        )
        if not res.get("success"):
            return await callback.message.answer(f"❌ خطا در صدور اکانت وایرگارد در سرور:\n{api_error_text(res)}")

        conf = res.get("config", "")
        pubkey = res.get("public_key", "")
        sub_tok = res.get("sub_token", "")
        saved_pass = pubkey
        saved_srv = conf
        sub_url = ""
        sub_b64 = ""
        uuid_str = ""

    elif target_cat == "dnstt":
        new_u = f"ms_dns_{telegram_id}_{rand_suffix}"
        new_p = f"Dns{secrets.token_hex(3)}"
        res = await panel_api.create_l2tp_user(
            username=new_u,
            password=new_p,
            traffic_limit_gb=target_plan.get("traffic_gb", 30),
            validity_days=target_plan.get("duration_days", 30),
        )
        if not res.get("success"):
            return await callback.message.answer(f"❌ خطا در صدور اکانت تانل DNS در سرور:\n{api_error_text(res)}")

        dnstt_dom = await database.get_setting("dnstt_domain", settings.DNSTT_DOMAIN)
        saved_pass = new_p
        saved_srv = dnstt_dom
        sub_tok = ""
        sub_url = ""
        sub_b64 = ""
        uuid_str = ""

    elif target_cat == "system_l2tp":
        new_u = f"ms_sys_{telegram_id}_{rand_suffix}"
        new_p = f"Ms{secrets.token_hex(3)}"
        res = await panel_api.create_l2tp_user(
            username=new_u,
            password=new_p,
            traffic_limit_gb=target_plan.get("traffic_gb", 30),
            validity_days=target_plan.get("duration_days", 30),
        )
        if not res.get("success"):
            return await callback.message.answer(f"❌ خطا در صدور اکانت سیستمی در سرور:\n{api_error_text(res)}")

        srv_ip = await database.get_setting("server_ip", settings.SERVER_IP)
        saved_pass = new_p
        saved_srv = srv_ip
        sub_tok = ""
        sub_url = ""
        sub_b64 = ""
        uuid_str = ""

    elif target_cat == "gas":
        gas_cfg = await panel_api.get_gas_client_configs(use_cloudflare=True)
        mhrv = gas_cfg.get("mhrv_profile", {})
        goose_uri = gas_cfg.get("goose_uri", "")
        webapp_url = mhrv.get("apps_script_url", "")
        secret = mhrv.get("auth_key", "gas_secret")
        scripts = mhrv.get("script_ids", [])
        dep_id = scripts[0] if scripts else "AKfycb_CloudDeployment"
        new_u = f"gas_{telegram_id}_{rand_suffix}"
        saved_pass = secret
        saved_srv = dep_id
        sub_tok = ""
        sub_url = webapp_url
        sub_b64 = goose_uri
        uuid_str = ""

    else:
        # دسته هوشمند Sing-box و V2Ray
        new_u = f"ms_sb_{telegram_id}_{rand_suffix}"
        inbounds = None
        if target_cat == "v2ray":
            inbounds = V2RAY_INBOUNDS
        elif target_cat == "reality":
            inbounds = REALITY_INBOUNDS

        res = await panel_api.create_user(
            username=new_u,
            traffic_limit_gb=target_plan.get("traffic_gb", 30.0),
            validity_days=target_plan.get("duration_days", 30),
            expiry_type="on_first_use",
            category="MS_VPN_Convert",
            inbounds=inbounds,
            note=f"Converted TG: {telegram_id} - {target_plan.get('name')}",
        )
        if not res.get("success"):
            return await callback.message.answer(f"❌ خطا در صدور اکانت Sing-box / V2Ray در سرور:\n{api_error_text(res)}")

        created_u = res.get("user", {})
        sub_tok = created_u.get("sub_token", "")
        sub_url = created_u.get("sub_url", f"{settings.PANEL_SUB_URL}/{sub_tok}")
        sub_b64 = created_u.get("sub_b64_url", f"{sub_url}/b64")
        uuid_str = created_u.get("uuid", "")
        saved_pass = None
        saved_srv = ""

    # ۲. اعمال تراکنش مابه‌التفاوت پس از اطمینان از ساخت در سرور
    if diff > 0:
        await database.update_wallet_balance(telegram_id, -diff)
        await database.create_transaction(telegram_id, diff, "convert_pay", "wallet", status="approved")
    elif diff < 0:
        await database.update_wallet_balance(telegram_id, abs(diff))
        await database.create_transaction(telegram_id, abs(diff), "convert_refund", "wallet", status="approved")

    # ۳. حذف اکانت قدیمی از سرور و پایگاه داده
    old_cat = account.get("category", "singbox")
    old_uname = account.get("panel_username", "")
    try:
        if old_cat in ["singbox", "v2ray", "reality"]:
            await panel_api.delete_user(old_uname)
        elif old_cat in ["system_l2tp", "dnstt"]:
            await panel_api.delete_l2tp_user(old_uname)
        elif old_cat == "wireguard":
            await panel_api.delete_wireguard_account(account.get("panel_password", ""))
    except Exception:
        pass

    await database.delete_account(account_id)

    # ۴. ذخیره اکانت جدید در دیتابیس ربات
    new_acc_id = await database.save_account(
        telegram_id=telegram_id,
        panel_username=new_u,
        panel_password=saved_pass,
        category=target_cat,
        plan_name=target_plan.get("name"),
        server_info=saved_srv,
        sub_token=sub_tok,
        sub_url=sub_url,
        sub_b64_url=sub_b64,
        traffic_gb=target_plan.get("traffic_gb", 30),
        duration_days=target_plan.get("duration_days", 30),
    )

    # ۵. ساخت پیام نهایی با جزئیات دقیق اتصال
    if target_cat in ["singbox", "v2ray", "reality"]:
        msg_text = (
            "🎉 <b>تبدیل اکانت با موفقیت انجام شد!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"سرویس جدید: <b>{target_plan.get('name')}</b>\n"
            f"👤 شناسه اشتراک: <code>{new_u}</code>\n"
            f"🆔 <b>شناسه اتصال (UUID):</b>\n<code>{uuid_str}</code>\n\n"
            "💡 <i>پروتکل‌های V2Ray و Sing-box نیازی به نام کاربری و رمز عبور سنتی ندارند؛ اتصال از طریق شناسه UUID و لینک‌های سابسکریپشن هوشمند زیر برقرار می‌شود:</i>\n\n"
            "🔗 <b>لینک هوشمند سابسکریپشن:</b>\n"
            f"<code>{sub_url}</code>\n\n"
            "📡 <b>لینک ساب Base64 (مخصوص v2rayNG و SlipNet):</b>\n"
            f"<code>{sub_b64}</code>\n\n"
            "👇 جهت باز کردن صفحه وب، دریافت کانفیگ‌های تکی یا دانلود فایل کانفیگ‌ها از دکمه‌های زیر استفاده فرمایید:"
        )
    elif target_cat == "dnstt":
        # استخراج و ارسال خودکار بارکد QR و فایل متنی برای تانل DNS
        all_uris = await panel_api.get_all_dns_slipnet_uris(username=new_u, password=saved_pass)
        primary_uri = all_uris.get("vaydns", {}).get("uri") or all_uris.get("dnstt", {}).get("uri") or ""
        if primary_uri:
            try:
                qr = qrcode.QRCode(box_size=8, border=3)
                qr.add_data(primary_uri)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                bio = io.BytesIO()
                img.save(bio, format="PNG")
                bio.seek(0)
                qr_photo = BufferedInputFile(bio.getvalue(), filename=f"slipnet_qr_{new_u}.png")
                await callback.message.answer_photo(
                    photo=qr_photo,
                    caption=(
                        f"📷 <b>بارکد اختصاصی اتصال سریع به تانل DNS (کلاینت SlipNet)</b>\n\n"
                        f"👤 کاربر: <code>{new_u}</code> | 🔑 رمز: <code>{saved_pass}</code>\n"
                        "💡 جهت اتصال، این بارکد را در نرم‌افزار SlipNet اسکن نمایید."
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass

        if all_uris:
            lines = [
                "==================================================",
                " MS VPN - Complete SlipNet & DNS Tunnel Configs",
                f" Username: {new_u}",
                f" Password: {saved_pass}",
                f" Server Info: {saved_srv}",
                "==================================================\n",
            ]
            for p_key, p_info in all_uris.items():
                lines.append(f"## {p_info.get('label')}")
                lines.append(f"{p_info.get('uri')}\n")

            doc = BufferedInputFile("\n".join(lines).encode("utf-8"), filename=f"MS_SlipNet_{new_u}.txt")
            await callback.message.answer_document(
                doc,
                caption="📁 <b>فایل جامع کلیه کانفیگ‌های تانل DNS و SlipNet جهت دانلود</b>",
                parse_mode="HTML",
            )

        cfg_blocks = []
        for p_key, p_info in all_uris.items():
            lbl = p_info.get("label", p_key.upper())
            uri = p_info.get("uri", "")
            cfg_blocks.append(f"⚡ <b>{lbl}:</b>\n<code>{uri}</code>")

        all_cfgs_text = "\n\n".join(cfg_blocks)
        msg_text = (
            "🎉 <b>تبدیل اکانت با موفقیت انجام شد!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"سرویس جدید: <b>{target_plan.get('name')}</b> (DNS Tunnel / SlipNet)\n"
            f"👤 <b>نام کاربری:</b> <code>{new_u}</code>\n"
            f"🔑 <b>رمز عبور:</b> <code>{saved_pass}</code>\n"
            f"📡 <b>دامنه سرور:</b> <code>{saved_srv}</code>\n\n"
            "📋 <b>کانفیگ‌های کلاینت SlipNet (با یک لمس، کد کپی می‌شود):</b>\n\n"
            f"{all_cfgs_text}\n\n"
            "💡 <i>پروتکل‌های بالا در شرایط فیلترینگ شدید از طریق پورت ۵۳ به راحتی متصل می‌شوند.</i>"
        )
    elif target_cat == "wireguard":
        msg_text = (
            "🎉 <b>تبدیل اکانت با موفقیت انجام شد!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"سرویس جدید شما: <b>{target_plan.get('name')}</b> (WireGuard)\n"
            f"👤 نام کاربری: <code>{new_u}</code>\n\n"
            "فایل کانفیگ اختصاصی (.conf) و بارکد QR در بخش اکانت‌های من آماده دریافت می‌باشد."
        )
    elif target_cat == "gas":
        msg_text = (
            "🎉 <b>تبدیل اکانت با موفقیت انجام شد!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"سرویس جدید: <b>{target_plan.get('name')}</b> (Google Apps Script)\n"
            f"👤 نام پروژه: <code>{new_u}</code>\n"
            f"🔑 کلید رمز تونل: <code>{saved_pass}</code>\n\n"
            "🔗 <b>لینک اختصاصی وب‌اپ گوگل:</b>\n"
            f"<code>{sub_url}</code>\n\n"
            "🚀 <b>لینک اختصاصی Goose VPN:</b>\n"
            f"<code>{sub_b64}</code>"
        )
    else:
        msg_text = (
            "🎉 <b>تبدیل اکانت با موفقیت انجام شد!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"سرویس جدید: <b>{target_plan.get('name')}</b>\n"
            f"👤 نام کاربری: <code>{new_u}</code>\n"
            f"🔑 رمز عبور: <code>{saved_pass}</code>\n"
            f"🌐 آدرس سرور: <code>{saved_srv}</code>\n\n"
            "جهت دانلود فایل OpenVPN، دریافت کانفیگ‌های SlipNet یا سرتیفیکیت‌ها دکمه‌های زیر را لمس فرمایید:"
        )

    await callback.message.edit_text(
        msg_text,
        reply_markup=account_details_keyboard(new_acc_id, category=target_cat, sub_url=sub_url),
        parse_mode="HTML",
    )


# ──────────────────────────────────────────────────────────────
#  استعلام و جستجوی هوشمند کانفیگ بر اساس UID / UUID / ساب‌توکن
# ──────────────────────────────────────────────────────────────

def extract_identifiers(text: str) -> List[str]:
    """استخراج شناسه‌ها، UUID، ساب‌توکن یا نام کاربری از متن ورودی یا لینک‌های کانفیگ."""
    text = (text or "").strip()
    uids = []

    # 1. تطبیق الگوی استاندارد UUID
    uuid_match = re.search(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', text)
    if uuid_match:
        uids.append(uuid_match.group(0).lower())

    # 2. تطبیق توکن سابسکریپشن از لینک ساب
    sub_match = re.search(r'/sub/([A-Za-z0-9_\-]+)', text)
    if sub_match:
        sub_tok = sub_match.group(1).split("/")[0]
        if sub_tok and sub_tok not in uids:
            uids.append(sub_tok)

    # 3. تطبیق لینک VMess Base64
    if text.startswith("vmess://"):
        try:
            b64_str = text[8:].strip()
            padded = b64_str + "=" * (-len(b64_str) % 4)
            data = json.loads(base64.b64decode(padded).decode("utf-8", errors="ignore"))
            if "id" in data and str(data["id"]).lower() not in uids:
                uids.append(str(data["id"]).lower())
        except Exception:
            pass

    # 4. پاکسازی متن تمیز ورودی
    clean = re.sub(r'[\r\n\t ]+', '', text)
    if clean and clean.lower() not in [x.lower() for x in uids]:
        uids.append(clean)

    return uids


async def execute_config_search(query: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """جستجوی زنده کانفیگ بر اساس کاندیداهای استخراج شده در پنل MHPanel و دیتابیس محلی."""
    candidates = extract_identifiers(query)
    if not candidates:
        return None, None

    # الف) جستجو در دیتابیس محلی ربات
    for cand in candidates:
        acc = await database.find_account_in_db(cand)
        if acc:
            cat = acc.get("category", "singbox")
            uname = acc.get("panel_username")
            live_data = None
            if cat in ("singbox", "v2ray", "reality"):
                live_res = await panel_api.get_user_details(uname)
                if live_res and live_res.get("success"):
                    live_data = live_res.get("user", {})
            if not live_data:
                live_data = {
                    "username": uname,
                    "uuid": acc.get("uuid") or "در سرور فعال",
                    "category": acc.get("plan_name"),
                    "traffic_limit_formatted": f"{acc.get('traffic_gb', 0)} GB",
                    "used_traffic_formatted": "—",
                    "traffic_percent": 0.0,
                    "expire_date": f"{acc.get('duration_days', 0)} روز",
                    "enabled": True,
                    "sub_url": acc.get("sub_url"),
                    "sub_b64_url": acc.get("sub_b64_url"),
                }
            return live_data, acc

    # ب) جستجو در کلیه کاربران پنل Sing-box
    try:
        all_res = await panel_api.get_all_users()
        if all_res and all_res.get("success"):
            users = all_res.get("users", [])
            for cand in candidates:
                cand_lower = cand.lower()
                cand_nodash = cand_lower.replace("-", "")
                for u in users:
                    u_uuid = (u.get("uuid") or "").lower()
                    u_token = (u.get("sub_token") or "").lower()
                    u_name = (u.get("username") or "").lower()

                    if (
                        cand_lower in (u_uuid, u_token, u_name)
                        or (len(cand_nodash) == 32 and u_uuid.replace("-", "") == cand_nodash)
                    ):
                        acc = await database.get_account_by_panel_username(u.get("username"))
                        return u, acc
    except Exception as e:
        logger.error(f"خطا در جستجوی کاربران پنل: {e}")

    return None, None


@router.message(F.text.in_({"🔍 استعلام کانفیگ", "🔍 استعلام با شناسه (UID)"}))
async def msg_start_config_search(message: types.Message, state: FSMContext):
    """شروع فرآیند جستجوی کانفیگ با کلیک روی دکمه منوی اصلی."""
    await state.set_state(ConfigSearchStates.waiting_uid)
    text = (
        "🔍 <b>استعلام و رهگیری کانفیگ با شناسه (UID)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "لطفاً <b>شناسه اتصال (UUID)</b>، <b>لینک کانفیگ (VLESS / VMess)</b> یا <b>لینک سابسکریپشن</b> خود را ارسال نمایید:\n\n"
        "💡 <i>ربات به صورت خودکار شناسه را تشخیص داده و وضعیت لحظه‌ای، حجم مصرفی و مهلت باقیمانده را از سرور استعلام می‌کند.</i>"
    )
    await message.answer(text, reply_markup=cancel_keyboard, parse_mode="HTML")


@router.callback_query(F.data == "acc:search_uid")
async def cb_start_config_search(callback: types.CallbackQuery, state: FSMContext):
    """شروع فرآیند جستجوی کانفیگ از طریق دکمه شیشه‌ای درون‌برنامه‌ای."""
    await state.set_state(ConfigSearchStates.waiting_uid)
    text = (
        "🔍 <b>استعلام و رهگیری کانفیگ با شناسه (UID)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "لطفاً <b>شناسه اتصال (UUID)</b>، <b>لینک کانفیگ (VLESS / VMess)</b> یا <b>لینک سابسکریپشن</b> خود را در چت ارسال نمایید:\n\n"
        "💡 <i>می‌توانید کل لینک سابسکریپشن یا کد UUID اختصاصی کانفیگ خود را کپی و ارسال کنید.</i>"
    )
    await callback.message.answer(text, reply_markup=cancel_keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(ConfigSearchStates.waiting_uid)
async def process_config_search_input(message: types.Message, state: FSMContext):
    """پردازش متن ورودی کاربر جهت یافتن مشخصات کانفیگ."""
    text_input = (message.text or "").strip()
    if text_input in ["❌ لغو", "/cancel"]:
        await state.clear()
        return await message.answer("عملیات استعلام کانفیگ لغو شد.", reply_markup=main_menu_keyboard)

    await state.clear()
    wait_msg = await message.answer("⏳ در حال استعلام و دریافت مشخصات از سرور...")

    live_user, acc = await execute_config_search(text_input)

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if not live_user:
        fail_text = (
            "❌ <b>کانفیگی با شناسه یا مشخصات وارد شده یافت نشد!</b>\n\n"
            "لطفاً از صحت شناسه (UUID) یا لینک کپی‌شده اطمینان حاصل فرمایید."
        )
        kb = InlineKeyboardBuilder()
        kb.button(text="🔍 تلاش مجدد", callback_data="acc:search_uid")
        kb.button(text="🔙 منوی اصلی", callback_data="menu:home")
        kb.adjust(1)
        return await message.answer(fail_text, reply_markup=kb.as_markup(), parse_mode="HTML")

    is_owner = (acc is not None and acc.get("telegram_id") == message.from_user.id)
    acc_id = acc.get("id") if acc else None
    card_text = format_searched_config(live_user, account=acc, is_owner=is_owner)
    kb = config_search_result_keyboard(uid_or_query=text_input, account_id=acc_id, is_owner=is_owner)

    await message.answer(card_text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("acc:refresh_uid:"))
async def cb_refresh_config_search(callback: types.CallbackQuery):
    """بروزرسانی زنده مشخصات کانفیگ استعلام شده."""
    query = callback.data.split(":", 2)[2]
    live_user, acc = await execute_config_search(query)

    if not live_user:
        return await callback.answer("کانفیگ در سرور یافت نشد یا حذف شده است.", show_alert=True)

    is_owner = (acc is not None and acc.get("telegram_id") == callback.from_user.id)
    acc_id = acc.get("id") if acc else None
    card_text = format_searched_config(live_user, account=acc, is_owner=is_owner)
    kb = config_search_result_keyboard(uid_or_query=query, account_id=acc_id, is_owner=is_owner)

    try:
        await callback.message.edit_text(card_text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer("🔄 اطلاعات و وضعیت مصرف بروزرسانی شد.")


# ──────────────────────────────────────────────────────────────
#  هدیه دادن کانفیگ (انتقال اشتراک به کاربر دیگر در ربات)
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "acc:gift_select")
async def cb_gift_select_account(callback: types.CallbackQuery, state: FSMContext):
    """انتخاب اکانت جهت هدیه دادن از لیست اشتراک‌های کاربر."""
    telegram_id = callback.from_user.id
    accounts = await database.get_user_accounts(telegram_id)
    if not accounts:
        return await callback.answer("شما هیچ اکانت فعالی برای هدیه دادن ندارید.", show_alert=True)

    if len(accounts) == 1:
        callback.data = f"acc:gift_ask:{accounts[0]['id']}"
        return await cb_gift_ask_target(callback, state)

    text = (
        "🎁 <b>هدیه دادن اشتراک به کاربر دیگر</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "لطفاً اکانتی را که مایلید به عنوان هدیه منتقل فرمایید، انتخاب نمایید:"
    )
    await callback.message.edit_text(text, reply_markup=account_gift_select_keyboard(accounts), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("acc:gift_ask:"))
async def cb_gift_ask_target(callback: types.CallbackQuery, state: FSMContext):
    """دریافت درخواست هدیه دادن اکانت و درخواست شناسه گیرنده."""
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد یا متعلق به شما نیست.", show_alert=True)

    await state.set_state(AccountGiftStates.waiting_target_user)
    await state.update_data(gift_account_id=account_id)

    plan = account.get("plan_name", "اشتراک VPN")
    uname = account.get("panel_username", "—")

    text = (
        "🎁 <b>هدیه و انتقال اشتراک به کاربر دیگر</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 <b>پلن انتخابی:</b> <b>{plan}</b>\n"
        f"👤 <b>شناسه اکانت:</b> <code>{uname}</code>\n\n"
        "👇 لطفاً <b>شناسه عددی (Telegram ID)</b> یا <b>یوزرنیم (@username)</b> کاربری که می‌خواهید این اشتراک را به او هدیه دهید در چت ارسال فرمایید:\n\n"
        "💡 <i>نکته: کاربر گیرنده باید حداقل یک‌بار ربات را با دکمه /start راه‌اندازی کرده باشد تا در سیستم شناخته شود.</i>"
    )
    await callback.message.answer(text, reply_markup=cancel_keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(AccountGiftStates.waiting_target_user)
async def process_gift_target_user(message: types.Message, state: FSMContext):
    """بررسی کاربر گیرنده و نمایش فاکتور تأیید هدیه."""
    raw_target = (message.text or "").strip()
    if raw_target in ["❌ لغو", "/cancel"]:
        await state.clear()
        return await message.answer("عملیات هدیه دادن اشتراک لغو شد.", reply_markup=main_menu_keyboard)

    data = await state.get_data()
    account_id = data.get("gift_account_id")
    if not account_id:
        await state.clear()
        return await message.answer("خطا در بازیابی اطلاعات اکانت. لطفاً دوباره تلاش فرمایید.", reply_markup=main_menu_keyboard)

    sender_id = message.from_user.id
    account = await database.get_account_by_id(account_id, sender_id)
    if not account:
        await state.clear()
        return await message.answer("اکانت مورد نظر یافت نشد یا مالکیت آن تغییر کرده است.", reply_markup=main_menu_keyboard)

    target_user = await database.find_user_by_id_or_username(raw_target)
    if not target_user:
        return await message.answer(
            "❌ <b>کاربر گیرنده در سیستم ربات یافت نشد!</b>\n\n"
            "گیرنده باید حداقل یک‌بار دکمه /start را در ربات زده باشد.\n"
            "لطفاً شناسه عددی (Telegram ID) یا یوزرنیم صحیح را ارسال فرمایید (یا دکمه ❌ لغو را لمس نمایید):",
            reply_markup=cancel_keyboard,
            parse_mode="HTML",
        )

    target_id = target_user.get("telegram_id")
    if target_id == sender_id:
        return await message.answer(
            "⚠️ <b>خطا:</b> شما نمی‌توانید اشتراک را به خودتان هدیه دهید!\nلطفاً شناسه کاربر دیگری را ارسال فرمایید:",
            reply_markup=cancel_keyboard,
            parse_mode="HTML",
        )

    target_name = target_user.get("first_name") or "کاربر گرامی"
    target_uname = f"@{target_user.get('username')}" if target_user.get("username") else "—"

    confirm_text = (
        "🎁 <b>تأیید نهایی انتقال و هدیه اشتراک</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>اشتراک اهدایی:</b> <b>{account.get('plan_name')}</b> (<code>{account.get('panel_username')}</code>)\n\n"
        f"👤 <b>مشخصات گیرنده هدیه:</b>\n"
        f"▫️ نام: <b>{target_name}</b>\n"
        f"▫️ شناسه کاربری: <code>{target_id}</code>\n"
        f"▫️ یوزرنیم: <b>{target_uname}</b>\n\n"
        "⚠️ <b>توجه مهم:</b>\n"
        "پس از لمس دکمه تأیید، این اشتراک بلافاصله از حساب شما خارج و به لیست اکانت‌های گیرنده منتقل شده و پیام تبریک به همراه مشخصات اتصال برای ایشان ارسال می‌گردد.\n\n"
        "آیا از انتقال و هدیه دادن این اشتراک اطمینان دارید؟"
    )

    await state.clear()
    await message.answer(
        confirm_text,
        reply_markup=account_gift_confirm_keyboard(account_id, target_id),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("acc:gift_confirm:"))
async def cb_gift_execute_confirm(callback: types.CallbackQuery):
    """اجرای نهایی هدیه دادن اکانت در دیتابیس و پنل."""
    parts = callback.data.split(":")
    account_id = int(parts[2])
    target_id = int(parts[3])
    sender_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, sender_id)
    if not account:
        return await callback.answer("اکانت یافت نشد یا قبلاً منتقل شده است.", show_alert=True)

    target_user = await database.get_user(target_id)
    if not target_user:
        return await callback.answer("کاربر گیرنده یافت نشد.", show_alert=True)

    # انتقال مالکیت در دیتابیس
    success = await database.transfer_account(
        account_id=account_id,
        current_owner_id=sender_id,
        new_owner_id=target_id,
    )
    if not success:
        return await callback.answer("خطا در انتقال اکانت. لطفاً دوباره تلاش نمایید.", show_alert=True)

    panel_user = account.get("panel_username", "")
    plan_name = account.get("plan_name", "اشتراک VPN")
    sender_name = callback.from_user.first_name or "کاربر گرامی"
    sender_uname = f" (@{callback.from_user.username})" if callback.from_user.username else ""

    # بروزرسانی یادداشت کاربر در پنل در صورت امکان
    try:
        await panel_api.edit_user(
            panel_user,
            note=f"Gifted from {sender_id} to {target_id} - {plan_name}",
        )
    except Exception:
        pass

    # ارسال اعلان و پیام تبریک به گیرنده هدیه
    try:
        gift_notice = (
            "🎉🎁 <b>تبریک! شما یک اشتراک هدیه دریافت کردید!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"کاربر گرامی <b>{sender_name}</b>{sender_uname} یک اشتراک اختصاصی VPN به شما هدیه داد.\n\n"
            f"🏷 <b>پلن:</b> <b>{plan_name}</b>\n"
            f"👤 <b>شناسه اشتراک:</b> <code>{panel_user}</code>\n\n"
            "💡 <i>این اشتراک اکنون در پنل کاربری شما ثبت شده است. جهت مشاهده اطلاعات اتصال، دریافت لینک سابسکریپشن و بارکد دکمه زیر را لمس فرمایید:</i>"
        )
        rec_kb = InlineKeyboardBuilder()
        rec_kb.button(text="📦 مشاهده و اتصال به اشتراک هدیه", callback_data=f"acc:view:{account_id}")
        rec_kb.button(text="📦 اکانت‌های من", callback_data="acc:list")
        rec_kb.adjust(1)
        await callback.bot.send_message(target_id, gift_notice, reply_markup=rec_kb.as_markup(), parse_mode="HTML")
    except Exception as e:
        logger.warning(f"عدم امکان ارسال پیام هدیه به گیرنده {target_id}: {e}")

    target_name = target_user.get("first_name") or "کاربر"
    success_sender_text = (
        "🎉 <b>اشتراک شما با موفقیت هدیه داده شد!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"اشتراک <b>{plan_name}</b> (<code>{panel_user}</code>) با موفقیت به کاربر <b>{target_name}</b> (<code>{target_id}</code>) انتقال یافت.\n\n"
        "پیام تبریک و لینک اتصال برای گیرنده ارسال شد."
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="📦 لیست اکانت‌های من", callback_data="acc:list")
    kb.button(text="🔙 منوی اصلی", callback_data="menu:home")
    kb.adjust(1)

    await callback.message.edit_text(success_sender_text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer("اشتراک با موفقیت منتقل گردید!")


@router.callback_query(F.data.startswith("acc:gift_cancel:"))
async def cb_gift_cancel(callback: types.CallbackQuery, state: FSMContext):
    """انصراف از هدیه دادن و بازگشت به جزئیات اکانت."""
    await state.clear()
    account_id = int(callback.data.split(":")[2])
    callback.data = f"acc:view:{account_id}"
    await cb_view_account(callback)


# ──────────────────────────────────────────────────────────────
#  تنظیم نام دلخواه برای اکانت (Custom Alias / Label)
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("acc:set_name:"))
async def cb_account_set_name_start(callback: types.CallbackQuery, state: FSMContext):
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id
    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    await state.set_state(UserAccountManageStates.waiting_account_name)
    await state.update_data(target_acc_id=account_id)

    curr_name = account.get("custom_name") or "هنوز نامی ثبت نشده است"
    text = (
        "✏️ <b>تنظیم یا ویرایش نام دلخواه برای این کانفیگ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 نام فعلی: <b>{curr_name}</b>\n\n"
        "لطفاً یک نام دلخواه برای این اکانت ارسال فرمایید:\n"
        "(مثلاً: <code>گوشی علی</code>، <code>لپ‌تاپ</code>، <code>اینترنت منزل</code> یا <code>کانفیگ پدر</code>)\n\n"
        "<i>💡 جهت حذف نام دلخواه و بازگشت به عنوان پیش‌فرض، عدد 0 را ارسال کنید.</i>"
    )
    await callback.message.answer(text, reply_markup=cancel_keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(UserAccountManageStates.waiting_account_name)
async def state_account_set_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    acc_id = data.get("target_acc_id")
    await state.clear()

    text_input = (message.text or "").strip()
    if text_input == "❌ لغو":
        return await message.answer("❌ عملیات تغییر نام اکانت لغو شد.", reply_markup=main_menu_keyboard)

    telegram_id = message.from_user.id
    new_name = "" if text_input == "0" else text_input[:50]
    await database.update_account_custom_name(acc_id, telegram_id, new_name)

    account = await database.get_account_by_id(acc_id, telegram_id)
    cat = account.get("category", "singbox") if account else "singbox"
    sub_url = account.get("sub_url", "") if account else ""

    success_msg = "✅ نام دلخواه اکانت حذف شد." if not new_name else f"✅ نام دلخواه اکانت به «<b>{new_name}</b>» تغییر یافت."
    await message.answer(success_msg, reply_markup=main_menu_keyboard, parse_mode="HTML")

    if account:
        srv_ip = await database.get_setting("server_ip", settings.SERVER_IP)
        psk = await database.get_setting("ipsec_psk", settings.IPSEC_PSK)
        live_data = None
        if cat in ("singbox", "v2ray", "reality"):
            live_data = await panel_api.get_user_details(account.get("panel_username"))
        card_text = format_account_details(account, live_data if (live_data and live_data.get("success")) else None, server_ip=srv_ip, psk=psk)
        await message.answer(card_text, reply_markup=account_details_keyboard(acc_id, category=cat, sub_url=sub_url), parse_mode="HTML")


# ──────────────────────────────────────────────────────────────
#  مدیریت پوشه‌ها و دسته‌بندی‌های شخصی کاربر (User Folders)
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "acc:manage_user_cats")
async def cb_user_categories_manage(callback: types.CallbackQuery):
    telegram_id = callback.from_user.id
    categories = await database.get_user_categories(telegram_id)

    text = (
        "📁 <b>مدیریت پوشه‌ها و دسته‌بندی‌های شخصی شما</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "شما می‌توانید برای اکانت‌های خود دسته‌بندی‌های مختلف (مانند: <b>خانوادگی</b>، <b>همکاران</b>، <b>شخصی</b> و...) بسازید تا کانفیگ‌هایتان مرتب باشند.\n\n"
        "جهت مشاهده و ویرایش روی دسته بزنید، یا یک دسته جدید بسازید:"
    )
    await callback.message.edit_text(text, reply_markup=user_categories_menu_keyboard(categories), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "acc:user_cat_new")
@router.callback_query(F.data.startswith("acc:user_cat_new_for:"))
async def cb_user_cat_new_start(callback: types.CallbackQuery, state: FSMContext):
    target_acc_id = None
    if callback.data.startswith("acc:user_cat_new_for:"):
        target_acc_id = int(callback.data.split(":")[2])

    await state.set_state(UserAccountManageStates.waiting_new_category_name)
    await state.update_data(target_acc_id=target_acc_id)

    text = (
        "➕ <b>ساخت دسته‌بندی شخصی جدید</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "لطفاً <b>نام دسته‌بندی جدید</b> را ارسال فرمایید:\n"
        "(مثلاً: <code>خانوادگی</code>، <code>دوستان</code>، <code>گوشی‌های منزل</code>)"
    )
    await callback.message.answer(text, reply_markup=cancel_keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(UserAccountManageStates.waiting_new_category_name)
async def state_user_cat_new_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_acc_id = data.get("target_acc_id")
    await state.clear()

    name = (message.text or "").strip()
    if name == "❌ لغو":
        return await message.answer("❌ ساخت دسته‌بندی لغو شد.", reply_markup=main_menu_keyboard)

    telegram_id = message.from_user.id
    cat_id = await database.create_user_category(telegram_id, name[:40])

    if target_acc_id:
        await database.update_account_user_category(target_acc_id, telegram_id, cat_id)
        await message.answer(
            f"🎉 <b>دسته‌بندی «{name}» ساخته شد و اکانت به این دسته منتقل گردید!</b>",
            reply_markup=main_menu_keyboard,
            parse_mode="HTML",
        )
        # بازگشت به اکانت
        account = await database.get_account_by_id(target_acc_id, telegram_id)
        if account:
            cat = account.get("category", "singbox")
            sub_url = account.get("sub_url", "")
            srv_ip = await database.get_setting("server_ip", settings.SERVER_IP)
            psk = await database.get_setting("ipsec_psk", settings.IPSEC_PSK)
            live_data = None
            if cat in ("singbox", "v2ray", "reality"):
                live_data = await panel_api.get_user_details(account.get("panel_username"))
            card_text = format_account_details(account, live_data if (live_data and live_data.get("success")) else None, server_ip=srv_ip, psk=psk)
            await message.answer(card_text, reply_markup=account_details_keyboard(target_acc_id, category=cat, sub_url=sub_url), parse_mode="HTML")
    else:
        await message.answer(
            f"🎉 <b>دسته‌بندی «{name}» با موفقیت ساخته شد!</b>\n"
            "اکنون می‌توانید از مشخصات هر اکانت، آن را به این دسته اختصاص دهید.",
            reply_markup=main_menu_keyboard,
            parse_mode="HTML",
        )
        categories = await database.get_user_categories(telegram_id)
        text = "📁 <b>لیست دسته‌بندی‌های شخصی شما:</b>"
        await message.answer(text, reply_markup=user_categories_menu_keyboard(categories), parse_mode="HTML")


@router.callback_query(F.data.startswith("acc:user_cat_view:"))
async def cb_user_cat_view(callback: types.CallbackQuery):
    cat_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    cat = await database.get_user_category(cat_id, telegram_id)
    if not cat:
        return await callback.answer("دسته‌بندی یافت نشد.", show_alert=True)

    accounts = await database.get_user_accounts(telegram_id, user_category_id=cat_id)
    acc_lines = []
    for idx, a in enumerate(accounts, 1):
        cname = a.get("custom_name")
        pname = a.get("plan_name", "اشتراک")
        display_label = f"{cname} ({pname})" if cname else pname
        acc_lines.append(f"▫️ {to_fa(idx)}. <b>{display_label}</b> — <code>{a.get('panel_username')}</code>")

    acc_block = "\n".join(acc_lines) if acc_lines else "📭 هیچ اکانتی در این دسته قرار ندارد."
    text = (
        f"📁 <b>مشخصات دسته‌بندی «{cat.get('name')}»</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"تعداد اکانت‌ها: <b>{to_fa(len(accounts))} عدد</b>\n\n"
        f"<b>کانفیگ‌های این دسته:</b>\n{acc_block}\n\n"
        "جهت تغییر نام یا حذف این دسته از دکمه‌های زیر استفاده کنید:"
    )
    await callback.message.edit_text(text, reply_markup=user_category_view_keyboard(cat_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("acc:user_cat_rename:"))
async def cb_user_cat_rename_start(callback: types.CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id
    cat = await database.get_user_category(cat_id, telegram_id)
    if not cat:
        return await callback.answer("دسته‌بندی یافت نشد.", show_alert=True)

    await state.set_state(UserAccountManageStates.waiting_rename_category)
    await state.update_data(target_cat_id=cat_id)

    text = (
        f"✏️ <b>ویرایش نام دسته‌بندی «{cat.get('name')}»</b>\n\n"
        "لطفاً نام جدید مورد نظر خود را ارسال فرمایید:"
    )
    await callback.message.answer(text, reply_markup=cancel_keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(UserAccountManageStates.waiting_rename_category)
async def state_user_cat_rename_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cat_id = data.get("target_cat_id")
    await state.clear()

    name = (message.text or "").strip()
    if name == "❌ لغو":
        return await message.answer("❌ ویرایش نام لغو شد.", reply_markup=main_menu_keyboard)

    telegram_id = message.from_user.id
    await database.update_user_category_name(cat_id, telegram_id, name[:40])
    await message.answer(f"✅ نام دسته‌بندی با موفقیت به «<b>{name}</b>» تغییر یافت.", reply_markup=main_menu_keyboard, parse_mode="HTML")

    categories = await database.get_user_categories(telegram_id)
    await message.answer("📁 <b>لیست دسته‌بندی‌های شخصی شما:</b>", reply_markup=user_categories_menu_keyboard(categories), parse_mode="HTML")


@router.callback_query(F.data.startswith("acc:user_cat_del_ask:"))
async def cb_user_cat_del_ask(callback: types.CallbackQuery):
    cat_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id
    cat = await database.get_user_category(cat_id, telegram_id)
    if not cat:
        return await callback.answer("دسته‌بندی یافت نشد.", show_alert=True)

    text = (
        f"⚠️ <b>آیا از حذف دسته‌بندی «{cat.get('name')}» اطمینان دارید؟</b>\n\n"
        "💡 <i>توجه: با حذف این دسته‌بندی، اکانت‌های درون آن حذف نمی‌شوند و فقط به حالت بدون دسته درمی‌آیند.</i>"
    )
    await callback.message.edit_text(text, reply_markup=user_cat_delete_confirm_keyboard(cat_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("acc:user_cat_del_confirm:"))
async def cb_user_cat_del_confirm(callback: types.CallbackQuery):
    cat_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id
    await database.delete_user_category(cat_id, telegram_id)
    await callback.answer("🗑 دسته‌بندی با موفقیت حذف شد.", show_alert=True)

    categories = await database.get_user_categories(telegram_id)
    text = "📁 <b>دسته‌بندی با موفقیت حذف شد. لیست دسته‌بندی‌های شما:</b>"
    await callback.message.edit_text(text, reply_markup=user_categories_menu_keyboard(categories), parse_mode="HTML")


@router.callback_query(F.data.startswith("acc:set_cat:"))
async def cb_account_set_cat_menu(callback: types.CallbackQuery):
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    categories = await database.get_user_categories(telegram_id)
    current_cat_id = account.get("user_category_id")

    text = (
        "📁 <b>انتخاب و تغییر پوشه / دسته‌بندی این اکانت</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"اکانت: <b>{account.get('custom_name') or account.get('plan_name')}</b>\n"
        f"دسته‌بندی فعلی: <b>{account.get('user_category_name') or 'بدون دسته‌بندی'}</b>\n\n"
        "دسته‌بندی مورد نظر خود را انتخاب کنید یا یک دسته جدید بسازید:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=user_assign_category_keyboard(account_id, categories, current_cat_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("acc:assign_cat:"))
async def cb_account_assign_cat_execute(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    account_id = int(parts[2])
    target_cat_id = int(parts[3])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    await database.update_account_user_category(account_id, telegram_id, target_cat_id if target_cat_id > 0 else None)

    if target_cat_id > 0:
        cat_info = await database.get_user_category(target_cat_id, telegram_id)
        cat_title = cat_info.get("name") if cat_info else "دسته انتخابی"
        await callback.answer(f"✅ این کانفیگ در دسته «{cat_title}» قرار گرفت.", show_alert=True)
    else:
        await callback.answer("✅ کانفیگ از دسته‌بندی خارج شد (بدون دسته).", show_alert=True)

    account = await database.get_account_by_id(account_id, telegram_id)
    cat = account.get("category", "singbox")
    sub_url = account.get("sub_url", "")
    srv_ip = await database.get_setting("server_ip", settings.SERVER_IP)
    psk = await database.get_setting("ipsec_psk", settings.IPSEC_PSK)
    live_data = None
    if cat in ("singbox", "v2ray", "reality"):
        live_data = await panel_api.get_user_details(account.get("panel_username"))
    card_text = format_account_details(account, live_data if (live_data and live_data.get("success")) else None, server_ip=srv_ip, psk=psk)
    await callback.message.edit_text(card_text, reply_markup=account_details_keyboard(account_id, category=cat, sub_url=sub_url), parse_mode="HTML")


# ──────────────────────────────────────────────────────────────
#  لغو و حذف کانفیگ با عودت وجه باقیمانده به کیف پول (Refund)
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("acc:del_ask:"))
async def cb_account_delete_ask(callback: types.CallbackQuery):
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد.", show_alert=True)

    cat = account.get("category", "singbox")
    live_data = None
    if cat in ("singbox", "v2ray", "reality"):
        live_data = await panel_api.get_user_details(account.get("panel_username"))

    plan_price = 0
    if not account.get("price") and not account.get("is_trial"):
        plans = await database.get_plans_by_category(cat, active_only=False)
        for p in plans:
            if p.get("name") == account.get("plan_name"):
                plan_price = p.get("price", 0)
                break

    refund_amount, breakdown = calculate_account_refund(account, live_data, plan_price=plan_price)

    custom_name = account.get("custom_name")
    plan_name = account.get("plan_name", "اشتراک VPN")
    display_name = f"{custom_name} ({plan_name})" if custom_name else plan_name

    if account.get("is_trial"):
        confirm_text = (
            f"🗑 <b>حذف اکانت تستی: {display_name}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 شناسه: <code>{account.get('panel_username')}</code>\n\n"
            "⚠️ این اشتراک یک اکانت تستی رایگان بوده است و شامل عودت وجه نمی‌باشد.\n"
            "با تایید، این اکانت از سرور و لیست شما حذف خواهد شد."
        )
    else:
        used_gb_str = f"{to_fa(breakdown['used_gb'])} از {to_fa(breakdown['total_gb'])} GB" if breakdown['total_gb'] > 0 else "نامحدود"
        rem_gb_str = f"{to_fa(breakdown['remaining_gb'])} گیگابایت" if breakdown['total_gb'] > 0 else "نامحدود"
        rem_days_str = f"{to_fa(breakdown['remaining_days'])} از {to_fa(breakdown['total_days'])} روز"
        pct_str = f"{to_fa(round(breakdown['refund_ratio'] * 100, 1))}٪"

        confirm_text = (
            f"🗑 <b>لغو و حذف اشتراک با عودت وجه به کیف پول</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🏷 <b>اشتراک:</b> <b>{display_name}</b>\n"
            f"👤 <b>نام کاربری:</b> <code>{account.get('panel_username')}</code>\n"
            f"💰 <b>مبلغ اولیه خرید:</b> <b>{to_toman(breakdown['price'])}</b>\n\n"
            "📊 <b>میزان مصرف و باقیمانده سرویس:</b>\n"
            f"▫️ ترافیک مصرفی: <b>{used_gb_str}</b>\n"
            f"▫️ حجم باقیمانده: <b>{rem_gb_str}</b>\n"
            f"▫️ زمان باقیمانده: <b>{rem_days_str}</b>\n"
            f"▫️ درصد سهم باقیمانده: <b>{pct_str}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 <b>مبلغ عودت به کیف پول:</b> <b>{to_toman(refund_amount)}</b>\n\n"
            "⚠️ <b>توجه مهم:</b> با تایید حذف، این کانفیگ فوراً از روی سرور باطل و قطع گردیده و "
            f"مبلغ <b>{to_toman(refund_amount)}</b> مستقیماً به موجودی کیف پول حساب کاربری شما اضافه خواهد شد.\n\n"
            "آیا از حذف اشتراک و دریافت وجه اطمینان دارید؟"
        )

    await callback.message.edit_text(confirm_text, reply_markup=account_delete_confirm_keyboard(account_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("acc:del_confirm:"))
async def cb_account_delete_confirm(callback: types.CallbackQuery):
    account_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    account = await database.get_account_by_id(account_id, telegram_id)
    if not account:
        return await callback.answer("اکانت یافت نشد یا قبلاً حذف شده است.", show_alert=True)

    cat = account.get("category", "singbox")
    live_data = None
    if cat in ("singbox", "v2ray", "reality"):
        live_data = await panel_api.get_user_details(account.get("panel_username"))

    plan_price = 0
    if not account.get("price") and not account.get("is_trial"):
        plans = await database.get_plans_by_category(cat, active_only=False)
        for p in plans:
            if p.get("name") == account.get("plan_name"):
                plan_price = p.get("price", 0)
                break

    refund_amount, breakdown = calculate_account_refund(account, live_data, plan_price=plan_price)

    # ۱. حذف واقعی از پنل MHPanel
    from utils.trial_manager import delete_account_from_panel
    await delete_account_from_panel(account)

    # ۲. حذف از دیتابیس ربات
    await database.delete_account(account_id)

    # ۳. واریز مبلغ به کیف پول در صورت وجود
    if refund_amount > 0:
        await database.update_wallet_balance(telegram_id, refund_amount)
        await database.create_transaction(telegram_id, refund_amount, "refund", "wallet", status="approved")

    user = await database.get_user(telegram_id)
    current_balance = user.get("wallet_balance", 0) if user else refund_amount

    success_text = (
        "✅ <b>اشتراک شما با موفقیت لغو و حذف گردید!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 شناسه کانفیگ: <code>{account.get('panel_username')}</code>\n"
    )
    if refund_amount > 0:
        success_text += (
            f"💵 مبلغ بازگشت به کیف پول: <b>{to_toman(refund_amount)}</b>\n"
            f"💰 موجودی فعلی کیف پول شما: <b>{to_toman(current_balance)}</b>\n\n"
            "💡 هم‌اکنون می‌توانید با موجودی کیف پول خود از بخش فروشگاه پلن دیگری خریداری فرمایید."
        )
    else:
        success_text += "\nکانفیگ از سرور و لیست اکانت‌های شما حذف شد."

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="📦 اکانت‌های من", callback_data="acc:list")
    kb.button(text="🛒 خرید اشتراک جدید", callback_data="shop:categories")
    kb.button(text="🔙 منوی اصلی", callback_data="menu:home")
    kb.adjust(1)

    await callback.message.edit_text(success_text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer("اشتراک حذف و عودت وجه با موفقیت انجام شد.")
