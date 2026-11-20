"""ماژول هوشمند ساخت و ارسال خودکار کانفیگ به کانال مقصد تلگرام (Auto Channel Post).

ویژگی‌ها و قابلیت‌های پشتیبانی‌شده:
  1) ایجاد کانفیگ‌های هوشمند Sing-box / V2Ray با لینک مستقیم سابسکریپشن Base64 و QR Code.
  2) ایجاد و ارسال کانفیگ‌های تانل ضد فیلتر SlipNet (SlowDNS, VayDNS, Slipstream, Tor).
  3) ایجاد و ارسال پروتکل‌های استاندارد سیستمی (Cisco AnyConnect, OpenVPN, L2TP, IKEv2).
  4) امکان انتشار پکیج ترکیبی و همگانی از تمامی پروتکل‌ها.
  5) ارسال خودکار طبق زمان‌بندی روزهای هفته و ساعات تعیین‌شده توسط مدیر.
  6) بررسی دقیق وضعیت دسترسی و مدیریت ربات در کانال قبل از ارسال.
"""
import io
import logging
import secrets
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

import qrcode
from aiogram import Bot
from aiogram.types import BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from api import panel_api
from config import settings
from db import database
from utils.helpers import to_fa, api_error_text
from utils.cert_manager import get_ovpn_content

logger = logging.getLogger("MS_VPN_BOT.channel_poster")

DAY_MAP = {
    5: "sat",  # Saturday
    6: "sun",  # Sunday
    0: "mon",  # Monday
    1: "tue",  # Tuesday
    2: "wed",  # Wednesday
    3: "thu",  # Thursday
    4: "fri",  # Friday
}

DAY_NAMES_FA = {
    "sat": "شنبه",
    "sun": "یک‌شنبه",
    "mon": "دوشنبه",
    "tue": "سه‌شنبه",
    "wed": "چهارشنبه",
    "thu": "پنج‌شنبه",
    "fri": "جمعه",
}

PROTO_TITLES = {
    "singbox": "سوئیت Sing-box و V2Ray (ساب Base64)",
    "slipnet": "تانل ضد فیلتر SlipNet (DNS / SSH / Tor)",
    "system_l2tp": "پروتکل‌های استاندارد (Cisco / OpenVPN / L2TP)",
    "all": "پکیج کامل همگانی (ترکیبی)",
}


async def check_bot_channel_admin(bot: Bot, channel_id: str) -> Tuple[bool, str]:
    """بررسی وضعیت ادمین بودن و دسترسی ارسال پیام توسط ربات در کانال مقصد."""
    if not channel_id:
        return False, "شناسه کانال تنظیم نشده است."

    try:
        me = await bot.get_me()
        chat = await bot.get_chat(channel_id)
        member = await bot.get_chat_member(chat.id, me.id)

        status = getattr(member, "status", "")
        if status in ("administrator", "creator"):
            can_post = getattr(member, "can_post_messages", None)
            if can_post is False:
                return False, f"⚠️ ربات در کانال «{chat.title}» ادمین است ولی دسترسی «ارسال پیام (Post Messages)» ندارد!"
            return True, f"✅ ربات در کانال «{chat.title}» ادمین با دسترسی کامل است."
        else:
            return False, f"⚠️ ربات در کانال «{chat.title}» عضو است اما هنوز به عنوان «مدیر (Admin)» تعیین نشده است!"
    except Exception as e:
        err_msg = str(e).lower()
        if "chat not found" in err_msg:
            return False, "❌ کانال یافت نشد! لطفاً اطمینان حاصل کنید شناسه یا یوزرنیم کانال صحیح است و ربات در آن عضو شده است."
        elif "bot is not a member" in err_msg:
            return False, "❌ ربات در این کانال عضو نیست! ابتدا ربات را به کانال اضافه کرده و دسترسی مدیریت به آن بدهید."
        return False, f"❌ خطا در استعلام کانال: {e}"


