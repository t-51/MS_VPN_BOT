"""مدیریت جامع اکانت‌های تستی (صدور از تمامی پروتکل‌ها و پاکسازی خودکار پس از انقضا).

این ماژول وظایف زیر را بر عهده دارد:
۱. صدور اکانت تستی برای تمامی حالت‌ها: Sing-box/V2Ray، سیستمی (Cisco/L2TP/OpenVPN)، وایرگارد و تانل DNS (SlipNet).
۲. پکیج جامع تستی (صدور همزمان کلیه پروتکل‌ها).
۳. استعلام زنده وضعیت انقضا (زمانی یا ترافیکی) از پنل MHPanel.
۴. حذف خودکار اکانت‌های تستی منقضی شده از داخل پنل جهت جلوگیری از پر شدن فضا و منابع سرور.
"""
import io
import logging
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

import qrcode
from aiogram import Bot
from aiogram.types import BufferedInputFile

from api import panel_api
from config import settings
from db import database
from utils.cert_manager import get_ovpn_content
from utils.helpers import to_fa, api_error_text

logger = logging.getLogger("MS_VPN_BOT.trial_manager")


async def issue_trial_singbox(telegram_id: int, trial_gb: float, trial_days: int, note_suffix: str = "") -> Dict[str, Any]:
    """ساخت اکانت تستی هسته Sing-box (Reality / V2Ray / VMess / TUIC / Hysteria)."""
    rand_suffix = secrets.token_hex(2)
    panel_user = f"ms_t_sb_{telegram_id}_{rand_suffix}"

    res = await panel_api.create_user(
        username=panel_user,
        traffic_limit_gb=trial_gb,
        validity_days=trial_days,
        expiry_type="on_first_use",
        category="MS_VPN_Trial",
        note=f"Trial SB TG: {telegram_id} {note_suffix}".strip(),
    )
    if not res.get("success"):
        return {"success": False, "error": api_error_text(res)}

    created_u = res.get("user", {})
    sub_token = created_u.get("sub_token", "")
    sub_url = created_u.get("sub_url", f"{settings.PANEL_SUB_URL}/{sub_token}")
    sub_b64 = created_u.get("sub_b64_url", f"{sub_url}/b64")

    acc_id = await database.save_account(
        telegram_id=telegram_id,
        panel_username=panel_user,
        category="singbox",
        plan_name="اکانت تستی Sing-box و V2Ray",
        sub_token=sub_token,
        sub_url=sub_url,
        sub_b64_url=sub_b64,
        is_trial=1,
        traffic_gb=trial_gb,
        duration_days=trial_days,
    )

    return {
        "success": True,
        "account_id": acc_id,
        "category": "singbox",
        "username": panel_user,
        "sub_url": sub_url,
        "sub_b64_url": sub_b64,
    }


async def issue_trial_system_l2tp(telegram_id: int, trial_gb: float, trial_days: int) -> Dict[str, Any]:
    """ساخت اکانت تستی پروتکل‌های سیستمی (Cisco AnyConnect / OpenVPN / L2TP / IKEv2 / SSH)."""
    rand_suffix = secrets.token_hex(2)
    panel_user = f"ms_t_sys_{telegram_id}_{rand_suffix}"
    panel_pass = f"Ms{secrets.token_hex(3)}"
    srv_ip = await database.get_setting("server_ip", settings.SERVER_IP)
    psk = await database.get_setting("ipsec_psk", settings.IPSEC_PSK)

    res = await panel_api.create_l2tp_user(
        username=panel_user,
        password=panel_pass,
        traffic_limit_gb=trial_gb,
        validity_days=trial_days,
    )
    if not res.get("success"):
        return {"success": False, "error": api_error_text(res)}

    acc_id = await database.save_account(
        telegram_id=telegram_id,
        panel_username=panel_user,
        panel_password=panel_pass,
        category="system_l2tp",
        plan_name="اکانت تستی سیستمی (Cisco/L2TP)",
        server_info=srv_ip,
        is_trial=1,
        traffic_gb=trial_gb,
        duration_days=trial_days,
    )

    return {
        "success": True,
        "account_id": acc_id,
        "category": "system_l2tp",
        "username": panel_user,
        "password": panel_pass,
        "server_ip": srv_ip,
        "psk": psk,
    }


