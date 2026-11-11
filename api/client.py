"""کلاینت ارتباط امن با API پنل MHPanel.

تمام درخواست‌ها با استفاده از کلید X-API-Key ارسال شده و خروجی یکپارچه Dict[str, Any]
دارای کلید 'success' برمی‌گردانند.
"""
import asyncio
from typing import Optional, Dict, Any

import aiohttp

from config import settings


def _fail(message: str, status_code: Optional[int] = None, **extra) -> Dict[str, Any]:
    return {"success": False, "error": message, "status_code": status_code, **extra}


async def request(
    method: str,
    endpoint: str,
    *,
    data: Optional[Dict] = None,
    params: Optional[Dict] = None,
) -> Dict[str, Any]:
    """ارسال یک درخواست HTTP به API پنل MHPanel."""
    base = settings.PANEL_API_URL.rstrip("/")
    path = endpoint.lstrip("/")
    url = f"{base}/{path}"

    headers = {
        "Accept": "application/json",
        "X-API-Key": settings.PANEL_API_KEY,
        "Authorization": f"Bearer {settings.PANEL_API_KEY}",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"

    timeout = aiohttp.ClientTimeout(total=settings.API_TIMEOUT)
    # نادیده گرفتن خطاهای گواهینامه SSL برای جلوگیری از تداخل آی‌پی محلی
    connector = aiohttp.TCPConnector(ssl=False)

    try:
        async with aiohttp.ClientSession(headers=headers, timeout=timeout, connector=connector) as session:
            async with session.request(
                method, url, json=data, params=params
            ) as response:
                try:
                    payload = await response.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError):
                    text = await response.text()
                    return _fail(
                        "پاسخ نامعتبر از سرور MHPanel.",
                        status_code=response.status,
                        raw=text[:300],
                    )

                if isinstance(payload, dict) and "success" not in payload:
                    payload["success"] = 200 <= response.status < 300

                if isinstance(payload, dict) and not payload.get("success", False):
                    payload.setdefault("status_code", response.status)
                    payload.setdefault(
                        "error", payload.get("error") or f"HTTP {response.status}"
                    )

                return payload if isinstance(payload, dict) else {"success": True, "data": payload}

    except asyncio.TimeoutError:
        return _fail("پاسخ سرور پنل در زمان مقرر دریافت نشد (Timeout).")
    except aiohttp.ClientError as e:
        return _fail(f"خطای شبکه در ارتباط با پنل MHPanel: {e}")
    except Exception as e:
        return _fail(f"خطای پیش‌بینی‌نشده: {e}")


async def get(endpoint: str, *, params: Optional[Dict] = None) -> Dict[str, Any]:
    return await request("GET", endpoint, params=params)


async def post(endpoint: str, *, data: Optional[Dict] = None) -> Dict[str, Any]:
    return await request("POST", endpoint, data=data)


async def delete(endpoint: str, *, data: Optional[Dict] = None) -> Dict[str, Any]:
    return await request("DELETE", endpoint, data=data)
