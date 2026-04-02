#!/usr/bin/env bash
# Render Build Script for CSWDO Management System
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate
