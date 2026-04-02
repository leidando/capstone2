#!/usr/bin/env bash
# Render Build Script for CSWDO Management System
set -o errexit

# Use the virtualenv provided by Render
pip install --upgrade pip
pip install -r requirements.txt

# Ensure we're using binary versions of critical packages if possible
pip install --only-binary :all: psycopg2-binary || true

python manage.py collectstatic --no-input
python manage.py migrate
python manage.py createsuperuser --no-input || true
