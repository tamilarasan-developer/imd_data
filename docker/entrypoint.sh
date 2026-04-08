#!/bin/sh
set -e

touch /var/log/imd-cron.log

echo "[startup] Cron scheduler started. Job runs daily at 16:00 Asia/Kolkata."
cron
exec tail -F /var/log/imd-cron.log
