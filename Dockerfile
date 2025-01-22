FROM python:3.10

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY bot.py bot.py
COPY config.py config.py
COPY open_weather_api.py open_weather_api.py
COPY requirements.txt requirements.txt

CMD ["python", "bot.py"]
