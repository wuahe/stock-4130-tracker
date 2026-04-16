#!/bin/bash

# 將環境變數寫入 cron 可讀取的檔案
env > /app/.env

# 寫入 cron 排程：每週一到週五 19:00 (台灣時間)
cat > /etc/cron.d/broker-check << 'EOF'
0 19 * * 1-5 cd /app && export $(cat /app/.env | xargs) && python3 check_broker.py >> /var/log/broker.log 2>&1
EOF
chmod 0644 /etc/cron.d/broker-check
crontab /etc/cron.d/broker-check

echo "=== Broker checker started ==="
echo "排程：每週一到週五 19:00 (台灣時間)"
echo "首次測試執行..."
python3 check_broker.py

# 啟動 cron 並保持容器運行
cron -f
