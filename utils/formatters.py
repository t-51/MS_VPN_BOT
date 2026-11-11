"""قالب‌بندی داده‌های MHPanel، دیتابیس محلی و گزارشات مدیریت به متن فارسی."""
import re
from typing import Any, Dict, List, Optional

from utils.helpers import to_fa, to_toman, to_days
from config import settings


# ── پروفایل ──────────────────────────────────────────────────

def format_profile(user: Dict[str, Any], accounts_count: int, ref_stats: Dict[str, Any]) -> str:
    telegram_id = user.get("telegram_id", "—")
    username = f"@{user.get('username')}" if user.get("username") else "—"
    name = user.get("first_name", "کاربر گرامی")
    balance = user.get("wallet_balance", 0)
    created_at = str(user.get("created_at", "—"))[:19]

    return (
        f"👤 <b>پروفایل کاربری {name}</b>\n\n"
        f"🆔 شناسه کاربری: <code>{to_fa(telegram_id)}</code>\n"
        f"📎 نام کاربری: <b>{username}</b>\n"
        f"💰 موجودی کیف پول: <b>{to_toman(balance)}</b>\n"
        f"📦 تعداد اشتراک‌های فعال: <b>{to_fa(accounts_count)}</b>\n"
        f"👥 تعداد زیرمجموعه‌ها: <b>{to_fa(ref_stats.get('total_referrals', 0))} نفر</b>\n"
        f"💵 درآمد از زیرمجموعه: <b>{to_toman(ref_stats.get('total_commission', 0))}</b>\n"
        f"📅 تاریخ عضویت: <i>{to_fa(created_at)}</i>"
    )


# ── اکانت‌ها ─────────────────────────────────────────────────

def format_account_item(acc: Dict[str, Any], index: int = 0) -> str:
    prefix = f"{to_fa(index)}. " if index else ""
    cat_names = {
        "singbox": "⚡ Sing-box & V2Ray",
        "system_l2tp": "🛡️ پروتکل‌های استاندارد سیستمی",
        "dnstt": "🌐 تانل ضد فیلتر DNS",
        "wireguard": "⚡ وایرگارد مدرن (WireGuard)",
        "gas": "☁️ گوگل اسکریپت (GAS / Workers)",
    }
    cat = acc.get("category", "singbox")
    cat_title = cat_names.get(cat, "سرویس")
    plan = acc.get("plan_name", "اشتراک")
    acc_type = "🎁 تستی" if acc.get("is_trial") else "💎 VIP"
    uname = acc.get("panel_username", "—")
    return f"{prefix}<b>{plan}</b> [{acc_type} | {cat_title}]\n   👤 نام کاربری: <code>{uname}</code>"


def format_accounts_list(accounts: List[Dict[str, Any]]) -> str:
    if not accounts:
        return "📭 شما هنوز هیچ اکانت فعالی ندارید.\nجهت دریافت سرویس، از بخش «🎁 اکانت تستی» یا «🛒 خرید اشتراک» اقدام فرمایید."
    lines = ["📦 <b>لیست اشتراک‌های فعال شما در MHPanel</b>\n"]
    for i, acc in enumerate(accounts, 1):
        lines.append(format_account_item(acc, i))
        lines.append("")
    lines.append("👇 جهت مشاهده جزئیات ترافیک، تاریخ انقضا و مشخصات اتصال، یکی از اشتراک‌ها را انتخاب کنید:")
    return "\n".join(lines)


