"""توابع اتصال به API پنل مدیریت پروتکل‌های MHPanel.

تمامی عملیات‌های ساخت کاربر، دریافت کانفیگ‌ها، لینک‌های سابسکریپشن و استعلام حجم
مستقیماً با هسته Sing-box، پروتکل‌های سیستمی L2TP/IKEv2 و سامانه ساب پنل MHPanel ارتباط برقرار می‌کنند.
"""
from typing import Dict, Any, Optional, List
import re
from datetime import datetime, timedelta

from api import client


def clean_username(uname: str) -> str:
    """پاکسازی نام کاربری مطابق با قوانین پنل MHPanel (حروف انگلیسی، ارقام، _ و -)."""
    clean = re.sub(r'[^a-zA-Z0-9_\-]', '', uname).lower()
    if len(clean) < 3:
        clean = f"ms_{clean}"
    return clean[:32]


# ──────────────────────────────────────────────────────────────
#  هسته Sing-box (Reality, VMess, Trojan, Hysteria 2, TUIC)
# ──────────────────────────────────────────────────────────────

async def get_all_users() -> Dict[str, Any]:
    """دریافت لیست تمام کاربران سینگ‌باکس از پنل."""
    return await client.get("singbox/users")


async def get_user_details(username: str) -> Dict[str, Any]:
    """دریافت جزئیات کامل کاربر به همراه کانفیگ‌ها و لینک سابسکریپشن."""
    safe_user = clean_username(username)
    return await client.get(f"singbox/user/{safe_user}/links")


async def create_user(
    username: str,
    traffic_limit_gb: float = 30.0,
    validity_days: int = 30,
    expiry_type: str = "on_first_use",
    category: str = "MS_VPN",
    inbounds: Optional[List[str]] = None,
    note: str = "",
) -> Dict[str, Any]:
    """ساخت کاربر جدید در هسته Sing-box پنل MHPanel با قابلیت انتخاب اینباندها."""
    safe_user = clean_username(username)
    payload = {
        "username": safe_user,
        "traffic_limit_gb": float(traffic_limit_gb),
        "validity_days": int(validity_days),
        "expiry_type": expiry_type,
        "category": category,
        "note": note,
    }
    if inbounds is not None:
        payload["inbounds"] = inbounds
    return await client.post("singbox/user/add", data=payload)


async def toggle_user(username: str) -> Dict[str, Any]:
    safe_user = clean_username(username)
    return await client.post(f"singbox/user/{safe_user}/toggle", data={})


async def reset_user_traffic(username: str) -> Dict[str, Any]:
    safe_user = clean_username(username)
    return await client.post(f"singbox/user/{safe_user}/reset-traffic", data={})


async def delete_user(username: str) -> Dict[str, Any]:
    safe_user = clean_username(username)
    return await client.post(f"singbox/user/{safe_user}/delete", data={})


async def edit_user(username: str, **kwargs) -> Dict[str, Any]:
    safe_user = clean_username(username)
    return await client.post(f"singbox/user/{safe_user}/edit", data=kwargs)


# ──────────────────────────────────────────────────────────────
#  پروتکل‌های سیستمی و استاندارد (L2TP / IKEv2 / RADIUS)
# ──────────────────────────────────────────────────────────────

async def get_l2tp_users() -> Dict[str, Any]:
    """دریافت کاربران L2TP/IPsec از پنل."""
    return await client.get("l2tp/users")


async def create_l2tp_user(
    username: str,
    password: str,
    traffic_limit_gb: float = 30.0,
    validity_days: int = 30,
) -> Dict[str, Any]:
    """ساخت کاربر پروتکل‌های سیستمی (L2TP / IKEv2 / IPsec / RADIUS) در MHPanel."""
    safe_user = clean_username(username)
    exp_date = (datetime.now() + timedelta(days=int(validity_days))).strftime("%Y-%m-%d")
    payload = {
        "username": safe_user,
        "password": str(password),
        "limit_gb": float(traffic_limit_gb),
        "expire_date": exp_date,
    }
    res = await client.post("l2tp/users", data=payload)
    if res.get("success") or res.get("status_code") == 200:
        return {"success": True, "username": safe_user, "password": password, "expire_date": exp_date}
    return res


async def delete_l2tp_user(username: str) -> Dict[str, Any]:
    safe_user = clean_username(username)
    return await client.delete(f"l2tp/users/{safe_user}")


# ──────────────────────────────────────────────────────────────
#  پروتکل اختصاصی وایرگارد (WireGuard)
# ──────────────────────────────────────────────────────────────

async def get_wireguard_peers() -> List[Dict[str, Any]]:
    """دریافت لیست پیرها و کلاینت‌های وایرگارد از پنل."""
    res = await client.get("wireguard/peers")
    if isinstance(res, list):
        return res
    if isinstance(res, dict) and "data" in res and isinstance(res["data"], list):
        return res["data"]
    return []


