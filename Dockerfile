FROM python:3.6
LABEL maintainer="fredi_68"
WORKDIR /app
RUN mkdir chat
RUN mkdir config
RUN mkdir sounds
RUN mkdir tracks
RUN mkdir logs
VOLUME chat
VOLUME config
VOLUME sounds
VOLUME tracks
VOLUME logs
RUN apt-get install -y gcc
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python3", "ProtOS_Bot.py", "--docker"]