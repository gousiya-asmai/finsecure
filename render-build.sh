#!/usr/bin/env bash
# ---------------------------------------------
# Render build script for FinSecure Django app
# ---------------------------------------------
set -o errexit  # Exit immediately if a command fails

echo "🔧 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "🧩 Making migrations..."
python manage.py makemigrations --noinput || true

echo "🗃️ Applying database migrations..."
python manage.py migrate --noinput

echo "🎨 Collecting static files..."
python manage.py collectstatic --noinput

echo "✅ Build completed successfully!"
