"""نقطه‌ی شروع ربات تلگرام MS_VPN_BOT (متصل به سامانه MHPanel).

راه‌اندازی بات، دیسپچر، مقداردهی اولیه دیتابیس و اتصال به وب‌سرویس MHPanel.
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from db import database
from handlers import get_main_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)
logger = logging.getLogger("MS_VPN_BOT")


async def main():
    # مقداردهی اولیه‌ی دیتابیس محلی
    await database.init_db()
    logger.info("دیتابیس محلی ربات با موفقیت مقداردهی شد.")

    # تست اولیه اتصال به API پنل MHPanel
    from api import panel_api
    try:
        status_res = await panel_api.get_all_users()
        if status_res.get("success"):
            logger.info(f"✅ اتصال به API پنل MHPanel برقرار است. تعداد کاربران فعلی: {status_res.get('count', 0)}")
        else:
            logger.warning(f"⚠️ پاسخ ناموفق از پنل MHPanel: {status_res.get('error')}")
    except Exception as e:
        logger.error(f"❌ خطا در بررسی اولیه اتصال به MHPanel: {e}")

    # راه‌اندازی ربات تلگرام
    bot = Bot(token=settings.TELEGRAM_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # الصاق روترهای اصلی برنامه
    dp.include_router(get_main_router())

    logger.info(f"🤖 ربات MS VPN با موفقیت راه‌اندازی شد (یوزرنیم: @{settings.BOT_USERNAME}).")
    print(f"🤖 ربات MS VPN (@{settings.BOT_USERNAME}) شروع به کار کرد.")
    
    # حذف پیام‌های آپدیت انباشته شده قبل از اجرا
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("⛔ ربات متوقف شد.")
