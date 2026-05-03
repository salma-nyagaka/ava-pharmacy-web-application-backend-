#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/home/ava/production/backend
BRANCH=${PRODUCTION_BRANCH:-main}
export DJANGO_SETTINGS_MODULE=avapharmacy.settings.production

cd "$APP_DIR"
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"

source venv/bin/activate
pip install -r requirements.txt

python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check --deploy

sudo systemctl restart avapharmacy-production