async def issue_trial_wireguard(telegram_id: int, trial_gb: float, trial_days: int) -> Dict[str, Any]:
    """ساخت اکانت تستی اختصاصی وایرگارد (WireGuard)."""
    rand_suffix = secrets.token_hex(2)
    panel_user = f"ms_t_wg_{telegram_id}_{rand_suffix}"

    res = await panel_api.create_wireguard_account(
        name=panel_user,
        traffic_limit_gb=trial_gb,
        validity_days=trial_days,
    )
    if not res.get("success"):
        return {"success": False, "error": api_error_text(res)}

    client_conf = res.get("config", "")
    client_ip = res.get("ip", "")
    pubkey = res.get("public_key", "")
    sub_token = res.get("sub_token", "")

    acc_id = await database.save_account(
        telegram_id=telegram_id,
        panel_username=panel_user,
        panel_password=pubkey,
        category="wireguard",
        plan_name="اکانت تستی وایرگارد (WireGuard)",
        server_info=client_conf,
        sub_token=sub_token,
        is_trial=1,
        traffic_gb=trial_gb,
        duration_days=trial_days,
    )

    return {
        "success": True,
        "account_id": acc_id,
        "category": "wireguard",
        "username": panel_user,
        "public_key": pubkey,
        "client_ip": client_ip,
        "config": client_conf,
    }


async def issue_trial_dnstt(telegram_id: int, trial_gb: float, trial_days: int) -> Dict[str, Any]:
    """ساخت اکانت تستی تانل ضد فیلتر DNS (SlowDNS / SlipNet)."""
    rand_suffix = secrets.token_hex(2)
    panel_user = f"ms_t_dns_{telegram_id}_{rand_suffix}"
    panel_pass = f"Dns{secrets.token_hex(3)}"
    dnstt_dom = await database.get_setting("dnstt_domain", settings.DNSTT_DOMAIN)
    dnstt_pub = await database.get_setting("dnstt_pubkey", settings.DNSTT_PUBKEY)

    res = await panel_api.create_l2tp_user(
        username=panel_user,
        password=panel_pass,
        traffic_limit_gb=trial_gb,
        validity_days=trial_days,
    )
    if not res.get("success"):
        return {"success": False, "error": api_error_text(res)}

    acc_id = await database.save_account(
        telegram_id=telegram_id,
        panel_username=panel_user,
        panel_password=panel_pass,
        category="dnstt",
        plan_name="اکانت تستی تانل DNS (SlipNet)",
        server_info=dnstt_dom,
        is_trial=1,
        traffic_gb=trial_gb,
        duration_days=trial_days,
    )

    all_uris = await panel_api.get_all_dns_slipnet_uris(username=panel_user, password=panel_pass)

    return {
        "success": True,
        "account_id": acc_id,
        "category": "dnstt",
        "username": panel_user,
        "password": panel_pass,
        "domain": dnstt_dom,
        "pubkey": dnstt_pub,
        "uris": all_uris,
    }


async def issue_trial_by_mode(telegram_id: int, mode: str, trial_gb: float, trial_days: int) -> Dict[str, Any]:
    """صدور اکانت تستی بر اساس حالت انتخابی (یا صدور یکپارچه تمام حالت‌ها)."""
    if mode == "singbox":
        return await issue_trial_singbox(telegram_id, trial_gb, trial_days)
    elif mode == "system_l2tp":
        return await issue_trial_system_l2tp(telegram_id, trial_gb, trial_days)
    elif mode == "wireguard":
        return await issue_trial_wireguard(telegram_id, trial_gb, trial_days)
    elif mode == "dnstt":
        return await issue_trial_dnstt(telegram_id, trial_gb, trial_days)
    elif mode == "all":
        # صدور پکیج کامل از تمام ۴ حالت
        sb_res = await issue_trial_singbox(telegram_id, trial_gb, trial_days, note_suffix="All-in-One")
        sys_res = await issue_trial_system_l2tp(telegram_id, trial_gb, trial_days)
        wg_res = await issue_trial_wireguard(telegram_id, trial_gb, trial_days)
        dns_res = await issue_trial_dnstt(telegram_id, trial_gb, trial_days)

        results = {
            "success": any([sb_res.get("success"), sys_res.get("success"), wg_res.get("success"), dns_res.get("success")]),
            "category": "all",
            "singbox": sb_res,
            "system_l2tp": sys_res,
            "wireguard": wg_res,
            "dnstt": dns_res,
        }
        return results
    else:
        return {"success": False, "error": f"حالت تستی نامعتبر: {mode}"}