def format_account_details(acc: Dict[str, Any], live_data: Optional[Dict[str, Any]] = None, server_ip: Optional[str] = None, psk: Optional[str] = None) -> str:
    server_ip = server_ip or settings.SERVER_IP
    psk = psk or settings.IPSEC_PSK
    cat = acc.get("category", "singbox")
    uname = acc.get("panel_username", "—")
    plan = acc.get("plan_name", "—")

    # 1. اگر پروتکل‌های استاندارد سیستمی (Cisco, OpenVPN, L2TP, IKEv2, SSH, SSTP) باشد:
    if cat == "system_l2tp":
        pwd = acc.get("panel_password", "—")
        return (
            "🛡️ <b>مشخصات اکانت پروتکل‌های استاندارد سیستمی</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🏷 پلن: <b>{plan}</b>\n"
            f"👤 <b>نام کاربری (Username):</b> <code>{uname}</code>\n"
            f"🔑 <b>رمز عبور (Password):</b> <code>{pwd}</code>\n"
            f"🌐 <b>آدرس سرور اصلی:</b> <code>{server_ip}</code>\n\n"
            "⚡ <b>اتصال همزمان به تمام پروتکل‌های زیر با همین اکانت:</b>\n"
            f"▫️ <b>Cisco AnyConnect:</b> سرور: <code>{server_ip}:10443</code>\n"
            f"▫️ <b>OpenVPN:</b> پورت <code>1194</code> (دانلود فایل .ovpn از دکمه زیر)\n"
            f"▫️ <b>L2TP / IPsec:</b> سرور: <code>{server_ip}</code> | کلید (PSK): <code>{psk}</code>\n"
            f"▫️ <b>IKEv2:</b> سرور: <code>{server_ip}</code>\n"
            f"▫️ <b>SSH Tunnel:</b> سرور: <code>{server_ip}</code> | پورت: <code>22</code> و <code>2053</code>\n"
            f"▫️ <b>SSTP:</b> سرور: <code>{server_ip}</code> | پورت: <code>443</code>\n\n"
            "👇 جهت دریافت فایل کانفیگ OpenVPN یا سرتیفیکیت‌ها، دکمه‌های زیر را لمس نمایید:"
        )

    # 2. اگر تانل DNS باشد:
    if cat == "dnstt":
        pwd = acc.get("panel_password", "—")
        dom = acc.get("server_info") or "t.vpn.kigaping.com"
        return (
            "🌐 <b>مشخصات اشتراک تانل ضد فیلتر DNS (SlowDNS / SlipNet)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🏷 پلن: <b>{plan}</b>\n"
            f"👤 <b>نام کاربری:</b> <code>{uname}</code>\n"
            f"🔑 <b>رمز عبور:</b> <code>{pwd}</code>\n"
            f"📡 <b>دامنه سرور DNS:</b> <code>{dom}</code>\n"
            "🔑 <b>کلید عمومی سرور:</b>\n<code>b3290012dd13fe7df78551fdfbccfdfce5d3c594522fef40bf8284e4313b3a31</code>\n\n"
            "⚡ <b>پروتکل‌های متصل:</b> VayDNS, DNSTT, Slipstream, MasterDNS, NoizDNS, DoH, Tor\n"
            "💡 این پروتکل در زمان قطعی کامل اینترنت بین‌الملل و فیلترینگ شدید از طریق پورت ۵۳ با نرم‌افزارهای SlipNet یا SlowDNS متصل می‌شود.\n\n"
            "👇 جهت دانلود فایل متنی کانفیگ‌ها، نمایش متنی یا دریافت بارکد QR، دکمه‌های زیر را لمس نمایید:"
        )

    # 3. اگر پروتکل اختصاصی وایرگارد (WireGuard) باشد:
    if cat == "wireguard":
        wg_conf = acc.get("server_info", "")
        pubkey = acc.get("panel_password", "—")
        ip_match = re.search(r"Address\s*=\s*([^\n\r/]+)", wg_conf) if wg_conf else None
        client_ip = ip_match.group(1).strip() if ip_match else "اختصاصی"
        return (
            "⚡ <b>مشخصات اشتراک اختصاصی وایرگارد (WireGuard)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🏷 پلن: <b>{plan}</b>\n"
            f"👤 نام کاربری: <code>{uname}</code>\n"
            f"🌐 آی‌پی کلاینت: <code>{client_ip}</code>\n"
            f"📶 حجم ترافیک: <b>{to_fa(acc.get('traffic_gb', 0))} گیگابایت</b>\n"
            f"⏱ مدت اعتبار: <b>{to_fa(acc.get('duration_days', 0))} روز</b>\n"
            f"🔑 کلید عمومی: <code>{pubkey[:24]}...</code>\n\n"
            "👇 جهت دانلود فایل <code>.conf</code> یا اسکن بارکد در اپلیکیشن وایرگارد، از دکمه‌های زیر استفاده فرمایید:"
        )

    # 4. اگر تونل ابری گوگل اسکریپت (GAS) باشد:
    if cat == "gas":
        dep_id = acc.get("server_info", "—")
        webapp_url = acc.get("sub_url", "")
        goose_uri = acc.get("sub_b64_url", "")
        secret = acc.get("panel_password", "—")
        return (
            "☁️ <b>مشخصات اکانت تونل ابری گوگل اسکریپت (GAS / Workers)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🏷 پلن: <b>{plan}</b>\n"
            f"👤 نام پروژه: <code>{uname}</code>\n"
            f"🔑 کلید رمز تونل: <code>{secret}</code>\n"
            f"🆔 شناسه استقرار گوگل (Deployment ID):\n<code>{dep_id}</code>\n\n"
            "🔗 <b>لینک استقرار وب‌اپ گوگل:</b>\n"
            f"<code>{webapp_url or 'سرور ابری فعال'}</code>\n\n"
            "🚀 <b>لینک اختصاصی Goose VPN:</b>\n"
            f"<code>{goose_uri or 'در بخش آموزش ملاحظه فرمایید'}</code>\n\n"
            "💡 این تونل بر بستر سرورهای رسمی گوگل با دامنه <code>script.google.com</code> اجرا شده و فیلترناپذیر است."
        )

    # 5. پروتکل‌های هوشمند Sing-box و V2Ray (Reality, VMess, VLESS, Hysteria 2, TUIC):
    u = live_data.get("user", {}) if live_data else {}
    used_fmt = u.get("used_traffic_formatted") or "۰ بایت"
    limit_fmt = u.get("traffic_limit_formatted") or f"{acc.get('traffic_gb', 0)} GB"
    pct = u.get("traffic_percent", 0.0)
    expire = u.get("expire_date") or "پس از اولین اتصال"
    days_rem = u.get("days_remaining")
    days_str = f" ({to_fa(days_rem)} روز باقی‌مانده)" if days_rem is not None else ""
    enabled_str = "🟢 فعال" if u.get("enabled", True) else "🔴 غیرفعال"

    sub_url = acc.get("sub_url") or (live_data.get("sub_url", "") if live_data else "")
    sub_b64 = acc.get("sub_b64_url") or (live_data.get("sub_b64_url", "") if live_data else "")
    uuid_str = u.get("uuid") or "در سرور فعال"
    cfg_cnt = live_data.get("configs_count") or (len(live_data.get("configs", [])) if live_data else 26)

    lines = [
        "⚡ <b>مشخصات و وضعیت زنده اشتراک هوشمند Sing-box و V2Ray</b>\n",
        f"🏷 پلن: <b>{plan}</b>",
        f"👤 شناسه اشتراک: <code>{uname}</code>",
        f"🆔 <b>شناسه اتصال (UUID):</b>\n<code>{uuid_str}</code>",
        f"📶 وضعیت سرویس: {enabled_str}",
        f"📊 مصرف ترافیک: <b>{to_fa(used_fmt)}</b> از <b>{to_fa(limit_fmt)}</b> ({to_fa(pct)}٪)",
        f"⏱ تاریخ انقضا: <b>{to_fa(expire)}</b>{days_str}\n",
        "🔗 <b>لینک هوشمند سابسکریپشن (Normal Sub):</b>",
        f"<code>{sub_url}</code>\n",
        "📡 <b>لینک ساب Base64 (مخصوص v2rayNG / SlipNet):</b>",
        f"<code>{sub_b64}</code>\n",
        f"💡 <i>این سرویس حاوی {to_fa(cfg_cnt)} کانفیگ متنوع شامل Reality, VMess, VLESS, Trojan, Hysteria 2 و TUIC است. در پروتکل‌های V2Ray نیازی به رمز عبور نیست؛ اتصال بر پایه UUID و لینک‌های ساب بالا می‌باشد.</i>",
    ]
    return "\n".join(lines)


