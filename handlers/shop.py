"""هندلر فروشگاه: دسته‌بندی‌های پویا، ایزوله‌سازی پروتکل‌ها (V2Ray, Singbox, L2TP, DNS, WireGuard, GAS) و صدور آنی."""
import io
import json
import secrets
import qrcode
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from api import panel_api
from config import settings
from db import database
from filters.auth import IsAuthorized
from keyboards.inline import (
    build_shop_categories_keyboard,
    build_plans_keyboard,
    build_payment_methods_keyboard,
    account_details_keyboard,
)
from keyboards.reply import main_menu_keyboard, cancel_keyboard
from states.forms import ChargeCardStates, GASWizardStates
from utils.helpers import to_toman, to_fa, api_error_text

router = Router(name="shop")
router.message.filter(IsAuthorized())
router.callback_query.filter(IsAuthorized())

# لیست اینباندهای مجزا برای دسته‌بندی V2Ray
V2RAY_INBOUNDS = [
    "vmess-in", "vmess-ws-tls", "vmess-grpc-tls", "vmess-upgrade-tls",
    "vless-ws-in", "vless-grpc-tls", "vless-upgrade-tls", "vless-tcp-tls"
]

# لیست اینباندهای مجزا برای Reality
REALITY_INBOUNDS = [
    "vless-reality-in", "vless-reality-grpc", "vless-reality-upgrade"
]


# ──────────────────────────────────────────────────────────────
#  اکانت تستی رایگان (قابل تنظیم توسط مدیر)
# ──────────────────────────────────────────────────────────────

@router.message(F.text == "🎁 اکانت تستی")
async def request_free_trial(message: types.Message):
    telegram_id = message.from_user.id
    user = await database.get_user(telegram_id)
    if not user:
        user = await database.get_or_create_user(telegram_id, message.from_user.username, message.from_user.first_name)

    is_enabled = (await database.get_setting("trial_enabled", "1")) == "1"
    if not is_enabled:
        return await message.answer(
            "⚠️ <b>توزیع اکانت تستی رایگان در حال حاضر توسط مدیریت موقتاً متوقف شده است.</b>\n\n"
            "جهت تهیه اشتراک، لطفاً از بخش «🛒 خرید اشتراک» اقدام فرمایید.",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard,
        )

    if user.get("trial_used"):
        return await message.answer(
            "⚠️ <b>شما قبلاً سهمیه اکانت تستی رایگان خود را دریافت کرده‌اید!</b>\n\n"
            "جهت تهیه اشتراک‌های پرسرعت، از بخش «🛒 خرید اشتراک» اقدام نمایید.",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard,
        )

    trial_gb = float(await database.get_setting("trial_traffic_gb", str(settings.TRIAL_TRAFFIC_GB)))
    trial_days = int(await database.get_setting("trial_duration_days", str(settings.TRIAL_DURATION_DAYS)))

    rand_suffix = secrets.token_hex(2)
    panel_user = f"ms_t_{telegram_id}_{rand_suffix}"

    wait_msg = await message.answer("⏳ در حال صدور اکانت تستی شما روی هسته MHPanel...")

    res = await panel_api.create_user(
        username=panel_user,
        traffic_limit_gb=trial_gb,
        validity_days=trial_days,
        expiry_type="on_first_use",
        category="MS_VPN_Trial",
        note=f"Trial TG: {telegram_id} (@{message.from_user.username or ''})",
    )

    if not res.get("success"):
        await wait_msg.delete()
        return await message.answer(
            f"❌ متأسفانه در ساخت اکانت تستی خطایی رخ داد:\n{api_error_text(res)}",
            reply_markup=main_menu_keyboard,
        )

    created_u = res.get("user", {})
    sub_token = created_u.get("sub_token", "")
    sub_url = created_u.get("sub_url", f"{settings.PANEL_SUB_URL}/{sub_token}")
    sub_b64 = created_u.get("sub_b64_url", f"{sub_url}/b64")

    await database.save_account(
        telegram_id=telegram_id,
        panel_username=panel_user,
        category="singbox",
        plan_name="اکانت تستی رایگان",
        sub_token=sub_token,
        sub_url=sub_url,
        sub_b64_url=sub_b64,
        is_trial=1,
        traffic_gb=trial_gb,
        duration_days=trial_days,
    )
    await database.set_trial_used(telegram_id)
    await wait_msg.delete()

    success_text = (
        "🎉 <b>اکانت تستی رایگان شما با موفقیت صادر شد!</b>\n\n"
        f"👤 نام کاربری در پنل: <code>{panel_user}</code>\n"
        f"📶 ترافیک هدیه: <b>{to_fa(trial_gb)} گیگابایت</b>\n"
        f"⏱ مدت اعتبار: <b>{to_fa(trial_days)} روز</b> (آغاز پس از اولین اتصال)\n\n"
        "🔗 <b>لینک هوشمند سابسکریپشن:</b>\n"
        f"<code>{sub_url}</code>\n\n"
        "📡 <b>لینک ساب Base64 (سازگار با تمامی کلاینت‌ها):</b>\n"
        f"<code>{sub_b64}</code>\n\n"
        "💡 جهت اتصال، لینک بالا را در نرم‌افزارهای SlipNet یا v2rayNG وارد فرمایید."
    )
    await message.answer(success_text, reply_markup=main_menu_keyboard, parse_mode="HTML")