async def delete_trial_from_panel(account: Dict[str, Any]) -> bool:
    """حذف واقعی اکانت تستی از پنل MHPanel متناسب با پروتکل آن."""
    cat = account.get("category", "singbox")
    uname = account.get("panel_username", "")
    try:
        if cat in ("singbox", "v2ray", "reality"):
            r = await panel_api.delete_user(uname)
            return r.get("success", False) or r.get("status_code") == 404
        elif cat in ("system_l2tp", "dnstt"):
            r = await panel_api.delete_l2tp_user(uname)
            return r.get("success", False)
        elif cat == "wireguard":
            pubkey = account.get("panel_password", "")
            r = await panel_api.delete_wireguard_account(pubkey)
            return r.get("success", False)
    except Exception as e:
        logger.error(f"خطا در حذف اکانت {uname} ({cat}) از پنل: {e}")
        return False
    return False


async def check_and_cleanup_expired_trials(bot: Optional[Bot] = None) -> int:
    """بررسی وضعیت کلیه اکانت‌های تستی و حذف موارد منقضی شده از داخل پنل و دیتابیس.
    
    مواردی که حذف می‌شوند:
    ۱. اکانت‌های سینگ‌باکس با is_expired یا is_quota_exceeded یا حذف شده در هسته.
    ۲. اکانت‌های سیستمی و تانل DNS که تاریخ انقضای آن‌ها گذشته یا حجم را تمام کرده‌اند.
    ۳. اکانت‌های وایرگارد که منقضی یا حجم تمام کرده‌اند.
    ۴. هر اکانت تستی که از تاریخ ایجاد آن در بات بیش از (مدت اعتبار + ۲ روز) سپری شده باشد.
    """
    trial_accounts = await database.get_all_trial_accounts()
    if not trial_accounts:
        return 0

    today_str = datetime.now().strftime("%Y-%m-%d")
    now_dt = datetime.now()
    deleted_count = 0

    # بارگذاری پیش‌دستانه کاربران جهت بهینه‌سازی تماس با پنل
    try:
        l2tp_data = await panel_api.get_l2tp_users()
        l2tp_users = l2tp_data.get("users", {}) if isinstance(l2tp_data, dict) else {}
    except Exception:
        l2tp_users = {}

    try:
        wg_peers = await panel_api.get_wireguard_peers()
    except Exception:
        wg_peers = []

    for acc in trial_accounts:
        acc_id = acc.get("id")
        uname = acc.get("panel_username")
        cat = acc.get("category", "singbox")
        telegram_id = acc.get("telegram_id")
        duration_days = int(acc.get("duration_days") or 1)
        created_str = str(acc.get("created_at") or "")

        # بررسی زمان سپری شده از ثبت در دیتابیس
        created_dt = None
        if created_str:
            try:
                # پشتیبانی از فرمت‌های SQLite
                clean_ts = created_str.replace("T", " ")
                created_dt = datetime.strptime(clean_ts.split(".")[0], "%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

        time_hard_expired = False
        if created_dt:
            # اگر از زمان ساخت اکانت بیش از مدت روز + ۲ روز گذشته باشد، منقضی در نظر گرفته می‌شود
            if (now_dt - created_dt).total_seconds() > ((duration_days + 2) * 86400):
                time_hard_expired = True

        is_expired = False
        reason = ""

        if time_hard_expired:
            is_expired = True
            reason = "اتمام زمان مجاز نگهداری تست"
        elif cat in ("singbox", "v2ray", "reality"):
            try:
                res = await panel_api.get_user_details(uname)
                if not res.get("success"):
                    # کاربر در پنل وجود ندارد یا قبلاً پاک شده
                    is_expired = True
                    reason = "عدم وجود کاربر در هسته پنل"
                else:
                    u_data = res.get("user", {})
                    if u_data.get("is_expired"):
                        is_expired = True
                        reason = "پایان مدت اعتبار زمانی"
                    elif u_data.get("is_quota_exceeded"):
                        is_expired = True
                        reason = "مصرف کل حجم ترافیک هدیه"
                    elif u_data.get("expire_date") and not u_data.get("is_waiting_first_use", False):
                        exp_d = u_data.get("expire_date", "")
                        if exp_d and exp_d < today_str:
                            is_expired = True
                            reason = "انقضای تاریخ اشتراک"
            except Exception as e:
                logger.warning(f"عدم امکان استعلام سینگ‌باکس برای {uname}: {e}")

        elif cat in ("system_l2tp", "dnstt"):
            u_info = l2tp_users.get(uname)
            if not u_info:
                # در پنل موجود نیست
                is_expired = True
                reason = "عدم وجود اکانت در سرور سیستمی"
            else:
                exp_date = u_info.get("expire_date")
                limit_gb = float(u_info.get("limit_gb") or 0.0)
                used_bytes = int(u_info.get("rx", 0)) + int(u_info.get("tx", 0))
                if exp_date and exp_date < today_str:
                    is_expired = True
                    reason = "پایان مدت زمان سیستمی"
                elif limit_gb > 0 and used_bytes >= (limit_gb * 1024**3):
                    is_expired = True
                    reason = "اتمام ترافیک هدیه سیستمی"
                elif created_dt and (now_dt - created_dt).total_seconds() > (duration_days * 86400):
                    is_expired = True
                    reason = "سپری شدن مدت اعتبار تست"

        elif cat == "wireguard":
            pubkey = acc.get("panel_password")
            matched_peer = None
            for p in wg_peers:
                if (pubkey and p.get("public_key") == pubkey) or (p.get("name") == uname):
                    matched_peer = p
                    break

            if not matched_peer:
                is_expired = True
                reason = "عدم وجود کلاینت وایرگارد در پنل"
            else:
                if matched_peer.get("is_date_expired") or matched_peer.get("is_traffic_expired") or matched_peer.get("status") == "expired":
                    is_expired = True
                    reason = "پایان اعتبار یا حجم وایرگارد"
                elif matched_peer.get("expire_date") and matched_peer.get("expire_date") < today_str:
                    is_expired = True
                    reason = "انقضای تاریخ وایرگارد"
                elif created_dt and (now_dt - created_dt).total_seconds() > (duration_days * 86400):
                    is_expired = True
                    reason = "سپری شدن مدت اعتبار تست"

        # اگر منقضی شده، از پنل و دیتابیس پاک شود
        if is_expired:
            logger.info(f"🗑 در حال حذف اکانت تستی منقضی شده: {uname} ({cat}) - علت: {reason}")
            await delete_trial_from_panel(acc)
            await database.delete_account(acc_id)
            deleted_count += 1

            # اطلاع‌رسانی محترمانه به کاربر
            if bot and telegram_id:
                try:
                    alert_text = (
                        "⏳ <b>مهلت استفاده از اکانت تستی شما به پایان رسید.</b>\n\n"
                        f"اکانت تستی شما (<b>{acc.get('plan_name')}</b>) به دلیل <b>{reason}</b> از پنل سرور حذف گردید.\n\n"
                        "🛒 جهت خرید اشتراک دائمی و پرسرعت، از منوی اصلی دکمه <b>«🛒 خرید اشتراک»</b> را لمس فرمایید."
                    )
                    await bot.send_message(telegram_id, alert_text, parse_mode="HTML")
                except Exception:
                    pass

    return deleted_count