# ── پلن‌ها ───────────────────────────────────────────────────

def plan_label(plan: Dict[str, Any]) -> str:
    name = plan.get("name", "—")
    price = to_toman(plan.get("price", 0))
    return f"🛒 {name} — {price}"


# ── زیرمجموعه‌گیری ───────────────────────────────────────────

def format_referral(ref: Dict[str, Any], bot_username: str) -> str:
    code = ref.get("code", "")
    link = f"https://t.me/{bot_username}?start=ref_{code}"
    rate = ref.get("commission_rate_percent", 10)
    return (
        "🤝 <b>سیستم هوشمند بازاریابی و زیرمجموعه‌گیری</b>\n\n"
        "با دعوت از دوستان خود، درصدی از هر پرداخت آن‌ها را به صورت نقدی در کیف پول خود دریافت کنید!\n\n"
        f"🔗 <b>لینک اختصاصی شما:</b>\n<code>{link}</code>\n\n"
        f"👥 تعداد زیرمجموعه‌ها: <b>{to_fa(ref.get('total_referrals', 0))} نفر</b>\n"
        f"💵 مجموع پورسانت دریافتی: <b>{to_toman(ref.get('total_commission', 0))}</b>\n"
        f"📊 درصد پورسانت فعلی: <b>{to_fa(rate)}٪</b>"
    )


