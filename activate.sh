sudo mkdir -p /opt/ping-monitor
sudo cp ping_monitor.py config.yaml hosts.yaml /opt/ping-monitor/

sudo systemctl daemon-reload
sudo systemctl enable ping-monitor
sudo systemctl start ping-monitor

# Проверка статуса
sudo systemctl status ping-monitor
# Просмотр логов
sudo journalctl -u ping-monitor -f
