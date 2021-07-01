FROM python:3.8

ENV PYTHONUNBUFFERED True
ENV APP_HOME /app

WORKDIR $APP_HOME
COPY . ./

RUN pip install -r requirements.txt

#ENV PORT 8080 (port should be set by cloud run)

# 當 Docker 容器啟動時，自動執行 app.py
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app