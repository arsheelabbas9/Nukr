from django.apps import AppConfig

class MarketplaceConfig(AppConfig):
    """
    Titanium Marketplace Configuration.
    This class initializes the application and registers all critical signal listeners.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'marketplace'

    def ready(self):
        # 🛡️ TITANIUM SIGNAL REGISTRY 🛡️
        # =========================================================
        # This method is called automatically when Django starts.
        # It imports 'marketplace.signals', which activates:
        #   1. Welcome Emails (Template 1)
        #   2. Order Confirmations (Template 4)
        #   3. New Store Alerts (Template 7)
        #   4. 🆕 Chat Message Notifications (with Smart Links)
        # =========================================================
        
        try:
            import marketplace.signals
            # print("✅ Titanium Signals Loaded: Welcome, Orders, Store & Chat Notifications active.")
        except ImportError:
            pass