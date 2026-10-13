#!/usr/bin/env python3
"""
WeatherAI - Простое приложение для получения текущей погоды по названию города.
Использует OpenWeatherMap API (требует бесплатный API ключ).
"""

import os
import sys
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")

def get_weather(city: str, api_key: Optional[str] = None) -> dict:
    """
    Получает текущую погоду для указанного города.

    Args:
        city: Название города (на русском или английском)
        api_key: API ключ OpenWeatherMap (можно задать через переменную окружения OPENWEATHER_API_KEY)

    Returns:
        Словарь с данными о погоде или ошибкой
    """
    # Получаем API ключ: сначала из аргумента, потом из переменной окружения, потом из константы в коде
    if api_key is None:
        api_key = os.environ.get("OPENWEATHER_API_KEY") or OPENWEATHER_API_KEY

    if not api_key:
        return {
            "error": "API ключ не найден. Получите бесплатный ключ на https://openweathermap.org/api "
                     "и установите переменную окружения OPENWEATHER_API_KEY"
        }

    # URL для запроса к OpenWeatherMap API
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": api_key,
        "units": "metric",  # Цельсии
        "lang": "ru"        # Русский язык описания
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Формируем читаемый результат
        weather_info = {
            "city": data.get("name", city),
            "country": data.get("sys", {}).get("country", ""),
            "temperature": round(data.get("main", {}).get("temp", 0)),
            "feels_like": round(data.get("main", {}).get("feels_like", 0)),
            "description": data.get("weather", [{}])[0].get("description", "").capitalize(),
            "humidity": data.get("main", {}).get("humidity", 0),
            "pressure": data.get("main", {}).get("pressure", 0),
            "wind_speed": data.get("wind", {}).get("speed", 0),
        }

        return weather_info

    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            return {"error": "Неверный API ключ. Проверьте OPENWEATHER_API_KEY"}
        elif response.status_code == 404:
            return {"error": f"Город '{city}' не найден. Проверьте написание."}
        else:
            return {"error": f"Ошибка API: {e}"}
    except requests.exceptions.ConnectionError:
        return {"error": "Нет подключения к интернету. Проверьте соединение."}
    except requests.exceptions.Timeout:
        return {"error": "Превышено время ожидания ответа от сервера."}
    except Exception as e:
        return {"error": f"Неизвестная ошибка: {e}"}


def format_weather(weather: dict, city_name: str = None, for_telegram: bool = False) -> str:
    """
    Формирует красивое сообщение о погоде.

    Args:
        weather: Словарь с данными о погоде
        city_name: Название города (если не в данных)
        for_telegram: True для HTML-форматирования (Telegram), False для консоли

    Returns:
        Отформатированная строка
    """
    if "error" in weather:
        prefix = "❌ " if not for_telegram else ""
        return f"{prefix}Ошибка: {weather['error']}"

    city = weather["city"]
    country = weather["country"]
    temp = weather["temperature"]
    feels = weather["feels_like"]
    desc = weather["description"]
    humidity = weather["humidity"]
    pressure = weather["pressure"]
    wind = weather["wind_speed"]

    location = city_name or (f"{city}, {country}" if country else city)

    if for_telegram:
        # HTML для Telegram
        lines = [
            f"🌤 <b>Погода в {location}</b>",
            "",
            f"🌡 Температура: <b>{temp}°C</b> (ощущается как <b>{feels}°C</b>)",
            f"☁ {desc}",
            f"💧 Влажность: <b>{humidity}%</b>",
            f"📊 Давление: <b>{pressure} гПа</b>",
            f"💨 Ветер: <b>{wind} м/с</b>",
        ]
        return "\n".join(lines)
    else:
        # Обычный текст для консоли
        lines = [
            f"\n{'='*40}",
            f"🌤  Погода в {location}",
            f"{'='*40}",
            f"🌡  Температура: {temp}°C (ощущается как {feels}°C)",
            f"☁  {desc}",
            f"💧 Влажность: {humidity}%",
            f"📊 Давление: {pressure} гПа",
            f"💨 Ветер: {wind} м/с",
            f"{'='*40}\n",
        ]
        return "\n".join(lines)


def print_weather(weather: dict) -> None:
    """Красиво выводит информацию о погоде в консоль."""
    print(format_weather(weather, for_telegram=False))


def main():
    """Главная функция программы."""
    # Поддержка запуска с аргументом: python weather.py "Москва"
    if len(sys.argv) > 1:
        city = sys.argv[1]
        weather = get_weather(city)
        print(format_weather(weather, for_telegram=False))
        return

    print("🌤  WeatherAI - Погода по городам")
    print("Введите название города (или 'exit' для выхода)")
    print("-" * 40)

    while True:
        try:
            city = input("\n🏙  Город: ").strip()

            if not city:
                print("Пожалуйста, введите название города.")
                continue

            if city.lower() in ("exit", "quit", "выход", "q"):
                print("👋 До свидания!")
                break

            print("⏳ Получаю погоду...")
            weather = get_weather(city)
            print_weather(weather)

        except KeyboardInterrupt:
            print("\n\n👋 До свидания!")
            break
        except EOFError:
            print("\n👋 До свидания!")
            break


if __name__ == "__main__":
    main()