# ──────────────────────────────────────────────────────────────
#  فروشگاه و دسته‌بندی‌های پویا
# ──────────────────────────────────────────────────────────────

@router.message(F.text.in_({"🛒 خرید اشتراک", "🛒 خرید اکانت"}))
async def show_shop_categories(message: types.Message):
    """نمایش دسته‌بندی‌های فعال فروشگاه."""
    cats = await database.get_active_categories()
    if not cats:
        return await message.answer("📭 در حال حاضر هیچ دسته‌بندی فعالی در فروشگاه وجود ندارد.")

    text = (
        "🛒 <b>فروشگاه تخصصی اشتراک‌های MS VPN (سامانه MHPanel)</b>\n\n"
        "پروتکل‌ها و بستر اتصال مورد نظر خود را از میان دسته‌بندی‌های زیر انتخاب فرمایید:\n"
    )
    for c in cats:
        text += f"\n▫️ <b>{c.get('icon', '⚡')} {c.get('title')}:</b>\n<i>{c.get('description', '')}</i>\n"

    await message.answer(text, reply_markup=build_shop_categories_keyboard(cats), parse_mode="HTML")


@router.callback_query(F.data == "shop:categories")
async def cb_shop_categories(callback: types.CallbackQuery):
    cats = await database.get_active_categories()
    text = "🛒 <b>لطفاً دسته‌بندی مورد نظر خود را انتخاب فرمایید:</b>"
    await callback.message.edit_text(text, reply_markup=build_shop_categories_keyboard(cats), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("shop:cat:"))
async def cb_select_category(callback: types.CallbackQuery):
    cat_key = callback.data.split(":")[2]
    cat = await database.get_category_by_key(cat_key)
    if not cat:
        return await callback.answer("دسته‌بندی یافت نشد.", show_alert=True)
    if not cat.get("is_active"):
        return await callback.answer("⚠️ این دسته‌بندی در حال حاضر توسط مدیریت خاموش و غیرفعال شده است.", show_alert=True)

    plans = await database.get_plans_by_category(cat_key, active_only=True)
    if not plans:
        return await callback.answer("هنوز پلنی برای این دسته‌بندی ثبت نشده است.", show_alert=True)

    icon = cat.get("icon") or "⚡"
    title = cat.get("title", "")
    desc = cat.get("description", "")
    text = (
        f"{icon} <b>پلن‌های اشتراک {title}</b>\n\n"
        f"<i>{desc}</i>\n\n"
        "👇 لطفاً پلن مورد نظر خود را انتخاب فرمایید:"
    )
    await callback.message.edit_text(text, reply_markup=build_plans_keyboard(plans, cat_key), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("buy:plan:"))
