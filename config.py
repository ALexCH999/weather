"""Конфигурация приложения: загрузка параметров из переменных окружения (.env)."""

import os
from dotenv import load_dotenv

load_dotenv()

# Флаг отладки (полезно при разработке)
DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")

# Ключи API
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
