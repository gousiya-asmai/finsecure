#!/usr/bin/env bash
set -o errexit

echo "🔧 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "🧩 Forcing migration detection..."
python manage.py makemigrations users assistance --noinput || true

echo "🗃️ Applying all migrations (even fake mismatches)..."
python manage.py migrate --fake-initial --noinput

echo "🎨 Collecting static files..."
python manage.py collectstatic --noinput

echo "✅ Build completed successfully!"