async def cb_select_plan(callback: types.CallbackQuery):
    plan_id = int(callback.data.split(":")[2])
    plan = await database.get_plan_by_id(plan_id)
    if not plan:
        return await callback.answer("پلن یافت نشد.", show_alert=True)

    cat_key = plan.get("category_key", "singbox")
    cat = await database.get_category_by_key(cat_key)
    if not cat or not cat.get("is_active"):
        return await callback.answer("⚠️ این پروتکل در حال حاضر توسط مدیریت غیرفعال شده است.", show_alert=True)

    traffic_desc = f"{to_fa(plan.get('traffic_gb'))} گیگابایت" if plan.get('traffic_gb') > 0 else "نامحدود سرعتی"

    text = (
        f"📦 <b>مشخصات پلن انتخابی:</b>\n\n"
        f"🏷 عنوان: <b>{plan.get('name')}</b>\n"
        f"📶 حجم ترافیک: <b>{traffic_desc}</b>\n"
        f"⏱ مدت اعتبار: <b>{to_fa(plan.get('duration_days'))} روز</b>\n"
        f"💰 مبلغ نهایی: <b>{to_toman(plan.get('price'))}</b>\n\n"
        "👇 لطفاً روش پرداخت را انتخاب فرمایید:"
    )
    await callback.message.edit_text(text, reply_markup=build_payment_methods_keyboard(plan_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("buy:pay:"))
async def cb_process_payment(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    plan_id = int(parts[2])
    method = parts[3]

    plan = await database.get_plan_by_id(plan_id)
    if not plan:
        return await callback.answer("پلن نامعتبر است.", show_alert=True)

    cat_key = plan.get("category_key", "singbox")
    cat = await database.get_category_by_key(cat_key)
    if not cat or not cat.get("is_active"):
        return await callback.answer("⚠️ این پروتکل در حال حاضر خاموش است و امکان خرید وجود ندارد.", show_alert=True)

    proto_type = cat.get("protocol_type", "singbox") if cat else "singbox"

    telegram_id = callback.from_user.id
    user = await database.get_user(telegram_id)

    # 1. پرداخت از موجودی کیف پول
    if method == "wallet":
        current_balance = user.get("wallet_balance", 0) if user else 0
        price = plan.get("price", 0)

        if current_balance < price:
            shortage = price - current_balance
            alert_text = (
                f"❌ <b>موجودی کیف پول شما کافی نیست!</b>\n\n"
                f"💰 موجودی فعلی: <b>{to_toman(current_balance)}</b>\n"
                f"💳 مبلغ پلن: <b>{to_toman(price)}</b>\n"
                f"⚠️ کسری موجودی: <b>{to_toman(shortage)}</b>\n\n"
                "جهت خرید، ابتدا از بخش «💰 کیف پول» حساب خود را شارژ فرمایید."
            )
            await callback.message.edit_text(alert_text, parse_mode="HTML")
            return await callback.answer()

        # کسر موجودی
        await database.update_wallet_balance(telegram_id, -price)
        await database.create_transaction(telegram_id, price, "buy", "wallet", status="approved")

        # پورسانت رفرال
        ref_pct = int(await database.get_setting("referral_percent", str(settings.REFERRAL_PERCENT)))
        referrer_id = user.get("referrer_id") if user else None
        if referrer_id:
            comm = int(price * ref_pct / 100)
            if comm > 0:
                await database.update_wallet_balance(referrer_id, comm)
                await database.create_transaction(referrer_id, comm, "commission", "system", status="approved")

        rand_suffix = secrets.token_hex(2)
        srv_ip = await database.get_setting("server_ip", settings.SERVER_IP)
        psk = await database.get_setting("ipsec_psk", settings.IPSEC_PSK)

        # ── ۱. دسته V2Ray (ایزوله فقط پروتکل‌های V2Ray) ──
        if proto_type == "v2ray":
            panel_user = f"ms_v2_{telegram_id}_{rand_suffix}"
            res = await panel_api.create_user(
                username=panel_user,
                traffic_limit_gb=plan.get("traffic_gb", 30.0),
                validity_days=plan.get("duration_days", 30),
                expiry_type="on_first_use",
                category="MS_V2Ray",
                inbounds=V2RAY_INBOUNDS,
                note=f"V2Ray TG: {telegram_id} - {plan.get('name')}",
            )
            if not res.get("success"):
                await database.update_wallet_balance(telegram_id, price)
                return await callback.message.edit_text(f"❌ خطا در صدور اکانت V2Ray:\n{api_error_text(res)}")

            created_u = res.get("user", {})
            sub_token = created_u.get("sub_token", "")
            sub_url = created_u.get("sub_url", f"{settings.PANEL_SUB_URL}/{sub_token}")
            sub_b64 = created_u.get("sub_b64_url", f"{sub_url}/b64")

            await database.save_account(
                telegram_id=telegram_id,
                panel_username=panel_user,
                category="v2ray",
                plan_name=plan.get("name"),
                sub_token=sub_token,
                sub_url=sub_url,
                sub_b64_url=sub_b64,
                is_trial=0,
                traffic_gb=plan.get("traffic_gb"),
                duration_days=plan.get("duration_days"),
            )

            success_text = (
                "🎉 <b>اشتراک اختصاصی V2Ray با موفقیت صادر شد!</b>\n\n"
                f"🏷 پلن: <b>{plan.get('name')}</b>\n"
                f"👤 نام کاربری در پنل: <code>{panel_user}</code>\n"
                f"📶 حجم ترافیک: <b>{to_fa(plan.get('traffic_gb'))} گیگابایت</b>\n"
                f"⏱ مدت اعتبار: <b>{to_fa(plan.get('duration_days'))} روز</b>\n\n"
                "🔗 <b>لینک هوشمند سابسکریپشن V2Ray:</b>\n"
                f"<code>{sub_url}</code>\n\n"
                "📡 <b>لینک ساب Base64 (مخصوص v2rayNG / SlipNet):</b>\n"
                f"<code>{sub_b64}</code>\n\n"
                "💡 این سابسکریپشن فقط شامل پروتکل‌های خالص VMess و VLESS می‌باشد."
            )
            await callback.message.edit_text(success_text, parse_mode="HTML")

        # ── ۲. دسته Reality (فقط اینباندهای Reality) ──
        elif proto_type == "reality":
            panel_user = f"ms_real_{telegram_id}_{rand_suffix}"
            res = await panel_api.create_user(
                username=panel_user,
                traffic_limit_gb=plan.get("traffic_gb", 30.0),
                validity_days=plan.get("duration_days", 30),
                expiry_type="on_first_use",
                category="MS_Reality",
                inbounds=REALITY_INBOUNDS,
                note=f"Reality TG: {telegram_id} - {plan.get('name')}",
            )
            if not res.get("success"):
                await database.update_wallet_balance(telegram_id, price)
                return await callback.message.edit_text(f"❌ خطا در صدور اکانت Reality:\n{api_error_text(res)}")

            created_u = res.get("user", {})
            sub_token = created_u.get("sub_token", "")
            sub_url = created_u.get("sub_url", f"{settings.PANEL_SUB_URL}/{sub_token}")
            sub_b64 = created_u.get("sub_b64_url", f"{sub_url}/b64")

            await database.save_account(
                telegram_id=telegram_id,
                panel_username=panel_user,
                category="reality",
                plan_name=plan.get("name"),
                sub_token=sub_token,
                sub_url=sub_url,
                sub_b64_url=sub_b64,
                is_trial=0,
                traffic_gb=plan.get("traffic_gb"),
                duration_days=plan.get("duration_days"),
            )

            success_text = (
                "🎉 <b>اشتراک اختصاصی VLESS Reality صادر شد!</b>\n\n"
                f"🏷 پلن: <b>{plan.get('name')}</b>\n"
                f"👤 نام کاربری: <code>{panel_user}</code>\n"
                f"🔗 <b>لینک سابسکریپشن Reality:</b>\n<code>{sub_url}</code>\n\n"
                f"📡 <b>لینک Base64:</b>\n<code>{sub_b64}</code>"
            )
            await callback.message.edit_text(success_text, parse_mode="HTML")

        # ── ۳. دسته پروتکل‌های سیستمی مستقیم (L2TP/IKEv2) ──
        elif proto_type == "system_l2tp":
            panel_user = f"ms_l2tp_{telegram_id}_{rand_suffix}"
            panel_pass = f"Ms{secrets.token_hex(3)}"

            res = await panel_api.create_l2tp_user(
                username=panel_user,
                password=panel_pass,
                traffic_limit_gb=plan.get("traffic_gb", 30.0),
                validity_days=plan.get("duration_days", 30),
            )
            if not res.get("success"):
                await database.update_wallet_balance(telegram_id, price)
                return await callback.message.edit_text(f"❌ خطا در صدور اکانت سیستمی:\n{api_error_text(res)}")

            acc_id = await database.save_account(
                telegram_id=telegram_id,
                panel_username=panel_user,
                panel_password=panel_pass,
                category="system_l2tp",
                plan_name=plan.get("name"),
                server_info=srv_ip,
                is_trial=0,
                traffic_gb=plan.get("traffic_gb"),
                duration_days=plan.get("duration_days"),
            )

            success_text = (
                "🎉 <b>اشتراک پروتکل‌های استاندارد با موفقیت صادر شد!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🏷 پلن: <b>{plan.get('name')}</b>\n"
                f"👤 <b>نام کاربری (Username):</b> <code>{panel_user}</code>\n"
                f"🔑 <b>رمز عبور (Password):</b> <code>{panel_pass}</code>\n"
                f"🌐 <b>آدرس سرور:</b> <code>{srv_ip}</code>\n\n"
                "⚡ <b>این اکانت به طور همزمان برای کلیه پروتکل‌های زیر فعال است:</b>\n"
                f"▫️ <b>Cisco AnyConnect:</b> سرور <code>{srv_ip}:10443</code>\n"
                f"▫️ <b>OpenVPN:</b> پورت <code>1194</code> (دانلود .ovpn از دکمه زیر)\n"
                f"▫️ <b>L2TP / IPsec:</b> سرور <code>{srv_ip}</code> | کلید (PSK): <code>{psk}</code>\n"
                f"▫️ <b>IKEv2:</b> سرور <code>{srv_ip}</code>\n"
                f"▫️ <b>SSH Tunnel:</b> سرور <code>{srv_ip}</code> | پورت: <code>22</code> و <code>2053</code>\n"
                f"▫️ <b>SSTP:</b> سرور <code>{srv_ip}</code> | پورت: <code>443</code>\n\n"
                "👇 جهت دانلود فایل OpenVPN یا گواهی‌ها، از دکمه‌های زیر استفاده فرمایید:"
            )
            await callback.message.edit_text(
                success_text,
                reply_markup=account_details_keyboard(acc_id, category="system_l2tp"),
                parse_mode="HTML",
            )

        # ── ۴. دسته تانل DNS (SlowDNS / SlipNet) ──
        elif proto_type == "dnstt":
            panel_user = f"ms_dns_{telegram_id}_{rand_suffix}"
            panel_pass = f"Dns{secrets.token_hex(3)}"
            dnstt_dom = await database.get_setting("dnstt_domain", settings.DNSTT_DOMAIN)
            dnstt_pub = await database.get_setting("dnstt_pubkey", settings.DNSTT_PUBKEY)

            res = await panel_api.create_l2tp_user(
                username=panel_user,
                password=panel_pass,
                traffic_limit_gb=plan.get("traffic_gb", 0.0),
                validity_days=plan.get("duration_days", 30),
            )
            if not res.get("success"):
                await database.update_wallet_balance(telegram_id, price)
                return await callback.message.edit_text(f"❌ خطا در صدور اکانت در سرور:\n{api_error_text(res)}")

            acc_id = await database.save_account(
                telegram_id=telegram_id,
                panel_username=panel_user,
                panel_password=panel_pass,
                category="dnstt",
                plan_name=plan.get("name"),
                server_info=dnstt_dom,
                is_trial=0,
                traffic_gb=plan.get("traffic_gb"),
                duration_days=plan.get("duration_days"),
            )

            # استخراج فوری تمامی کانفیگ‌های تانل DNS و SlipNet
            all_uris = await panel_api.get_all_dns_slipnet_uris(username=panel_user, password=panel_pass)

            # ۱. تولید و ارسال بارکد QR کانفیگ اصلی (VayDNS یا DNSTT)
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
                    qr_photo = BufferedInputFile(bio.getvalue(), filename=f"slipnet_qr_{panel_user}.png")
                    await callback.message.answer_photo(
                        photo=qr_photo,
                        caption=(
                            f"📷 <b>بارکد اتصال سریع به تانل DNS (کلاینت SlipNet)</b>\n\n"
                            f"👤 کاربر: <code>{panel_user}</code> | 🔑 رمز: <code>{panel_pass}</code>\n"
                            "💡 جهت اتصال، این بارکد را در نرم‌افزار SlipNet اسکن فرمایید."
                        ),
                        parse_mode="HTML",
                    )
                except Exception:
                    pass

            # ۲. ارسال فایل متنی کلیه کانفیگ‌ها (.txt)
            if all_uris:
                lines = [
                    "==================================================",
                    " MS VPN - Complete SlipNet & DNS Tunnel Configs",
                    f" Username: {panel_user}",
                    f" Password: {panel_pass}",
                    f" DNS Domain: {dnstt_dom}",
                    f" Public Key: {dnstt_pub}",
                    "==================================================\n",
                ]
                for p_key, p_info in all_uris.items():
                    lines.append(f"## {p_info.get('label')}")
                    lines.append(f"{p_info.get('uri')}\n")

                doc = BufferedInputFile("\n".join(lines).encode("utf-8"), filename=f"MS_SlipNet_{panel_user}.txt")
                await callback.message.answer_document(
                    doc,
                    caption="📁 <b>فایل جامع کلیه کانفیگ‌های تانل DNS و SlipNet</b>\n💡 قابل دانلود و ذخیره در موبایل.",
                    parse_mode="HTML",
                )

            # ۳. آماده‌سازی پیام متنی شامل تمام کانفیگ‌های تکی
            cfg_blocks = []
            for p_key, p_info in all_uris.items():
                lbl = p_info.get("label", p_key.upper())
                uri = p_info.get("uri", "")
                cfg_blocks.append(f"⚡ <b>{lbl}:</b>\n<code>{uri}</code>")

            all_cfgs_text = "\n\n".join(cfg_blocks)

            success_text = (
                "🎉 <b>اشتراک تانل ضد فیلتر DNS (SlowDNS / SlipNet) با موفقیت صادر شد!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🏷 پلن: <b>{plan.get('name')}</b>\n"
                f"👤 <b>نام کاربری:</b> <code>{panel_user}</code>\n"
                f"🔑 <b>رمز عبور:</b> <code>{panel_pass}</code>\n"
                f"📡 <b>دامنه سرور DNS:</b> <code>{dnstt_dom}</code>\n"
                f"🔑 <b>کلید عمومی سرور:</b>\n<code>{dnstt_pub}</code>\n\n"
                "📋 <b>کانفیگ‌های کلاینت SlipNet (با یک لمس روی کد، کپی می‌شود):</b>\n\n"
                f"{all_cfgs_text}\n\n"
                "💡 <i>پروتکل‌های بالا در زمان قطعی کامل اینترنت بین‌الملل و فیلترینگ شدید از طریق پورت ۵۳ متصل می‌شوند.</i>"
            )
            await callback.message.edit_text(
                success_text,
                reply_markup=account_details_keyboard(acc_id, category="dnstt"),
                parse_mode="HTML",
            )

        # ── ۵. دسته پروتکل اختصاصی و مدرن WireGuard ──
        elif proto_type == "wireguard":
            panel_user = f"ms_wg_{telegram_id}_{rand_suffix}"
            res = await panel_api.create_wireguard_account(
                name=panel_user,
                traffic_limit_gb=plan.get("traffic_gb", 30.0),
                validity_days=plan.get("duration_days", 30),
            )
            if not res.get("success"):
                await database.update_wallet_balance(telegram_id, price)
                return await callback.message.edit_text(f"❌ خطا در صدور اکانت وایرگارد:\n{api_error_text(res)}")

            client_conf = res.get("config", "")
            client_ip = res.get("ip", "")
            pubkey = res.get("public_key", "")
            sub_token = res.get("sub_token", "")

            acc_id = await database.save_account(
                telegram_id=telegram_id,
                panel_username=panel_user,
                panel_password=pubkey,
                category="wireguard",
                plan_name=plan.get("name"),
                server_info=client_conf,
                sub_token=sub_token,
                is_trial=0,
                traffic_gb=plan.get("traffic_gb"),
                duration_days=plan.get("duration_days"),
            )

            success_text = (
                "🎉 <b>اشتراک اختصاصی وایرگارد (WireGuard) با موفقیت صادر شد!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🏷 پلن: <b>{plan.get('name')}</b>\n"
                f"👤 نام کاربری: <code>{panel_user}</code>\n"
                f"🌐 آی‌پی کلاینت: <code>{client_ip}</code>\n"
                f"📶 حجم ترافیک: <b>{to_fa(plan.get('traffic_gb'))} گیگابایت</b>\n"
                f"⏱ مدت اعتبار: <b>{to_fa(plan.get('duration_days'))} روز</b>\n\n"
                "⚡ فایل کانفیگ و بارکد اختصاصی QR برای شما در زیر ارسال گردید.\n"
                "جهت مدیریت اکانت می‌توانید از دکمه‌های زیر استفاده فرمایید:"
            )
            await callback.message.edit_text(
                success_text,
                reply_markup=account_details_keyboard(acc_id, category="wireguard"),
                parse_mode="HTML",
            )

            # ارسال فایل .conf
            try:
                conf_doc = BufferedInputFile(
                    client_conf.encode("utf-8"),
                    filename=f"MS_WireGuard_{panel_user}.conf",
                )
                await callback.message.answer_document(
                    document=conf_doc,
                    caption=f"📁 <b>فایل کانفیگ اختصاصی وایرگارد</b>\n👤 <code>{panel_user}</code>",
                    parse_mode="HTML",
                )
            except Exception:
                pass

            # ارسال تصویر QR Code اختصاصی
            try:
                qr = qrcode.QRCode(box_size=8, border=3)
                qr.add_data(client_conf)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                bio = io.BytesIO()
                img.save(bio, format="PNG")
                bio.seek(0)
                qr_photo = BufferedInputFile(bio.getvalue(), filename=f"wg_qr_{panel_user}.png")
                await callback.message.answer_photo(
                    photo=qr_photo,
                    caption="📷 <b>بارکد اختصاصی WireGuard جهت اسکن مستقیم در موبایل</b>",
                    parse_mode="HTML",
                )
            except Exception:
                pass

        # ── ۶. دسته گوگل اسکریپت و کلودفلر (GAS / Workers) ──
        elif proto_type == "gas":
            kb = InlineKeyboardBuilder()
            kb.button(text="⚡ تحویل فوری با سرور ابری فعال", callback_data=f"gas:instant:{plan_id}")
            kb.button(text="🔑 ساخت پروژه با توکن گوگل و کلودفلر شخصی", callback_data=f"gas:wiz_start:{plan_id}")
            kb.button(text="🔙 بازگشت", callback_data="shop:cats")
            kb.adjust(1)
            gas_prompt = (
                "☁️ <b>راه‌اندازی تونل ابری گوگل اسکریپت (GAS)</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🏷 پلن انتخابی: <b>{plan.get('name')}</b>\n"
                f"💰 هزینه: <b>{to_toman(price)}</b> (کسر شده از موجودی)\n\n"
                "لطفاً شیوه صدور و استقرار را انتخاب نمایید:\n\n"
                "⚡ <b>۱. تحویل فوری (پیشنهادی):</b>\n"
                "بدون نیاز به ساخت توکن، فوراً لینک اختصاصی Goose VPN و وب‌اپ پرسرعت گوگل تحویل داده می‌شود.\n\n"
                "🔑 <b>۲. استقرار اختصاصی بر روی جیمیل شما:</b>\n"
                "ربات با دریافت توکن Google OAuth پروژه را مستقیماً روی گوگل اسکریپت شما Deploy می‌کند."
            )
            return await callback.message.edit_text(gas_prompt, reply_markup=kb.as_markup(), parse_mode="HTML")

        # ── ۷. دسته کامل Sing-box VIP (تمام ۲۳ اینباند) ──
        else:
            panel_user = f"ms_sb_{telegram_id}_{rand_suffix}"
            res = await panel_api.create_user(
                username=panel_user,
                traffic_limit_gb=plan.get("traffic_gb", 30.0),
                validity_days=plan.get("duration_days", 30),
                expiry_type="on_first_use",
                category="MS_Singbox_VIP",
                note=f"Singbox VIP TG: {telegram_id} - {plan.get('name')}",
            )
            if not res.get("success"):
                await database.update_wallet_balance(telegram_id, price)
                return await callback.message.edit_text(f"❌ خطا در صدور اکانت Sing-box:\n{api_error_text(res)}")

            created_u = res.get("user", {})
            sub_token = created_u.get("sub_token", "")
            sub_url = created_u.get("sub_url", f"{settings.PANEL_SUB_URL}/{sub_token}")
            sub_b64 = created_u.get("sub_b64_url", f"{sub_url}/b64")

            await database.save_account(
                telegram_id=telegram_id,
                panel_username=panel_user,
                category="singbox",
                plan_name=plan.get("name"),
                sub_token=sub_token,
                sub_url=sub_url,
                sub_b64_url=sub_b64,
                is_trial=0,
                traffic_gb=plan.get("traffic_gb"),
                duration_days=plan.get("duration_days"),
            )

            success_text = (
                "🎉 <b>خرید شما با موفقیت انجام شد و اشتراک تحویل گردید!</b>\n\n"
                f"🏷 پلن: <b>{plan.get('name')}</b>\n"
                f"👤 نام کاربری در پنل: <code>{panel_user}</code>\n"
                f"📶 حجم ترافیک: <b>{to_fa(plan.get('traffic_gb'))} گیگابایت</b>\n"
                f"⏱ مدت اعتبار: <b>{to_fa(plan.get('duration_days'))} روز</b>\n\n"
                "🔗 <b>لینک هوشمند سابسکریپشن:</b>\n"
                f"<code>{sub_url}</code>\n\n"
                "📡 <b>لینک ساب Base64 (v2rayNG / SlipNet):</b>\n"
                f"<code>{sub_b64}</code>\n\n"
                "💡 از بخش «📦 اکانت‌های من» می‌توانید وضعیت مصرف و انقضا را مشاهده فرمایید."
            )
            await callback.message.edit_text(success_text, parse_mode="HTML")

        await callback.answer("خرید با موفقیت انجام شد!")

    # 2. پرداخت کارت‌به‌کارت
    elif method == "card":
        card = await database.get_random_bank_card()
        card_num = card.get("card_number")
        card_hl = card.get("card_holder")

        await state.set_state(ChargeCardStates.waiting_amount)
        await state.update_data(
            target_plan_id=plan_id,
            plan_price=plan.get("price"),
            assigned_card=card_num,
            assigned_holder=card_hl,
        )
        card_text = (
            f"💳 <b>پرداخت کارت‌به‌کارت برای {plan.get('name')}</b>\n\n"
            f"💰 مبلغ قابل پرداخت: <b>{to_toman(plan.get('price'))}</b>\n\n"
            f"💳 شماره کارت جهت واریز:\n<code>{card_num}</code>\n"
            f"به نام: <b>{card_hl}</b>\n\n"
            "📌 پس از واریز، مبلغ ارسالی خود را به تومان وارد فرمایید:"
        )
        await callback.message.answer(card_text, reply_markup=cancel_keyboard, parse_mode="HTML")
        await callback.answer()


# ──────────────────────────────────────────────────────────────
#  هندلرهای ویزارد و تحویل سرویس گوگل اسکریپت و کلودفلر (GAS)
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("gas:instant:"))
async def cb_gas_instant_delivery(callback: types.CallbackQuery):
    """تحویل فوری اکانت ابری گوگل اسکریپت با زیرساخت آماده سرور."""
    plan_id = int(callback.data.split(":")[2])
    plan = await database.get_plan_by_id(plan_id)
    telegram_id = callback.from_user.id

    gas_cfg = await panel_api.get_gas_client_configs(use_cloudflare=True)
    mhrv = gas_cfg.get("mhrv_profile", {})
    goose_uri = gas_cfg.get("goose_uri", "")
    webapp_url = mhrv.get("apps_script_url", "")
    secret = mhrv.get("auth_key", "gas_secret")
    scripts = mhrv.get("script_ids", [])
    dep_id = scripts[0] if scripts else "AKfycb_CloudDeployment"

    panel_user = f"gas_{telegram_id}_{secrets.token_hex(2)}"
    acc_id = await database.save_account(
        telegram_id=telegram_id,
        panel_username=panel_user,
        panel_password=secret,
        category="gas",
        plan_name=plan.get("name") if plan else "اشتراک ابری GAS",
        server_info=dep_id,
        sub_url=webapp_url,
        sub_b64_url=goose_uri,
        is_trial=0,
        traffic_gb=plan.get("traffic_gb", 0) if plan else 0,
        duration_days=plan.get("duration_days", 30) if plan else 30,
    )

    success_text = (
        "🎉 <b>اشتراک ابری گوگل اسکریپت و کلودفلر (GAS) با موفقیت تحویل داده شد!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 سرویس: <b>{plan.get('name') if plan else 'گوگل اسکریپت'}</b>\n"
        f"👤 شناسه اکانت: <code>{panel_user}</code>\n"
        f"🔑 رمز تونل: <code>{secret}</code>\n"
        f"🆔 شناسه استقرار (Deployment ID):\n<code>{dep_id}</code>\n\n"
        "🔗 <b>آدرس وب‌اپ اختصاصی گوگل:</b>\n"
        f"<code>{webapp_url}</code>\n\n"
        "🚀 <b>لینک اتصال مستقیم در Goose VPN:</b>\n"
        f"<code>{goose_uri}</code>\n\n"
        "💡 با استفاده از نرم‌افزار <b>Goose VPN</b> یا کلاینت‌های هسته <b>Sing-box</b> می‌توانید با نهایت سرعت و پایداری متصل شوید."
    )
    await callback.message.edit_text(
        success_text,
        reply_markup=account_details_keyboard(acc_id, category="gas"),
        parse_mode="HTML",
    )
    await callback.answer("✅ اکانت تحویل داده شد!")


@router.callback_query(F.data.startswith("gas:wiz_start:"))
async def cb_gas_wizard_start(callback: types.CallbackQuery, state: FSMContext):
    """شروع مراحل دریافت توکن گوگل و کلودفلر از کاربر."""
    plan_id = int(callback.data.split(":")[2])
    plan = await database.get_plan_by_id(plan_id)

    await state.set_state(GASWizardStates.waiting_google_token)
    await state.update_data(plan_id=plan_id, plan_name=plan.get("name") if plan else "GAS")

    guide_text = (
        "🔑 <b>گام اول: ثبت توکن گوگل (Google OAuth Token)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "جهت استقرار خودکار پروژه روی اکانت گوگل شما، به توکن دسترسی پروژه نیاز است.\n\n"
        "📖 <b>مراحل دریافت توکن دسترسی (۱ دقیقه):</b>\n"
        "۱. وارد صفحه رسمی <a href='https://developers.google.com/oauthplayground'>Google OAuth 2.0 Playground</a> شوید.\n"
        "۲. در ستون چپ در کادر <code>Input your own scopes</code> این آدرس را کپی کنید:\n"
        "<code>https://www.googleapis.com/auth/script.projects</code>\n"
        "۳. روی دکمه آبی <b>Authorize APIs</b> بزنید و دسترسی جیمیل خود را تأیید کنید.\n"
        "۴. سپس روی دکمه <b>Exchange authorization code for tokens</b> کلیک کنید.\n"
        "۵. مقدار کادر <b>Access token</b> (که با <code>ya29...</code> شروع می‌شود) را کپی کرده و به ربات ارسال فرمایید.\n\n"
        "✉️ <i>نکته: در صورت تمایل می‌توانید آدرس ایمیل جیمیل خود را نیز در پیام بعدی ارسال فرمایید.</i>"
    )
    await callback.message.answer(guide_text, reply_markup=cancel_keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(GASWizardStates.waiting_google_token)
async def process_gas_google_token(message: types.Message, state: FSMContext):
    """دریافت توکن گوگل و پرسش در مورد کلودفلر."""
    token_input = (message.text or "").strip()
    if token_input == "❌ لغو":
        await state.clear()
        return await message.answer("❌ عملیات استقرار گوگل اسکریپت لغو شد.", reply_markup=main_menu_keyboard)

    await state.update_data(google_token=token_input)
    await state.set_state(GASWizardStates.waiting_cf_credentials)

    kb = InlineKeyboardBuilder()
    kb.button(text="⚡ استقرار فقط روی گوگل (بدون کلودفلر)", callback_data="gas:skip_cf")
    kb.adjust(1)

    cf_prompt = (
        "🌐 <b>گام دوم: اطلاعات کلودفلر (اختیاری جهت رله فوق‌سریع)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "اگر مایلید ترافیک از شبکه Cloudflare Workers نیز رله شود، "
        "اطلاعات API Token و Account ID کلودفلر خود را با کاما جدا کرده و ارسال فرمایید:\n\n"
        "فرمت ورودی:\n"
        "<code>API_TOKEN,ACCOUNT_ID</code>\n\n"
        "💡 یا در صورت عدم تمایل، دکمه زیر را لمس کنید تا پروژه فقط روی گوگل مستقر شود:"
    )
    await message.answer(cf_prompt, reply_markup=kb.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "gas:skip_cf")
async def cb_gas_skip_cf(callback: types.CallbackQuery, state: FSMContext):
    """استقرار پروژه فقط با توکن گوگل بدون ورکر کلودفلر."""
    await callback.answer("در حال شروع استقرار روی گوگل...")
    await _finalize_gas_deployment(callback.message, state, cf_token="", cf_acc_id="", user_id=callback.from_user.id)


@router.message(GASWizardStates.waiting_cf_credentials)
async def process_gas_cf_credentials(message: types.Message, state: FSMContext):
    """دریافت توکن‌های کلودفلر و اجرای استقرار خودکار."""
    text = (message.text or "").strip()
    if text == "❌ لغو":
        await state.clear()
        return await message.answer("❌ عملیات لغو شد.", reply_markup=main_menu_keyboard)

    cf_token = ""
    cf_acc_id = ""
    if "," in text:
        parts = [p.strip() for p in text.split(",", 1)]
        cf_token = parts[0]
        cf_acc_id = parts[1]
    else:
        cf_token = text

    await _finalize_gas_deployment(message, state, cf_token=cf_token, cf_acc_id=cf_acc_id, user_id=message.from_user.id)


async def _finalize_gas_deployment(message_or_target: types.Message, state: FSMContext, cf_token: str, cf_acc_id: str, user_id: int):
    data = await state.get_data()
    google_token = data.get("google_token", "")
    plan_id = data.get("plan_id")
    plan = await database.get_plan_by_id(plan_id) if plan_id else None

    status_msg = await message_or_target.answer("⏳ <b>در حال ارسال پروژه و استقرار خودکار روی گوگل و کلودفلر...</b>\nلطفاً چند لحظه شکیبا باشید.", parse_mode="HTML")

    mode = "google_and_cloudflare" if (cf_token and cf_acc_id) else "google_only"
    email = f"user_{user_id}@gmail.com"
    if "@" in google_token and "ya29." not in google_token:
        email = google_token
        google_token = ""

    deploy_res = await panel_api.deploy_gas_wizard(
        name=f"gas_usr_{user_id}",
        email=email,
        google_token=google_token,
        cf_token=cf_token,
        cf_account_id=cf_acc_id,
        mode=mode,
    )

    await state.clear()

    if not deploy_res.get("success"):
        return await status_msg.edit_text(
            f"❌ <b>خطا در استقرار پروژه گوگل اسکریپت:</b>\n{api_error_text(deploy_res)}\n\n"
            "مبلغی از شما کسر نگردید یا در صورت کسر، به کیف پول شما بازگردانده می‌شود."
        )

    acc_info = deploy_res.get("account", {})
    acc_id_str = deploy_res.get("account_id", "")
    dep_id = acc_info.get("deployment_id", "")
    webapp_url = acc_info.get("webapp_url", "")
    panel_user = acc_info.get("name", f"gas_{user_id}")

    # استعلام کانفیگ کلاینت
    cfg_res = await panel_api.get_gas_client_configs(account_id=acc_id_str)
    goose_uri = cfg_res.get("goose_uri", "")
    secret = cfg_res.get("goose_json", {}).get("secret", "gas_secret")

    db_acc_id = await database.save_account(
        telegram_id=user_id,
        panel_username=panel_user,
        panel_password=secret,
        category="gas",
        plan_name=plan.get("name") if plan else "اشتراک اختصاصی GAS",
        server_info=dep_id or acc_id_str,
        sub_url=webapp_url,
        sub_b64_url=goose_uri,
        is_trial=0,
        traffic_gb=plan.get("traffic_gb", 0) if plan else 0,
        duration_days=plan.get("duration_days", 30) if plan else 30,
    )

    success_text = (
        "🎉 <b>پروژه اختصاصی گوگل اسکریپت با موفقیت Deploy شد!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 سرویس: <b>{plan.get('name') if plan else 'GAS اختصاصی'}</b>\n"
        f"👤 نام پروژه: <code>{panel_user}</code>\n"
        f"🆔 شناسه استقرار (Deployment ID):\n<code>{dep_id}</code>\n\n"
        "🌐 <b>آدرس WebApp اختصاصی:</b>\n"
        f"<code>{webapp_url}</code>\n\n"
        "🚀 <b>لینک اتصال مستقیم در Goose VPN:</b>\n"
        f"<code>{goose_uri}</code>\n\n"
        "💡 جهت مشاهده جزئیات اتصال و راهنما از دکمه‌های زیر استفاده فرمایید:"
    )
    await status_msg.edit_text(
        success_text,
        reply_markup=account_details_keyboard(db_acc_id, category="gas"),
        parse_mode="HTML",
    )
