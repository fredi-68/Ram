FROM python:3.6-alpine
WORKDIR /app
RUN pip install -r requirements.txt
CMD ["python3", "ProtOS_Bot.py"]