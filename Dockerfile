FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY ./telegram_bot /app/telegram_bot

CMD ["python", "-m", "telegram_bot.bot"]
