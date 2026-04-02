#!/bin/sh
set -e

touch /var/log/imd-cron.log

echo "[startup] Cron scheduler started. Job runs daily at 09:30 Asia/Kolkata."
cron
exec tail -F /var/log/imd-cron.log
