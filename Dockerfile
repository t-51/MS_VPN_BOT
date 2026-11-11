FROM python:3.12-slim

# تنظیم منطقه زمانی و دایرکتوری کاری
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Tehran

WORKDIR /app

# نصب پکیج‌های پایه سیستم
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# کپی فایل‌های نیازمندی و نصب پکیج‌ها
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# کپی کل سورس کد به کانتینر
COPY . .

# ایجاد دایرکتوری دیتابیس
RUN mkdir -p /app/data

VOLUME ["/app/data"]

CMD ["python", "bot.py"]
