# 🚀 Інструкція для деплою Telegram-бота на Render.com

## 1. Створи акаунт
Перейди на [https://render.com](https://render.com) і створи безкоштовний акаунт.

## 2. Завантаж бота на GitHub
1. Створи новий репозиторій на GitHub, наприклад `telegram-bot`.
2. Завантаж туди вміст цієї папки (`bot.py`, `requirements.txt`, `render.yaml`).

## 3. Розгорни на Render
1. На головній сторінці Render натисни “New → Web Service”.
2. Обери “Deploy from GitHub”.
3. Підключи свій репозиторій.
4. Render автоматично розпізнає `render.yaml`.

## 4. Додай BOT_TOKEN
1. У Render у розділі “Environment → Add Environment Variable”.
2. Назва: `BOT_TOKEN`
3. Значення: твій токен із BotFather.

## 5. Запуск
Render сам встановить Python і бібліотеки, після чого запустить бота.
Бот запуститься через кілька секунд після деплою.

## 6. Логи
Перевірити роботу можна у вкладці **Logs** на Render.
