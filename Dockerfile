FROM python:3.6
LABEL maintainer="fredi_68"
WORKDIR /app
RUN mkdir chat
RUN mkdir config
RUN mkdir sounds
RUN mkdir tracks
RUN mkdir logs
VOLUME /app/chat
VOLUME /app/config
VOLUME /app/sounds
VOLUME /app/tracks
VOLUME /app/logs
EXPOSE 50010/tcp
RUN apt-get update && apt-get install -y gcc libopus-dev
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python3", "ProtOS_Bot.py", "--docker"]