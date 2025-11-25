#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
rm -f db.sqlite3
echo "Checking migration files..."
ls -R expenses/migrations
echo "Running makemigrations just in case..."
python manage.py makemigrations expenses
python manage.py migrate
