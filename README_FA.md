# آریا — دستیار هوشمند فارسی

این پروژه یک نسخهٔ اولیه از دستیار گفت‌وگویی فارسی است. کدنویسی روی گوشی لازم نیست؛ فایل‌ها را در GitHub قرار بده و با Render اجرا کن.

## فایل‌ها
- `app.py`: برنامهٔ دستیار
- `requirements.txt`: کتابخانه‌های لازم
- `render.yaml`: تنظیمات اولیهٔ استقرار Render

## راه‌اندازی کوتاه
1. فایل ZIP را از حالت فشرده خارج کن.
2. در https://github.com/new یک مخزن با نام `arya-persian-assistant` بساز.
3. در مخزن، گزینهٔ **Add file → Upload files** را بزن و هر چهار فایل (`app.py`، `requirements.txt`، `render.yaml`، `README_FA.md`) را بارگذاری و Commit کن.
4. در https://dashboard.render.com/ وارد شو؛ **New → Web Service** را انتخاب کن و مخزن GitHub را متصل کن.
5. اگر Render تنظیمات `render.yaml` را تشخیص داد، از همان تنظیمات استفاده کن. در غیر این صورت:
   - Build command: `pip install -r requirements.txt`
   - Start command: `python app.py`
6. در Environment Variables سرویس این موارد را تنظیم کن:
   - `OPENROUTER_API_KEY`: کلیدی که از https://openrouter.ai/settings/keys ساخته‌ای
   - `OPENROUTER_MODEL`: `openrouter/free`
   - `AI_PERSONALITY`: شخصیت دلخواه آریا
7. سرویس را Deploy کن و آدرس وبی که Render می‌دهد باز کن.

## تنظیمات اختیاری (Environment Variables)
- `MAX_TOKENS`: بیشینهٔ طول پاسخ (پیش‌فرض ۱۵۰۰)
- `HISTORY_LIMIT`: تعداد پیام‌های قبلی که به مدل داده می‌شود (پیش‌فرض ۱۶)
- `MAX_INPUT_CHARS`: بیشینهٔ طول پیام کاربر (پیش‌فرض ۴۰۰۰)
- `SITE_URL`: آدرس سایتت (برای شناسایی در OpenRouter؛ اختیاری)

## امنیت
کلید API را در فایل‌ها، GitHub، پیام گفتگو یا تصویر صفحه قرار نده. فقط در بخش Environment Variables سرویس میزبانی واردش کن. اگر کلید افشا شد، آن را باطل و کلید تازه بساز.

## خطاهای رایج
- `401`: کلید API اشتباه یا نامعتبر است.
- `402`: محدودیت اعتبار یا هزینهٔ سرویس مدل.
- `404`: نام مدل اشتباه است.
- `429`: محدودیت تعداد درخواست‌ها؛ کمی صبر کن.
- خطای ساخت برنامه: بخش Logs در Render را باز کن.

## نکته
مدل `openrouter/free` و سرویس میزبانی ممکن است محدودیت دسترسی، صف یا تغییرات قیمت داشته باشند؛ رایگان بودن همیشگی تضمین‌شده نیست. این نسخه حافظهٔ دائمی بین نشست‌ها ندارد.