# ── تیکت‌ها ──────────────────────────────────────────────────

_STATUS_ICON = {"open": "🟢 در حال بررسی", "closed": "🔴 بسته شده", "answered": "🔵 پاسخ داده شد"}


def format_tickets_list(tickets: List[Dict[str, Any]]) -> str:
    if not tickets:
        return "📭 شما در حال حاضر تیکت پشتیبانی باز ندارید."
    lines = ["🎫 <b>لیست تیکت‌های پشتیبانی شما</b>\n"]
    for t in tickets:
        st = _STATUS_ICON.get(t.get("status"), t.get("status"))
        lines.append(
            f"• <b>تیکت #{to_fa(t.get('id'))}</b> — {t.get('subject')} [{st}]"
        )
    lines.append("\nبرای مشاهده مکالمات یا ارسال پاسخ روی تیکت مورد نظر کلیک کنید:")
    return "\n".join(lines)


def format_ticket_details(ticket: Dict[str, Any]) -> str:
    st = _STATUS_ICON.get(ticket.get("status"), ticket.get("status"))
    lines = [
        f"🎫 <b>تیکت شماره #{to_fa(ticket.get('id'))}</b>\n",
        f"📝 موضوع: <b>{ticket.get('subject')}</b>",
        f"📊 وضعیت: <b>{st}</b>",
        f"📅 ثبت شده در: <i>{to_fa(str(ticket.get('created_at'))[:19])}</i>\n",
        f"💬 <b>متن پیام:</b>\n{ticket.get('message')}\n",
    ]
    replies = ticket.get("replies", [])
    if replies:
        lines.append("──────────────")
        lines.append("📬 <b>مکالمات و پاسخ‌ها:</b>\n")
        for r in replies:
            sender_title = "🛠 پشتیبانی (مدیریت)" if r.get("sender") == "admin" else "👤 کاربر"
            lines.append(f"<b>{sender_title}:</b>\n{r.get('message')}\n")
    return "\n".join(lines)


# ── اعلان‌ها ─────────────────────────────────────────────────

def format_notifications_list(notifications: List[Dict[str, Any]]) -> str:
    if not notifications:
        return "📭 در حال حاضر اعلانی برای شما ثبت نشده است."
    lines = ["🔔 <b>اعلان‌ها و اخبار سیستم</b>\n"]
    for n in notifications:
        icon = "📭" if n.get("is_read") else "📩"
        date_str = str(n.get("created_at", ""))[:19]
        lines.append(
            f"{icon} <i>{to_fa(date_str)}</i>\n{n.get('message')}\n"
        )
    return "\n".join(lines)


# ── روش‌های پرداخت و کارت ─────────────────────────────────────

def format_gateways(card_number: str, card_holder: str) -> str:
    return (
        "💳 <b>اطلاعات پرداخت و شماره کارت</b>\n\n"
        f"شماره کارت بانکی:\n<code>{card_number}</code>\n"
        f"به نام: <b>{card_holder}</b>\n\n"
        "📌 پس از واریز، دکمه «💳 شارژ حساب با کارت‌به‌کارت» را بزنید و مبلغ و کد پیگیری فیش را ارسال فرمایید."
    )


# ──────────────────────────────────────────────────────────────
#  قالب‌بندی بخش‌های اختصاصی پنل مدیریت (Admin Formatters)
# ──────────────────────────────────────────────────────────────

