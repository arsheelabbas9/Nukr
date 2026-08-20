import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

# Load .env file for local development
load_dotenv()

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================================
# 🔐 CORE SECURITY SETTINGS
# ==========================================

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-fallback-key-change-this')

# SECURITY WARNING: don't run with debug turned on in production!
# Make sure your .env file has DEBUG=True for local development
DEBUG = os.getenv('DEBUG', 'False') == 'True'

# --- 🛡️ TITANIUM HOST & ORIGIN GATEKEEPER ---
# 🚀 VERCEL FIX: We use '*' to allow Vercel's dynamic URLs to work immediately.
# This prevents the "DisallowedHost" error you saw earlier.
ALLOWED_HOSTS = ['*']

# Critical for preventing 403 Forbidden errors during Signup and Login
CSRF_TRUSTED_ORIGINS = [
    'https://nukr.store', 
    'https://www.nukr.store',
    'https://nukr-market.vercel.app',  # Added for your Vercel deployment
    'https://*.vercel.app'             # Wildcard for any Vercel preview URL
]

# --- 🔒 LIVE HTTPS SECURITY ---
# Only enable these in production (when DEBUG is False) to avoid breaking localhost
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
else:
    # Local development settings (Relaxed security to allow images to load)
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False


# ==========================================
# 🧩 APPLICATION DEFINITION
# ==========================================
INSTALLED_APPS = [
    # 🚨 CRITICAL: Added 'nukr_core' so the app config works
    'nukr_core',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.sites', 
    'whitenoise.runserver_nostatic', 
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    
    # 🛡️ Identity Gatekeeper (Allauth Core)
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google', 

    # 📧 Email API Integration (Brevo)
    'anymail',

    # ☁️ Cloud Storage
    'cloudinary',
    'cloudinary_storage',
    
    # 🏬 Nukr Marketplace Apps
    'marketplace',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware', 
    'whitenoise.middleware.WhiteNoiseMiddleware', 
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'allauth.account.middleware.AccountMiddleware', 
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'nukr_core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], 
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request', 
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'nukr_core.wsgi.application'


# ==========================================
# 🗄️ DATABASE ORCHESTRATOR (Supabase)
# ==========================================
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True,
        )
    }
else:
    # Fallback to SQLite only if no Database URL is found (Safety Net)
    if not DEBUG:
        raise ValueError("❌ FATAL: DATABASE_URL is missing in Production!")
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# ==========================================
# 🔑 AUTHENTICATION & IDENTITY
# ==========================================
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

SITE_ID =1

# --- 🛡️ IDENTITY GATEKEEPER BEHAVIOR ---
LOGIN_URL = 'account_login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

ACCOUNT_AUTHENTICATION_METHOD = 'email' 
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True       
ACCOUNT_USERNAME_REQUIRED = True   
ACCOUNT_EMAIL_VERIFICATION = 'mandatory' 
ACCOUNT_CONFIRM_EMAIL_ON_GET = True       
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True 
ACCOUNT_PREVENT_ENUMERATION = False
ACCOUNT_FORMS = {'login': 'nukr_core.forms.TitaniumLoginForm'}

ACCOUNT_SESSION_REMEMBER = True
SOCIALACCOUNT_LOGIN_ON_GET = True

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'}
    }
}


# ==========================================
# 📧 BREVO API & EMAIL SETTINGS
# ==========================================
ANYMAIL = {
    "BREVO_API_KEY": os.getenv("BREVO_API_KEY"),
    "SEND_DEFAULTS": {
        # 🚨 CLEANED: Removed 'reply_to' to fix the crash.
        "tags": ["nukr-system"],
    }
}
EMAIL_BACKEND = "anymail.backends.brevo.EmailBackend"

# --- Nukr Identities (Senders) ---
# The email client will automatically reply to the email inside <...>.

NUKR_HELLO_EMAIL = 'Nukr <hello@nukr.store>'
NUKR_SUPPORT_EMAIL = 'Nukr <support@nukr.store>'
NUKR_ORDER_EMAIL = 'Nukr <orders@nukr.store>'
NUKR_UPDATES_EMAIL = 'Nukr <updates@nukr.store>'

DEFAULT_FROM_EMAIL = NUKR_HELLO_EMAIL 
SERVER_EMAIL = NUKR_SUPPORT_EMAIL


# ==========================================
# 🔗 SMART DOMAIN (For Chat Notifications)
# ==========================================
# This logic is used by signals.py to generate the correct chat link
# whether you are on Localhost or Production.
SITE_DOMAIN = os.getenv('SITE_URL', 'http://127.0.0.1:8000')


# ==========================================
# 📦 STATIC & MEDIA ORCHESTRATION
# ==========================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Explicitly tell Django where to find your app's static files
STATICFILES_DIRS = [
    BASE_DIR / 'marketplace' / 'static',
]

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.getenv('CLOUDINARY_API_KEY'),
    'API_SECRET': os.getenv('CLOUDINARY_API_SECRET'),
}

STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",  # <--- CHANGED
    },
}
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'


# ==========================================
# 🛠️ SYSTEM CONFIGURATION
# ==========================================
# Password Standards
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Karachi'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

ACCOUNT_ADAPTER = 'nukr_core.adapters.NukrAccountAdapter'