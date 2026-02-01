#!/usr/bin/env python3
import sys
import yaml
import requests
from datetime import datetime

print("="*60)
print("ТЕСТ ПОДКЛЮЧЕНИЯ К TELEGRAM (через HTTP API)")
print("="*60)

# Загрузка конфига
try:
    with open("config.yaml", 'r') as f:
        config = yaml.safe_load(f)
    print("✓ config.yaml загружен")
except Exception as e:
    print(f"✗ Ошибка загрузки config.yaml: {e}")
    sys.exit(1)

token = config.get("telegram", {}).get("bot_token", "")
chat_id = config.get("telegram", {}).get("chat_id", "")

# Проверка токена
if not token or token == "YOUR_BOT_TOKEN":
    print("\n❌ ОШИБКА: bot_token не настроен в config.yaml")
    print("   Получите токен у @BotFather")
    sys.exit(1)
print(f"\nТокен бота: {token[:5]}...{token[-5:]}")

# Проверка chat_id
if not chat_id or chat_id == "YOUR_CHAT_ID":
    print("\n❌ ОШИБКА: chat_id не настроен в config.yaml")
    print("   Получите ID у @userinfobot")
    sys.exit(1)
print(f"Chat ID: {chat_id}")

# Тест подключения к API
print("\nПроверка подключения к Telegram API...")
api_url = f"https://api.telegram.org/bot{token}/getMe"
try:
    response = requests.get(api_url, timeout=10)
    data = response.json()
    if data.get("ok"):
        bot_info = data["result"]
        username = bot_info.get('username', 'N/A')
        print(f"✓ Бот авторизован: @{username} (ID: {bot_info['id']})")
    else:
        print(f"❌ Ошибка API: {data.get('description', 'Unknown')}")
        sys.exit(1)
except Exception as e:
    print(f"❌ Ошибка подключения: {e}")
    print("   Проверьте: интернет, фаервол, блокировку Telegram")
    sys.exit(1)

# Отправка тестового сообщения
print(f"\nОтправка тестового сообщения в чат {chat_id}...")
test_msg = f"✅ ТЕСТ УСПЕШЕН!\nСервер: {__import__('os').uname().nodename}\nВремя: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
send_url = f"https://api.telegram.org/bot{token}/sendMessage"
payload = {
    "chat_id": chat_id,
    "text": test_msg,
    "parse_mode": "HTML"
}

try:
    response = requests.post(send_url, json=payload, timeout=10)
    data = response.json()
    if data.get("ok"):
        print(f"✓ Сообщение доставлено! Message ID: {data['result']['message_id']}")
        print("\n" + "="*60)
        print("✅ ВСЁ РАБОТАЕТ! Бот может отправлять сообщения.")
        print("="*60)
        print("\n⚠️  ЕСЛИ СООБЩЕНИЕ НЕ ПРИШЛО В ТЕЛЕГРАМ:")
        print("   1. Откройте бота и напишите /start (обязательно!)")
        print("   2. Для групп: добавьте бота в группу и сделайте администратором")
        print("   3. Проверьте, не заблокирован ли бот вами")
    else:
        desc = data.get('description', 'Unknown error')
        print(f"❌ Ошибка отправки: {desc}")
        if "bot was blocked" in desc.lower():
            print("\n👉 РЕШЕНИЕ: Откройте бота в Telegram и напишите /start")
        elif "chat not found" in desc.lower():
            print("\n👉 РЕШЕНИЕ: Для групп используйте ID вида -1001234567890")
            print("   И добавьте бота в группу как администратора")
        sys.exit(1)
except Exception as e:
    print(f"❌ Ошибка запроса: {e}")
    sys.exit(1)
    