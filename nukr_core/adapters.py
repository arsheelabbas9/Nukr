from allauth.account.adapter import DefaultAccountAdapter
from django.core.mail import EmailMessage
from django.conf import settings

class NukrAccountAdapter(DefaultAccountAdapter):
    """
    Titanium Adapter: Connects Allauth system events (Reset, Verify)
    directly to Brevo Templates with correct Reply-To headers.
    """

    def send_mail(self, template_prefix, email, context):
        
        # 1. EMAIL VERIFICATION (Security) -> Template 3
        if 'email_confirmation' in template_prefix:
            params = {
                'NAME': context['user'].username,
                'VERIFY_URL': context.get('activate_url')
            }
            # Send as Support, Force Reply to Support
            self._trigger_brevo(email, 3, params, settings.NUKR_SUPPORT_EMAIL, 'support@nukr.store')
            return

        # 2. PASSWORD RESET (Security) -> Template 2
        if 'password_reset' in template_prefix:
            reset_url = context.get('password_reset_url') or context.get('url')
            params = {
                'NAME': context['user'].username,
                'RESET_URL': reset_url
            }
            # Send as Support, Force Reply to Support
            self._trigger_brevo(email, 2, params, settings.NUKR_SUPPORT_EMAIL, 'support@nukr.store')
            return

        # ❌ REMOVED WELCOME EMAIL LOGIC
        # This is now handled in marketplace/signals.py so it sends ONLY AFTER verification.

        # Fallback for standard Django emails
        super().send_mail(template_prefix, email, context)

    def _trigger_brevo(self, to_email, template_id, params, sender, reply_to_email):
        """
        Clean wrapper to send a Brevo Template.
        Forces the Reply-To to ensure it matches the sender identity.
        """
        msg = EmailMessage(
            to=[to_email],
            from_email=sender,
            reply_to=[reply_to_email] # 🚨 FORCED: Ensures reply goes to Support
        )
        msg.template_id = template_id
        msg.merge_global_data = params
        
        try:
            msg.send()
            print(f"✅ Adapter: Triggered Template {template_id} to {to_email}")
        except Exception as e:
            print(f"❌ Adapter Error (Template {template_id}): {e}")