FROM python:3.11-slim

WORKDIR /app

RUN ln -sf /usr/share/zoneinfo/Asia/Taipei /etc/localtime && echo "Asia/Taipei" > /etc/timezone

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY check_broker.py .
COPY fetch_history.py .
COPY scheduler.py .

ENV PYTHONUNBUFFERED=1
CMD ["python3", "scheduler.py"]
