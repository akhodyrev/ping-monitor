#!/usr/bin/env python3
"""
Ping Monitor Bot — мониторинг доступности хостов с уведомлениями в Telegram
Использует синхронный HTTP API (requests), не требует асинхронного кода
"""
import yaml
import logging
import time
import sys
import signal
import os
import json
from datetime import datetime
from ping3 import ping
import requests

class PingMonitor:
    def __init__(self, config_path="config.yaml", hosts_path="hosts.yaml"):
        # Загрузка конфигурации
        self.config = self.load_config_raw(config_path, hosts_path)
        
        # Настройка логирования
        self.setup_logging()
        
        # Инициализация
        self.telegram_token = self.config["telegram"]["bot_token"]
        self.chat_id = self.config["telegram"]["chat_id"]
        self.host_states = {}
        self.running = True
        self.start_time = datetime.now()
        
        # Обработчики сигналов
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
        
        # Проверка конфигурации Telegram
        self.validate_telegram_config()
        
        # Отправка уведомления о запуске
        self.send_startup_notification()
    
    def load_config_raw(self, config_path, hosts_path):
        """Загрузка конфигурации без логгера"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
        except Exception as e:
            print(f"[CRITICAL] Ошибка загрузки {config_path}: {e}", file=sys.stderr)
            sys.exit(1)
        
        try:
            with open(hosts_path, 'r') as f:
                data = yaml.safe_load(f)
                hosts = data.get("hosts", [])
        except Exception as e:
            print(f"[CRITICAL] Ошибка загрузки {hosts_path}: {e}", file=sys.stderr)
            sys.exit(1)
        
        config["hosts"] = hosts
        return config
    
    def setup_logging(self):
        log_config = self.config.get("logging", {})
        log_file = log_config.get("log_file", "/var/log/ping-monitor.log")
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        logging.basicConfig(
            level=getattr(logging, log_config.get("log_level", "INFO")),
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("="*60)
        self.logger.info("ЗАПУСК МОНИТОРИНГА ДОСТУПНОСТИ ХОСТОВ")
        self.logger.info("="*60)
        self.logger.info(f"Загружено хостов: {len(self.config['hosts'])}")
        for h in self.config['hosts']:
            self.logger.info(f"  • {h['name']:20} {h['ip']:15} ({h.get('description', '-')})")
        self.logger.info(f"Интервал проверки: {self.config['monitoring']['check_interval']} сек")
        self.logger.info(f"Порог сбоя: {self.config['monitoring']['failure_threshold']} проверок")
        self.logger.info(f"Порог восстановления: {self.config['monitoring']['recovery_threshold']} проверок")
        self.logger.info("="*60)
    
    def validate_telegram_config(self):
        """Проверка корректности настроек Telegram"""
        if not self.telegram_token or self.telegram_token == "YOUR_BOT_TOKEN":
            self.logger.error("✗ bot_token не настроен в config.yaml")
            sys.exit(1)
        
        if not self.chat_id or self.chat_id == "YOUR_CHAT_ID":
            self.logger.error("✗ chat_id не настроен в config.yaml")
            sys.exit(1)
        
        # Тест подключения к API
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/getMe"
            response = requests.get(url, timeout=10)
            data = response.json()
            if not data.get("ok"):
                self.logger.error(f"✗ Ошибка Telegram API: {data.get('description', 'Unknown')}")
                sys.exit(1)
            username = data["result"].get("username", "N/A")
            self.logger.info(f"✓ Telegram бот: @{username}")
        except Exception as e:
            self.logger.error(f"✗ Ошибка подключения к Telegram: {e}")
            sys.exit(1)
    
    def send_telegram(self, text, parse_mode="HTML"):
        """Отправка сообщения в Telegram через HTTP API"""
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            if data.get("ok"):
                msg_id = data["result"]["message_id"]
                preview = text.split('\n')[0][:60].replace('<b>', '').replace('</b>', '').replace('<code>', '').replace('</code>', '')
                self.logger.info(f"📤 Telegram: {preview}...")
                return True
            else:
                desc = data.get('description', 'Unknown error')
                self.logger.warning(f"⚠️ Ошибка отправки в Telegram: {desc}")
                return False
        except Exception as e:
            self.logger.error(f"✗ Исключение при отправке в Telegram: {e}")
            return False
    
    def send_startup_notification(self):
        """Уведомление о запуске бота"""
        hostname = os.uname().nodename
        start_time = self.start_time.strftime('%Y-%m-%d %H:%M:%S')
        hosts_list = "\n".join([f"• <code>{h['ip']:15}</code> {h['name']}" for h in self.config['hosts']])
        
        message = (
            f"🚀 <b>Мониторинг запущен</b>\n"
            f"Сервер: <code>{hostname}</code>\n"
            f"Время: {start_time}\n"
            f"Хостов: {len(self.config['hosts'])}\n"
            f"\nОтслеживаемые хосты:\n{hosts_list}"
        )
        
        if self.send_telegram(message):
            self.logger.info("✅ Уведомление о запуске отправлено")
        else:
            self.logger.warning("⚠️ Не удалось отправить уведомление о запуске")
    
    def send_shutdown_notification(self):
        """Уведомление об остановке бота"""
        if not self.running:
            return
        
        stop_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        duration = datetime.now() - self.start_time
        hours, remainder = divmod(duration.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime = f"{int(hours)}ч {int(minutes)}м {int(seconds)}с"
        
        message = (
            f"🛑 <b>Мониторинг остановлен</b>\n"
            f"Время: {stop_time}\n"
            f"Uptime: {uptime}"
        )
        
        self.send_telegram(message)
        self.logger.info("✅ Уведомление об остановке отправлено")
    
    def check_host(self, host):
        """Проверка доступности хоста через ping"""
        try:
            result = ping(host["ip"], timeout=self.config["monitoring"]["timeout"])
            status = result is not None and result is not False
            response_time = f"{result*1000:.1f}ms" if result else "N/A"
            self.logger.debug(f"Пинг {host['name']:20} ({host['ip']:15}): {'✓' if status else '✗'} ({response_time})")
            return status
        except Exception as e:
            self.logger.error(f"Ошибка проверки {host['name']} ({host['ip']}): {e}")
            return False
    
    def check_all_hosts(self):
        """Проверка всех хостов"""
        for host in self.config['hosts']:
            ip = host["ip"]
            current_status = self.check_host(host)
            state = self.host_states.get(ip, {"status": True, "fail_count": 0, "success_count": 0})
            
            if current_status != state["status"]:
                if current_status:  # Восстановление
                    state["success_count"] += 1
                    state["fail_count"] = 0
                    self.logger.info(f"🔄 {host['name']:20} восстановление #{state['success_count']}/{self.config['monitoring']['recovery_threshold']}")
                    if state["success_count"] >= self.config["monitoring"]["recovery_threshold"]:
                        state["status"] = True
                        state["success_count"] = 0
                        message = (
                            f"✅ <b>{host['name']}</b> восстановлен\n"
                            f"IP: <code>{host['ip']}</code>\n"
                            f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        self.send_telegram(message)
                else:  # Потеря связи
                    state["fail_count"] += 1
                    state["success_count"] = 0
                    self.logger.warning(f"⚠️ {host['name']:20} недоступен #{state['fail_count']}/{self.config['monitoring']['failure_threshold']}")
                    if state["fail_count"] >= self.config["monitoring"]["failure_threshold"]:
                        state["status"] = False
                        state["fail_count"] = 0
                        message = (
                            f"❌ <b>{host['name']}</b> НЕДОСТУПЕН\n"
                            f"IP: <code>{host['ip']}</code>\n"
                            f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        self.send_telegram(message)
            else:
                # Сброс счётчиков при стабильном состоянии
                if current_status:
                    state["success_count"] = 0
                else:
                    state["fail_count"] = 0
            
            self.host_states[ip] = state
    
    def shutdown(self, signum, frame):
        self.logger.info("Получен сигнал завершения. Остановка мониторинга...")
        self.running = False
        self.send_shutdown_notification()
        sys.exit(0)
    
    def run(self):
        # Инициализация состояний
        for host in self.config['hosts']:
            self.host_states[host["ip"]] = {"status": True, "fail_count": 0, "success_count": 0}
        
        self.logger.info("Мониторинг активен. Нажмите Ctrl+C для остановки.\n")
        
        try:
            while self.running:
                self.check_all_hosts()
                time.sleep(self.config["monitoring"]["check_interval"])
        except KeyboardInterrupt:
            self.logger.info("Остановка по Ctrl+C")
            self.shutdown(None, None)
        except Exception as e:
            self.logger.exception(f"Критическая ошибка: {e}")
            try:
                self.send_telegram(f"⚠️ Мониторинг остановлен из-за ошибки:\n<code>{str(e)[:100]}</code>")
            except:
                pass
        finally:
            self.logger.info("Мониторинг завершён")

if __name__ == "__main__":
    # Проверка прав на пинг (ICMP)
    python_path = sys.executable
    try:
        import subprocess
        result = subprocess.run(['getcap', python_path], capture_output=True, text=True)
        if 'cap_net_raw' not in result.stdout:
            print(f"⚠️  Внимание: Python не имеет прав на отправку ICMP-пакетов")
            print(f"   Выполните: sudo setcap cap_net_raw+ep {python_path}")
            print(f"   Или запускайте скрипт с правами root (не рекомендуется)\n")
    except:
        pass
    
    monitor = PingMonitor("config.yaml", "hosts.yaml")
    monitor.run()