async def create_wireguard_account(
    name: str,
    traffic_limit_gb: float = 30.0,
    validity_days: int = 30,
    simultaneous_use: int = 1,
) -> Dict[str, Any]:
    """ساخت کلاینت جدید وایرگارد در پنل MHPanel و دریافت کانفیگ اختصاصی."""
    safe_name = clean_username(name)
    payload = {
        "name": safe_name,
        "limit_gb": float(traffic_limit_gb) if traffic_limit_gb > 0 else None,
        "expire_days": int(validity_days) if validity_days > 0 else None,
        "start_on_first_connect": False,
        "simultaneous_use": simultaneous_use,
    }
    return await client.post("wireguard/client", data=payload)


async def delete_wireguard_account(public_key: str) -> Dict[str, Any]:
    """حذف کلاینت وایرگارد بر اساس کلید عمومی."""
    return await client.post("wireguard/client/delete", data={"public_key": public_key})


# ──────────────────────────────────────────────────────────────
#  سرویس تونل گوگل اسکریپت و کلودفلر (GAS / Workers)
# ──────────────────────────────────────────────────────────────

async def get_gas_status() -> Dict[str, Any]:
    """دریافت وضعیت و اکانت‌های سرویس Google Apps Script."""
    return await client.get("google_script/status")


async def deploy_gas_wizard(
    name: str,
    email: str,
    google_token: str = "",
    cf_token: str = "",
    cf_account_id: str = "",
    mode: str = "google_and_cloudflare",
) -> Dict[str, Any]:
    """استقرار خودکار و ساخت ورکر گوگل اسکریپت یا کلودفلر از طریق ویزارد پنل."""
    safe_name = clean_username(name)
    payload = {
        "mode": mode,
        "name": safe_name,
        "email": email or f"{safe_name}@gmail.com",
        "access_token": google_token,
        "cf_api_token": cf_token,
        "cf_account_id": cf_account_id,
        "cf_worker_name": f"worker-{safe_name[:14]}",
        "auto_deploy": True,
        "set_active": True,
    }
    return await client.post("google_script/accounts/wizard", data=payload)


async def get_gas_client_configs(account_id: str = "", use_cloudflare: bool = True) -> Dict[str, Any]:
    """دریافت پروفایل‌های کلاینت (Goose, Sing-box, MHRV) برای یک استقرار GAS."""
    params = {}
    if account_id:
        params["account_id"] = account_id
    if use_cloudflare:
        params["use_cloudflare"] = "1"
    return await client.get("google_script/client-configs", params=params)


# ──────────────────────────────────────────────────────────────
#  تانل‌های DNS، کلاینت SlipNet و پروتکل Tor
# ──────────────────────────────────────────────────────────────

async def get_slipnet_config(
    proto: str = "dnstt",
    username: str = "",
    password: str = "",
    domain: str = "",
) -> Dict[str, Any]:
    """دریافت لینک استاندارد slipnet:// برای پروتکل‌های DNS، DoH و Tor از پنل."""
    params = {
        "proto": proto,
        "user": username,
        "pass": password,
    }
    if domain:
        params["domain"] = domain
    return await client.get("dns/slipnet_config", params=params)


async def get_all_dns_slipnet_uris(username: str, password: str) -> Dict[str, Any]:
    """تولید یکپارچه لینک‌های اتصال SlipNet برای تمامی پروتکل‌های DNS و Tor."""
    protocols = [
        ("dnstt", "تانل ضد فیلتر DNSTT (SlowDNS)"),
        ("vaydns", "تانل پرسرعت VayDNS"),
        ("slipstream", "تانل کوئیک Slipstream QUIC"),
        ("masterdnsvpn", "تانل چانک MasterDNS"),
        ("noizdns", "تانل آنتی‌فیلتر NoizDNS (SayeDNS)"),
        ("doh", "تانل امن DoH (DNS-over-HTTPS)"),
        ("tor", "پل ضد سانسور Tor (obfs4 Bridge)"),
    ]
    results = {}
    for proto_key, label in protocols:
        try:
            res = await get_slipnet_config(proto=proto_key, username=username, password=password)
            if res.get("success") and res.get("uri"):
                results[proto_key] = {
                    "label": label,
                    "uri": res.get("uri"),
                    "domain": res.get("domain", ""),
                }
        except Exception:
            pass
    return results


async def reset_singbox_uuid(username: str, new_uuid: str) -> Dict[str, Any]:
    """تغییر شناسه UUID کاربر سینگ‌باکس جهت قطع دسترسی سایر افراد."""
    safe_user = clean_username(username)
    return await client.post(f"singbox/user/{safe_user}/edit", data={"uuid": new_uuid})


# ──────────────────────────────────────────────────────────────
#  وضعیت سیستم و سرور
# ──────────────────────────────────────────────────────────────

async def get_system_status() -> Dict[str, Any]:
    """استعلام وضعیت سرور و مصرف منابع و ترافیک از پنل."""
    from config import settings
    return await client.get(f"public/status?key={settings.PANEL_API_KEY}")
