#!/usr/bin/env python3
import yaml
import logging
import time
import sys
import signal
from datetime import datetime
from ping3 import ping
from telegram import Bot
from telegram.error import TelegramError

class PingMonitor:
    def __init__(self, config_path="config.yaml", hosts_path="hosts.yaml"):
        self.load_config(config_path, hosts_path)
        self.setup_logging()
        self.bot = Bot(token=self.config["telegram"]["bot_token"])
        self.chat_id = self.config["telegram"]["chat_id"]
        self.host_states = {}  # {ip: {"status": bool, "fail_count": int, "last_change": timestamp}}
        self.running = True
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
        
    def load_config(self, config_path, hosts_path):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        with open(hosts_path, 'r') as f:
            self.hosts = yaml.safe_load(f)["hosts"]
    
    def setup_logging(self):
        log_config = self.config.get("logging", {})
        logging.basicConfig(
            level=getattr(logging, log_config.get("log_level", "INFO")),
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.FileHandler(log_config.get("log_file", "/var/log/ping-monitor.log")),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def timestamp(self):
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def check_host(self, host):
        """Проверяет доступность хоста через пинг"""
        try:
            result = ping(host["ip"], timeout=self.config["monitoring"]["timeout"])
            return result is not None and result is not False
        except Exception as e:
            self.logger.error(f"Ошибка проверки {host['name']} ({host['ip']}): {e}")
            return False
    
    def send_telegram(self, message):
        """Отправляет уведомление в Telegram"""
        try:
            self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode="HTML")
            self.logger.info(f"Уведомление отправлено: {message[:50]}...")
        except TelegramError as e:
            self.logger.error(f"Ошибка отправки в Telegram: {e}")
    
    def check_all_hosts(self):
        """Проверяет все хосты и отправляет уведомления при изменении состояния"""
        for host in self.hosts:
            ip = host["ip"]
            current_status = self.check_host(host)
            state = self.host_states.get(ip, {"status": True, "fail_count": 0, "success_count": 0})
            
            # Обновляем счётчики
            if current_status != state["status"]:
                if current_status:  # Восстановление
                    state["success_count"] += 1
                    state["fail_count"] = 0
                    if state["success_count"] >= self.config["monitoring"]["recovery_threshold"]:
                        state["status"] = True
                        state["success_count"] = 0
                        message = (
                            f"✅ <b>{host['name']}</b> восстановлен\n"
                            f"IP: {host['ip']}\n"
                            f"Описание: {host.get('description', '-')}\n"
                            f"Время: {self.timestamp()}"
                        )
                        self.send_telegram(message)
                        self.logger.info(f"Хост восстановлен: {host['name']} ({host['ip']})")
                else:  # Потеря связи
                    state["fail_count"] += 1
                    state["success_count"] = 0
                    if state["fail_count"] >= self.config["monitoring"]["failure_threshold"]:
                        state["status"] = False
                        state["fail_count"] = 0
                        downtime = ""
                        if "last_down" in state:
                            downtime = f"\nНедоступен с: {state['last_down']}"
                        message = (
                            f"❌ <b>{host['name']}</b> НЕДОСТУПЕН\n"
                            f"IP: {host['ip']}\n"
                            f"Описание: {host.get('description', '-')}\n"
                            f"Время: {self.timestamp()}"
                            f"{downtime}"
                        )
                        self.send_telegram(message)
                        self.logger.warning(f"Хост недоступен: {host['name']} ({host['ip']})")
                        state["last_down"] = self.timestamp()
            else:
                # Сбрасываем противоположный счётчик при стабильном состоянии
                if current_status:
                    state["success_count"] = 0
                else:
                    state["fail_count"] = 0
            
            self.host_states[ip] = state
    
    def shutdown(self, signum, frame):
        self.logger.info("Получен сигнал завершения. Остановка мониторинга...")
        self.running = False
    
    def run(self):
        self.logger.info("Запуск мониторинга доступности хостов")
        self.logger.info(f"Отслеживается хостов: {len(self.hosts)}")
        
        # Инициализация состояний
        for host in self.hosts:
            self.host_states[host["ip"]] = {"status": True, "fail_count": 0, "success_count": 0}
        
        try:
            while self.running:
                self.check_all_hosts()
                time.sleep(self.config["monitoring"]["check_interval"])
        except Exception as e:
            self.logger.exception(f"Критическая ошибка: {e}")
            self.send_telegram(f"⚠️ Мониторинг остановлен из-за ошибки: {e}")
        finally:
            self.logger.info("Мониторинг остановлен")

if __name__ == "__main__":
    monitor = PingMonitor("config.yaml", "hosts.yaml")
    monitor.run()

