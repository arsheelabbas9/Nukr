#!/usr/bin/env bash
# exit on error
set -o errexit

echo "--- 🛡️ Starting Titanium Build Process ---"

# 1. Install all project dependencies
echo "--- 📦 Installing requirements ---"
pip install -r requirements.txt

# 2. Gather static files (CSS/JS) for the Nukr frontend
echo "--- 🎨 Collecting static files ---"
python manage.py collectstatic --no-input

# 3. Apply database migrations to the Supabase cluster
echo "--- 🗄️ Running migrations ---"
python manage.py migrate

echo "--- ✅ Build Successful: Nukr is ready to go live ---"