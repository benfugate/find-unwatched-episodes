FROM python:3.11-slim

RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y cron

COPY requirements.txt .
RUN pip3 install -r requirements.txt && rm requirements.txt

COPY cron-schedule /etc/cron.d/cron-schedule
RUN chmod 0644 /etc/cron.d/cron-schedule && \
    crontab /etc/cron.d/cron-schedule && \
    touch /var/log/cron.log

COPY . /usr/src/app/
COPY entrypoint.sh /
CMD ["/bin/sh", "/usr/src/app/entrypoint.sh"]