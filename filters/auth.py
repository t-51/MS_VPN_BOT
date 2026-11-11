"""فیلتر بررسی و ثبت‌نام خودکار کاربر در بات."""
from typing import Union

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from db import database


class IsAuthorized(BaseFilter):
    """ثبت‌نام خودکار کاربر در دیتابیس در اولین تعامل و صدور اجازه دسترسی."""

    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        user = event.from_user
        if not user:
            return False

        # ثبت‌نام خودکار در صورت عدم وجود در دیتابیس
        db_user = await database.get_user(user.id)
        if not db_user:
            await database.get_or_create_user(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
            )
        return True
