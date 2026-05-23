#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/home/ava/staging/backend
BRANCH=develop
export DJANGO_SETTINGS_MODULE=avapharmacy.settings.production

cd "$APP_DIR"
git remote get-url origin | grep -q 'github.com-backend' && git remote set-url origin "$(git remote get-url origin | sed 's/github.com-backend/github.com/g')" || true
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"

source venv/bin/activate
pip install -r requirements.txt

python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check --deploy

sudo /usr/sbin/apache2ctl configtest
sudo /bin/systemctl reload apache2
