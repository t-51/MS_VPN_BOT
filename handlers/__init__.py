"""بسته‌ی هندلرهای ربات MS_VPN_BOT — رجیستر کردن کلیه روترها."""
from aiogram import Router

from handlers import (
    admin,
    auth,
    profile,
    accounts,
    shop,
    referral,
    tickets,
    notifications,
    wallet,
    downloads,
)


def get_main_router() -> Router:
    main = Router(name="main")

    # روتر مدیریت برای پاسخ به دستورات و کال‌بک‌های ادمین
    main.include_router(admin.router)

    # روترهای اصلی کاربر
    main.include_router(auth.router)
    main.include_router(downloads.router)
    main.include_router(shop.router)
    main.include_router(accounts.router)
    main.include_router(profile.router)
    main.include_router(wallet.router)
    main.include_router(referral.router)
    main.include_router(tickets.router)
    main.include_router(notifications.router)

    return main