def format_sales_stats(stats: Dict[str, Any], sys_data: Optional[Dict[str, Any]] = None) -> str:
    """قالب‌بندی آمار حرفه‌ای فروش برای مدیر."""
    cat_stats = stats.get("cat_stats", {})
    sb_cnt = cat_stats.get("singbox", 0)
    l2_cnt = cat_stats.get("system_l2tp", 0)
    dns_cnt = cat_stats.get("dnstt", 0)

    sys_text = ""
    if sys_data and sys_data.get("system"):
        s = sys_data["system"]
        protos = sys_data.get("vpn_protocols", {})
        sb_conn = protos.get("singbox", {}).get("connections", 0)
        sys_text = (
            "\n🖥 <b>وضعیت منابع زنده سرور MHPanel:</b>\n"
            f"▫️ پردازنده: <b>{to_fa(s.get('cpu_percent', 0))}%</b>\n"
            f"▫️ مصرف رم: <b>{to_fa(s.get('ram_percent', 0))}%</b>\n"
            f"▫️ مصرف دیسک: <b>{to_fa(s.get('disk_percent', 0))}%</b>\n"
            f"▫️ اتصالات فعال هسته Sing-box: <b>{to_fa(sb_conn)} کاربر متصل</b>\n"
        )

    return (
        "📊 <b>گزارش و آمار حرفه‌ای فروش و کاربران (MS VPN)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 کل کاربران ثبت‌شده: <b>{to_fa(stats.get('total_users', 0))} نفر</b>\n"
        f"📦 کل اشتراک‌های صادرشده: <b>{to_fa(stats.get('total_accounts', 0))} عدد</b>\n\n"
        "🏷 <b>تفکیک اشتراک‌های فروخته‌شده بر اساس پروتکل:</b>\n"
        f"⚡ هسته Sing-box هوشمند: <b>{to_fa(sb_cnt)} عدد</b>\n"
        f"🛡️ پروتکل‌های سیستمی L2TP/IKEv2: <b>{to_fa(l2_cnt)} عدد</b>\n"
        f"🌐 تانل‌های اضطراری DNS: <b>{to_fa(dns_cnt)} عدد</b>\n\n"
        "💰 <b>آمار مالی و درآمد:</b>\n"
        f"💵 درآمد کل: <b>{to_toman(stats.get('total_revenue', 0))}</b> ({to_fa(stats.get('total_orders', 0))} تراکنش)\n"
        f"☀️ فروش امروز: <b>{to_toman(stats.get('today_revenue', 0))}</b> ({to_fa(stats.get('today_orders', 0))} خرید)\n"
        f"📅 فروش ۳۰ روز اخیر: <b>{to_toman(stats.get('month_revenue', 0))}</b> ({to_fa(stats.get('month_orders', 0))} خرید)\n\n"
        f"⏳ فیش‌های در انتظار بررسی: <b>{to_fa(stats.get('pending_count', 0))} مورد</b> (مجموع: {to_toman(stats.get('pending_amount', 0))})"
        f"{sys_text}"
    )


def format_top_referrers(top_list: List[Dict[str, Any]]) -> str:
    if not top_list:
        return "📭 هیچ رفرالی تاکنون ثبت نشده است."
    lines = ["🏆 <b>برترین معرف‌ها و بازاریاب‌های ربات:</b>\n"]
    for i, r in enumerate(top_list, 1):
        uname = f"@{r['username']}" if r.get("username") else str(r['telegram_id'])
        lines.append(
            f"{to_fa(i)}. <b>{uname}</b> — 👥 {to_fa(r['ref_count'])} نفر جذب | 💵 {to_toman(r['total_comm'])} پورسانت"
        )
    return "\n".join(lines)


def format_server_settings_info(settings_dict: Dict[str, str], sys_status: Optional[Dict[str, Any]] = None) -> str:
    """نمایش تنظیمات و پارامترهای ارتباطی سرور."""
    srv_ip = settings_dict.get("server_ip") or settings.SERVER_IP
    dom = settings_dict.get("server_domain") or settings.SERVER_DOMAIN
    psk = settings_dict.get("ipsec_psk") or settings.IPSEC_PSK
    dnstt_dom = settings_dict.get("dnstt_domain") or settings.DNSTT_DOMAIN

    api_state = "🟢 متصل و آماده پاسخگویی" if sys_status and sys_status.get("system") else "🔴 عدم پاسخ"

    return (
        "⚙️ <b>تنظیمات سرور، پروتکل‌ها و هسته MHPanel</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 <b>آی‌پی سرور (Server IP):</b> <code>{srv_ip}</code>\n"
        f"🔗 <b>دامنه پنل و سابسکریپشن:</b> <code>{dom}</code>\n"
        f"🔌 <b>پورت وب‌سرویس پنل:</b> <code>9090</code>\n"
        f"🔐 <b>کلید IPsec Pre-Shared Key (PSK):</b> <code>{psk}</code>\n"
        f"📡 <b>دامنه سرور تانل DNS (SlowDNS):</b> <code>{dnstt_dom}</code>\n"
        f"📡 <b>وضعیت اتصال زنده API:</b> {api_state}\n\n"
        "جهت تغییر هر یک از مقادیر، از دکمه‌های زیر استفاده فرمایید:"
    )
