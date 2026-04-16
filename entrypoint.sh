#!/bin/bash
ln -sf /usr/share/zoneinfo/Asia/Taipei /etc/localtime
echo "Asia/Taipei" > /etc/timezone
echo "=== Broker checker started ==="
echo "排程：每週一到週五 19:00 (台灣時間)"
exec python3 scheduler.py
