# Use official Python image
FROM python:3.12

# Set working directory
WORKDIR /app

# Copy files
COPY . /app

# Install cron and timezone data for daily scheduling
RUN apt-get update \
	&& apt-get install -y --no-install-recommends cron tzdata \
	&& rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Kolkata

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Add cron schedule and startup script
COPY docker/cron/imd-cron /etc/cron.d/imd-cron
RUN chmod 0644 /etc/cron.d/imd-cron && crontab /etc/cron.d/imd-cron

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]