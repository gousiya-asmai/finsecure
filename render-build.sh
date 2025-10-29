#!/usr/bin/env bash
# ---------------------------------------------
# Render build script for FinSecure Django app
# ---------------------------------------------
# Exit immediately if a command exits with a non-zero status
set -o errexit

echo "🔧 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "🗃️ Applying database migrations..."
python manage.py migrate --noinput

echo "🎨 Collecting static files..."
python manage.py collectstatic --noinput

echo "✅ Build completed successfully!"

pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
# Other commands...
