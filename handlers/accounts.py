"""هندلر مدیریت اکانت‌ها: نمایش تفکیک‌شده بر اساس پروتکل (Sing-box, L2TP, WireGuard, GAS, DNS Tunnel)."""
import io
import os
import secrets
import uuid
import qrcode
from aiogram import Router, F, types
from aiogram.types import BufferedInputFile, FSInputFile

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
)
from keyboards.reply import main_menu_keyboard
from utils.formatters import format_accounts_list, format_account_details
from utils.helpers import api_error_text, to_toman, to_fa
from utils.cert_manager import (
    get_ovpn_content,
    CISCO_CA_PATH,
    IKEV2_CA_PATH,
    SSTP_CA_PATH,
)

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
    accounts = await database.get_user_accounts(telegram_id)

    text = format_accounts_list(accounts)
    kb = build_accounts_keyboard(accounts) if accounts else None
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "acc:list")
async def cb_accounts_list(callback: types.CallbackQuery):
    telegram_id = callback.from_user.id
    accounts = await database.get_user_accounts(telegram_id)

    text = format_accounts_list(accounts)
    kb = build_accounts_keyboard(accounts) if accounts else None
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

    cfg_text = (
        f"🔑 <b>کانفیگ تکی {proto} ({tag})</b>\n\n"
        f"<code>{link}</code>\n\n"
        "💡 با لمس متن بالا، کانفیگ کپی خواهد شد."
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 بازگشت به لیست کانفیگ‌ها", callback_data=f"acc:configs:{account_id}")
    await callback.message.edit_text(cfg_text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


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

    lines = [
        "=========================================",
        "  MS VPN - V2Ray & Sing-box Configurations",
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
        lines.append(f"## {idx}. {proto} - {tag} (Port {port})\n{link}\n")

    txt_content = "\n".join(lines)
    file_bytes = txt_content.encode("utf-8")
    doc = BufferedInputFile(file_bytes, filename=f"configs_{account.get('panel_username')}.txt")

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

    ovpn_data = get_ovpn_content(server_ip=srv_ip, username=uname, password=pwd)
    filename = f"MS_VPN_OpenVPN_{uname}.ovpn"

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

    doc = BufferedInputFile(conf_content.encode("utf-8"), filename=f"MS_WireGuard_{uname}.conf")
    caption = (
        f"⚡ <b>فایل کانفیگ اختصاصی وایرگارد (WireGuard)</b>\n\n"
        f"👤 نام اکانت: <code>{uname}</code>\n"
        "💡 فایل فوق را مستقیماً در نرم‌افزار رسمی <b>WireGuard</b> وارد (Import) فرمایید."
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

    qr = qrcode.QRCode(box_size=8, border=3)
    qr.add_data(conf_content)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)

    photo = BufferedInputFile(bio.getvalue(), filename=f"wg_qr_{uname}.png")
    caption = (
        f"📷 <b>بارکد اختصاصی WireGuard جهت اسکن با گوشی</b>\n\n"
        f"👤 نام اکانت: <code>{uname}</code>\n"
        "💡 در نرم‌افزار وایرگارد دکمه + را زده و گزینه <b>Scan from QR code</b> را انتخاب کنید."
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

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 بازگشت به مشخصات اکانت", callback_data=f"acc:view:{account_id}")

    text = (
        f"📋 <b>متن کانفیگ وایرگارد ({uname})</b>\n\n"
        f"<pre>{conf_content}</pre>\n\n"
        "💡 با لمس کادر بالا، کل متن کانفیگ کپی خواهد شد."
    )
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


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
