"""
WSGI config for nukr_core project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nukr_core.settings')

# This is standard Django
application = get_wsgi_application()

# 🚀 VERCEL FIX:
# Vercel's serverless runtime looks for a variable named 'app' by default.
app = application