def _generate_qr_buffer(content: str) -> io.BytesIO:
    """تولید تصویر کیوآرکد در قالب بایت مموری."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(content)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio


async def _post_singbox_config(
    bot: Bot,
    channel_id: str,
    conf: Dict[str, Any],
    traffic_gb: float,
    duration_days: int,
    send_qr: bool,
    now_fa: str,
    bot_username: str,
) -> Dict[str, Any]:
    """ساخت و ارسال کانفیگ هسته Sing-box / V2Ray با لینک سابسکریپشن هوشمند Base64."""
    time_tag = datetime.now().strftime("%H%M")
    rand_suffix = secrets.token_hex(2)
    panel_user = f"ch_sb_{time_tag}_{rand_suffix}"

    res = await panel_api.create_user(
        username=panel_user,
        traffic_limit_gb=traffic_gb,
        validity_days=duration_days,
        expiry_type="on_first_use",
        category="MS_Channel_Auto",
        note=f"Auto Channel Singbox: {channel_id}",
    )
    if not res.get("success"):
        return {"success": False, "error": f"خطا در ساخت کانفیگ در پنل: {api_error_text(res)}"}

    created_u = res.get("user", {})
    sub_token = created_u.get("sub_token", "")
    sub_raw_url = created_u.get("sub_url", f"{settings.PANEL_SUB_URL}/{sub_token}")
    
    # تنظیم صریح لینک ساب به فرمت Base64 طبق درخواست
    sub_b64 = created_u.get("sub_b64_url") or f"{sub_raw_url}/b64"

    await database.save_account(
        telegram_id=0,
        panel_username=panel_user,
        category="singbox",
        plan_name=f"کانفیگ رایگان Sing-box ({traffic_gb}GB)",
        sub_token=sub_token,
        sub_url=sub_b64,
        sub_b64_url=sub_b64,
        is_trial=1,
        traffic_gb=traffic_gb,
        duration_days=duration_days,
    )

    direct_configs = []
    try:
        details = await panel_api.get_user_details(panel_user)
        if details and details.get("success"):
            for c in details.get("configs", []):
                uri = c.get("uri") if isinstance(c, dict) else str(c)
                if uri and uri.startswith(("vless://", "vmess://", "trojan://", "tuic://", "hy2://")):
                    direct_configs.append(uri)
    except Exception as e:
        logger.warning(f"عدم دریافت کانفیگ مستقیم: {e}")

    caption_template = conf.get("caption", "").strip()
    if caption_template:
        caption = caption_template.replace("{traffic}", str(traffic_gb))\
                                  .replace("{duration}", str(duration_days))\
                                  .replace("{sub_url}", sub_b64)\
                                  .replace("{sub_b64}", sub_b64)\
                                  .replace("{bot}", f"@{bot_username}")\
                                  .replace("{date}", now_fa)
        if "{direct}" in caption:
            d_text = "\n\n".join([f"<code>{u}</code>" for u in direct_configs[:2]]) if direct_configs else "—"
            caption = caption.replace("{direct}", d_text)
    else:
        configs_snippet = ""
        if direct_configs:
            configs_snippet = (
                "▫️ <b>کانفیگ مستقیم (کپی با یک کلیک):</b>\n"
                f"<code>{direct_configs[0]}</code>\n\n"
            )

        caption = (
            "🎁 <b>کانفیگ هوشمند و پرسرعت MS VPN (لینک Base64)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <b>حجم ترافیک:</b> {traffic_gb} گیگابایت\n"
            f"⏳ <b>اعتبار مصرف:</b> {duration_days} روز (پس از اولین اتصال)\n"
            f"🛡 <b>پروتکل‌ها:</b> Sing-box / VLESS Reality / VMess / Trojan\n"
            f"📅 <b>تاریخ انتشار:</b> {now_fa}\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🔗 <b>لینک سابسکریپشن Base64 (ایمپورت در نرم‌افزار):</b>\n"
            f"<code>{sub_b64}</code>\n\n"
            f"{configs_snippet}"
            "💡 <i>لینک ساب فوق با استاندارد کامل Base64 بوده و در نرم‌افزارهای v2rayNG ،Sing-box ،Streisand ،V2Box و Nekobox با یک کلیک آپدیت و متصل می‌شود.</i>\n\n"
            f"🤖 <b>دریافت اشتراک‌های پرسرعت اختصاصی:</b> @{bot_username}"
        )

    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 دریافت اکانت اختصاصی در ربات", url=f"https://t.me/{bot_username}")
    kb.button(text="🔗 لینک سابسکریپشن Base64", url=sub_b64)
    kb.adjust(1, 1)

    if send_qr:
        qr_buf = _generate_qr_buffer(sub_b64)
        photo_file = BufferedInputFile(qr_buf.getvalue(), filename=f"config_{panel_user}.png")
        msg = await bot.send_photo(
            chat_id=channel_id,
            photo=photo_file,
            caption=caption,
            parse_mode="HTML",
            reply_markup=kb.as_markup(),
        )
    else:
        msg = await bot.send_message(
            chat_id=channel_id,
            text=caption,
            parse_mode="HTML",
            reply_markup=kb.as_markup(),
            disable_web_page_preview=True,
        )

    return {"success": True, "message_id": msg.message_id, "username": panel_user, "sub_url": sub_b64}


async def _post_slipnet_config(
    bot: Bot,
    channel_id: str,
    conf: Dict[str, Any],
    traffic_gb: float,
    duration_days: int,
    send_qr: bool,
    now_fa: str,
    bot_username: str,
) -> Dict[str, Any]:
    """ساخت و ارسال کانفیگ‌های تانل ضد فیلتر SlipNet (DNS / SSH / Tor)."""
    time_tag = datetime.now().strftime("%H%M")
    rand_suffix = secrets.token_hex(2)
    panel_user = f"ch_dns_{time_tag}_{rand_suffix}"
    panel_pass = f"Dns{secrets.token_hex(3)}"
    dnstt_dom = await database.get_setting("dnstt_domain", settings.DNSTT_DOMAIN)

    res = await panel_api.create_l2tp_user(
        username=panel_user,
        password=panel_pass,
        traffic_limit_gb=traffic_gb,
        validity_days=duration_days,
    )
    if not res.get("success"):
        return {"success": False, "error": f"خطا در ایجاد اکانت SlipNet: {api_error_text(res)}"}

    await database.save_account(
        telegram_id=0,
        panel_username=panel_user,
        panel_password=panel_pass,
        category="dnstt",
        plan_name=f"کانفیگ رایگان SlipNet ({traffic_gb}GB)",
        server_info=dnstt_dom,
        is_trial=1,
        traffic_gb=traffic_gb,
        duration_days=duration_days,
    )

    all_uris = await panel_api.get_all_dns_slipnet_uris(username=panel_user, password=panel_pass)
    
    primary_uri = ""
    lines_uris = []
    txt_content_lines = [
        f"=== SlipNet Configs - MS VPN ===",
        f"Username: {panel_user}",
        f"Password: {panel_pass}",
        f"Created: {now_fa}",
        f"Traffic: {traffic_gb} GB",
        "================================",
        "",
    ]

    for k, item in all_uris.items():
        label = item.get("label", k)
        uri = item.get("uri", "")
        if not primary_uri:
            primary_uri = uri
        lines_uris.append(f"▫️ <b>{label}:</b>\n<code>{uri}</code>")
        txt_content_lines.append(f"[{label}]\n{uri}\n")

    uris_snippet = "\n\n".join(lines_uris[:3]) if lines_uris else f"<code>{primary_uri}</code>"

    caption = (
        "🌐 <b>کانفیگ‌های ضد فیلتر SlipNet (DNS Tunnel / SlowDNS / Tor)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>حجم ترافیک:</b> {traffic_gb} گیگابایت\n"
        f"⏳ <b>اعتبار مصرف:</b> {duration_days} روز\n"
        f"🛡 <b>مخصوص شرایط:</b> اینترنت ملی، فیلترینگ شدید و بدون نیاز به سرور واسط\n"
        f"📅 <b>تاریخ انتشار:</b> {now_fa}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📱 <b>کانفیگ‌های آماده SlipNet (کپی با یک کلیک):</b>\n\n"
        f"{uris_snippet}\n\n"
        "💡 <i>کافیست کانفیگ‌های بالا را در نرم‌افزار <b>SlipNet</b> ایمپورت کرده و بدون محدودیت متصل شوید.</i>\n\n"
        f"🤖 <b>دریافت اکانت‌های اختصاصی نامحدود:</b> @{bot_username}"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 دریافت اکانت اختصاصی در ربات", url=f"https://t.me/{bot_username}")
    if primary_uri:
        kb.button(text="📥 اتصال مستقیم SlipNet", url=primary_uri)
    kb.adjust(1, 1)

    if send_qr and primary_uri:
        qr_buf = _generate_qr_buffer(primary_uri)
        photo_file = BufferedInputFile(qr_buf.getvalue(), filename=f"slipnet_{panel_user}.png")
        msg = await bot.send_photo(
            chat_id=channel_id,
            photo=photo_file,
            caption=caption,
            parse_mode="HTML",
            reply_markup=kb.as_markup(),
        )
    else:
        msg = await bot.send_message(
            chat_id=channel_id,
            text=caption,
            parse_mode="HTML",
            reply_markup=kb.as_markup(),
            disable_web_page_preview=True,
        )

    # ارسال فایل جامع .txt کانفیگ‌های SlipNet به کانال
    try:
        txt_buf = io.BytesIO("\n".join(txt_content_lines).encode("utf-8"))
        doc_file = BufferedInputFile(txt_buf.getvalue(), filename=f"SlipNet_Configs_{panel_user}.txt")
        await bot.send_document(
            chat_id=channel_id,
            document=doc_file,
            caption=f"📁 فایل کامل کلیه کانفیگ‌های SlipNet برای اکانت <code>{panel_user}</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"ارسال فایل متنی SlipNet با خطا مواجه شد: {e}")

    return {"success": True, "message_id": msg.message_id, "username": panel_user, "primary_uri": primary_uri}


async def _post_system_l2tp_config(
    bot: Bot,
    channel_id: str,
    conf: Dict[str, Any],
    traffic_gb: float,
    duration_days: int,
    send_qr: bool,
    now_fa: str,
    bot_username: str,
) -> Dict[str, Any]:
    """ساخت و ارسال اکانت پروتکل‌های استاندارد (Cisco AnyConnect / OpenVPN / L2TP / IKEv2 / SSTP)."""
    time_tag = datetime.now().strftime("%H%M")
    rand_suffix = secrets.token_hex(2)
    panel_user = f"ch_sys_{time_tag}_{rand_suffix}"
    panel_pass = f"Ms{secrets.token_hex(3)}"
    srv_ip = await database.get_setting("server_ip", settings.SERVER_IP)
    psk = await database.get_setting("ipsec_psk", settings.IPSEC_PSK)

    res = await panel_api.create_l2tp_user(
        username=panel_user,
        password=panel_pass,
        traffic_limit_gb=traffic_gb,
        validity_days=duration_days,
    )
    if not res.get("success"):
        return {"success": False, "error": f"خطا در ایجاد اکانت سیستمی: {api_error_text(res)}"}

    await database.save_account(
        telegram_id=0,
        panel_username=panel_user,
        panel_password=panel_pass,
        category="system_l2tp",
        plan_name=f"اکانت رایگان سیستمی ({traffic_gb}GB)",
        server_info=srv_ip,
        is_trial=1,
        traffic_gb=traffic_gb,
        duration_days=duration_days,
    )

    caption = (
        "🛡️ <b>اکانت رایگان پروتکل‌های استاندارد (Cisco / OpenVPN / L2TP / IKEv2)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>حجم ترافیک:</b> {traffic_gb} گیگابایت\n"
        f"⏳ <b>اعتبار مصرف:</b> {duration_days} روز\n"
        f"📅 <b>تاریخ انتشار:</b> {now_fa}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🔑 <b>مشخصات اتصال مستقیم به سرور:</b>\n"
        f"▫️ <b>آدرس سرور (Server):</b> <code>{srv_ip}</code>\n"
        f"▫️ <b>نام کاربری (Username):</b> <code>{panel_user}</code>\n"
        f"▫️ <b>رمز عبور (Password):</b> <code>{panel_pass}</code>\n"
        f"▫️ <b>کلید امنیتی (IPsec PSK):</b> <code>{psk}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📱 <b>پروتکل‌های پشتیبانی‌شده:</b>\n"
        "▫️ سیسکو <b>Cisco AnyConnect</b> (با سرور و یوزر/پسورد فوق)\n"
        "▫️ کانکشن مستقیم سیستمی <b>L2TP / IPsec</b> در تنظیمات گوشی\n"
        "▫️ پروتکل‌های <b>IKEv2</b> و <b>SSTP</b>\n"
        "▫️ نرم‌افزار رسمی <b>OpenVPN</b>\n\n"
        f"🤖 <b>دریافت اشتراک‌های پرسرعت اختصاصی:</b> @{bot_username}"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 دریافت اکانت اختصاصی در ربات", url=f"https://t.me/{bot_username}")
    kb.adjust(1)

    msg = await bot.send_message(
        chat_id=channel_id,
        text=caption,
        parse_mode="HTML",
        reply_markup=kb.as_markup(),
        disable_web_page_preview=True,
    )

    # ارسال فایل اوپن‌وی‌پی‌ان (.ovpn) در صورت در دسترس بودن کانفیگ
    try:
        ovpn_data = get_ovpn_content(srv_ip, panel_user, panel_pass)
        if ovpn_data and "client" in ovpn_data:
            ovpn_buf = io.BytesIO(ovpn_data.encode("utf-8"))
            ovpn_file = BufferedInputFile(ovpn_buf.getvalue(), filename=f"MS_VPN_{panel_user}.ovpn")
            await bot.send_document(
                chat_id=channel_id,
                document=ovpn_file,
                caption=f"📥 فایل آماده کانکشن OpenVPN برای اکانت <code>{panel_user}</code>",
                parse_mode="HTML",
            )
    except Exception as e:
        logger.warning(f"ارسال فایل .ovpn با خطا روبرو شد: {e}")

    return {"success": True, "message_id": msg.message_id, "username": panel_user}


async def _post_multi_package(
    bot: Bot,
    channel_id: str,
    conf: Dict[str, Any],
    traffic_gb: float,
    duration_days: int,
    send_qr: bool,
    now_fa: str,
    bot_username: str,
) -> Dict[str, Any]:
    """ارسال پکیج جامع شامل Sing-box هوشمند (Base64) + تانل SlipNet + پروتکل استاندارد."""
    # ۱. ارسال کانفیگ هوشمند Sing-box
    res_sb = await _post_singbox_config(bot, channel_id, conf, traffic_gb, duration_days, send_qr, now_fa, bot_username)
    # ۲. ارسال کانفیگ تانل SlipNet
    res_dns = await _post_slipnet_config(bot, channel_id, conf, traffic_gb, duration_days, False, now_fa, bot_username)
    # ۳. ارسال پروتکل استاندارد سیستمی
    res_sys = await _post_system_l2tp_config(bot, channel_id, conf, traffic_gb, duration_days, False, now_fa, bot_username)

    return {
        "success": True,
        "singbox": res_sb,
        "slipnet": res_dns,
        "system": res_sys,
    }


async def create_and_post_channel_config(bot: Bot, force: bool = False) -> Dict[str, Any]:
    """ساخت کانفیگ جدید در پنل بر اساس پروتکل انتخابی و ارسال مستقیم به کانال مقصد."""
    conf = await database.get_auto_channel_settings()

    if not force and not conf.get("is_enabled"):
        return {"success": False, "error": "ارسال خودکار کانفیگ غیرفعال است."}

    channel_id = conf.get("channel_id")
    if not channel_id:
        return {"success": False, "error": "کانال مقصد تنظیم نشده است."}

    is_admin, admin_status_msg = await check_bot_channel_admin(bot, channel_id)
    if not is_admin:
        logger.warning(f"عدم دسترسی ربات در کانال مقصد {channel_id}: {admin_status_msg}")
        return {"success": False, "error": admin_status_msg}

    traffic_gb = conf.get("traffic_gb", 1.0)
    duration_days = conf.get("duration_days", 1)
    send_qr = conf.get("send_qr", True)
    protocol = conf.get("protocol", "singbox").lower()
    now_fa = datetime.now().strftime("%Y/%m/%d - %H:%M")
    bot_username = settings.BOT_USERNAME.lstrip("@")

    logger.info(f"شروع ارسال کانفیگ به کانال {channel_id} با پروتکل {protocol}")

    if protocol == "slipnet":
        return await _post_slipnet_config(bot, channel_id, conf, traffic_gb, duration_days, send_qr, now_fa, bot_username)
    elif protocol == "system_l2tp":
        return await _post_system_l2tp_config(bot, channel_id, conf, traffic_gb, duration_days, send_qr, now_fa, bot_username)
    elif protocol in ("all", "multi"):
        return await _post_multi_package(bot, channel_id, conf, traffic_gb, duration_days, send_qr, now_fa, bot_username)
    else:
        # حالت پیش‌فرض: Sing-box هوشمند با سابسکریپشن Base64
        return await _post_singbox_config(bot, channel_id, conf, traffic_gb, duration_days, send_qr, now_fa, bot_username)


async def check_and_run_scheduled_channel_posts(bot: Bot) -> None:
    """بررسی زمان‌بندی و ارسال خودکار کانفیگ در دقایق مقرر."""
    try:
        conf = await database.get_auto_channel_settings()
        if not conf.get("is_enabled"):
            return

        channel_id = conf.get("channel_id")
        if not channel_id:
            return

        now = datetime.now()
        weekday_idx = now.weekday()
        current_day_code = DAY_MAP.get(weekday_idx, "")
        days_list = conf.get("days_list", [])

        if current_day_code not in days_list:
            return

        current_time_str = now.strftime("%H:%M")
        times_list = conf.get("times_list", [])

        if current_time_str not in times_list:
            return

        time_key = f"{now.strftime('%Y-%m-%d')}_{current_time_str}"
        if conf.get("last_sent") == time_key:
            return

        logger.info(f"⏰ زمان ارسال خودکار کانفیگ فرا رسید ({current_time_str} - روز {current_day_code}).")
        res = await create_and_post_channel_config(bot, force=True)
        if res.get("success"):
            await database.set_auto_channel_last_sent(time_key)
            logger.info(f"✅ ارسال زمان‌بندی‌شده کانفیگ به کانال {channel_id} با موفقیت انجام شد.")
        else:
            logger.warning(f"⚠️ ارسال زمان‌بندی‌شده به کانال ناموفق بود: {res.get('error')}")
    except Exception as e:
        logger.error(f"خطا در رانر زمان‌بندی ارسال به کانال: {e}")
