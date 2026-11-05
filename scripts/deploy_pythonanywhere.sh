#!/usr/bin/env bash
# Update the live site on PythonAnywhere. Run in a PythonAnywhere Bash
# console from the clone, with the web app's virtualenv active:
#
#   cd ~/11_Beacon && workon <venv> && bash scripts/deploy_pythonanywhere.sh
#
# Then press Reload on the Web tab (or touch the WSGI file, printed below).
set -euo pipefail

SETTINGS=beacon_core.settings.production
cd "$(dirname "$0")/.."

echo "==> 1/6 Back up the live database"
backup=~/db-live-$(date +%F-%H%M).sqlite3
cp db.sqlite3 "$backup"
echo "    saved to $backup"

echo "==> 2/6 Pull the latest code (keeping the live database)"
git checkout -- db.sqlite3 2>/dev/null || true
git pull --ff-only origin main
cp "$backup" db.sqlite3

echo "==> 3/6 Install dependencies (no torch: too big for this host)"
pip install --quiet -r requirements-production.txt

echo "==> 4/6 Apply database migrations"
python manage.py migrate --noinput --settings=$SETTINGS
# The shared cache that rate limits and the AI circuit breaker use.
python manage.py createcachetable --settings=$SETTINGS

echo "==> 5/6 Collect static files"
python manage.py collectstatic --noinput --settings=$SETTINGS > /dev/null

echo "==> 6/6 Check the configuration"
python manage.py check --deploy --fail-level ERROR --settings=$SETTINGS
python - <<'PY'
import os
for name in ("DJANGO_SECRET_KEY", "LUMEN_API_KEY", "GOOGLE_OAUTH_CLIENT_ID", "SITE_URL"):
    from dotenv import dotenv_values
    present = bool(os.environ.get(name) or dotenv_values(".env").get(name))
    print(f"    {name:24} {'set' if present else 'MISSING'}")
PY

wsgi=$(ls /var/www/*_wsgi.py 2>/dev/null | head -1 || true)
echo
echo "Done. Reload the web app (Web tab > Reload)${wsgi:+, or: touch $wsgi}"
echo "Then open https://<your-domain>/healthz/ and expect {\"ok\": true, ...}"
