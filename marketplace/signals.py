import threading
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import EmailMessage, send_mail
from django.conf import settings
from django.urls import reverse
from allauth.account.signals import email_confirmed
from .models import Order, Store, Message

# ==============================================================================
# 🛡️ CONFIGURATION & HELPERS
# ==============================================================================

# 💎 LIVE DOMAIN FIX: This ensures links are ALWAYS correct in emails.
# Even if the server thinks it's localhost, this forces the real domain.
LIVE_DOMAIN = "https://nukr.store"

def get_reply_address(full_sender_string):
    """
    Helper: Extracts 'hello@nukr.store' from 'Nukr <hello@nukr.store>'
    Ensures Reply-To always matches the Sender dynamically.
    """
    if "<" in full_sender_string:
        return full_sender_string.split("<")[1].strip(">")
    return full_sender_string

# ==============================================================================
# 1. WELCOME EMAIL (Template 1)
# Triggered: After user clicks "Verify Email" link
# ==============================================================================
@receiver(email_confirmed)
def send_welcome_email(request, email_address, **kwargs):
    user = email_address.user
    
    # 1. Get Sender from Settings
    sender = settings.NUKR_HELLO_EMAIL
    
    # 2. Extract Reply-To Dynamically
    reply_to_addr = get_reply_address(sender)

    msg = EmailMessage(
        to=[user.email],
        from_email=sender,
        reply_to=[reply_to_addr] 
    )
    msg.template_id = 1
    msg.merge_global_data = {'NAME': user.username}
    
    try:
        msg.send()
        print(f"🎉 Signal: Sent Welcome (Temp 1) to {user.email}")
    except Exception as e:
        print(f"❌ Signal Error (Welcome): {e}")


# ==============================================================================
# 2. ORDER CONFIRMATION (Template 4)
# Triggered: When a customer places an order
# ==============================================================================
@receiver(post_save, sender=Order)
def send_order_confirmation(sender, instance, created, **kwargs):
    if created:
        # 🚨 FIX: Use 'customer' linkage to avoid crashes
        user = instance.customer 
        
        # 1. Get Sender from Settings
        sender = settings.NUKR_ORDER_EMAIL
        
        # 2. Extract Reply-To Dynamically
        reply_to_addr = get_reply_address(sender)

        # 3. Prepare Data
        items_summary = f"{instance.quantity}x {instance.product.name} ({instance.selected_variant})"
        
        # Safe fallback for delivery time if store is missing
        delivery_time = getattr(instance.product.store, 'delivery_time', "3-5 Days")

        params = {
            'NAME': user.username,
            'ORDER_ID': str(instance.id),
            'TOTAL': str(instance.total_price) if hasattr(instance, 'total_price') else "0",
            'ITEMS_SUMMARY': items_summary,
            'ADDRESS': f"{instance.shipping_address}, {instance.shipping_city}",
            'DELIVERY_TIME': delivery_time,
            'STORE_NAME': instance.product.store.name
        }

        msg = EmailMessage(
            to=[user.email],
            from_email=sender,
            reply_to=[reply_to_addr] 
        )
        msg.template_id = 4
        msg.merge_global_data = params

        try:
            msg.send()
            print(f"📦 Signal: Sent Order Conf (Temp 4) to {user.email}")
        except Exception as e:
            print(f"❌ Signal Error (Order): {e}")


# ==============================================================================
# 3. STORE CREATED (Template 7)
# Triggered: When a vendor creates a new store
# ==============================================================================
@receiver(post_save, sender=Store)
def send_store_created_alert(sender, instance, created, **kwargs):
    if created:
        user = instance.owner 
        
        # 1. Get Sender (Hello/Support Team)
        sender = settings.NUKR_HELLO_EMAIL
        
        # 2. Extract Reply-To
        reply_to_addr = get_reply_address(sender)

        params = {
            'NAME': user.username,
            'STORE_NAME': instance.name
        }

        msg = EmailMessage(
            to=[user.email],
            from_email=sender,
            reply_to=[reply_to_addr] 
        )
        msg.template_id = 7
        msg.merge_global_data = params

        try:
            msg.send()
            print(f"🏪 Signal: Sent Store Created (Temp 7) to {user.email}")
        except Exception as e:
            print(f"❌ Signal Error (Store): {e}")


# ==============================================================================
# 4. CHAT NOTIFICATION (The Critical Fix)
# Triggered: When a new message is sent in Chat
# ==============================================================================
@receiver(post_save, sender=Message)
def send_message_notification(sender, instance, created, **kwargs):
    """
    Sends an email notification when a new message is received.
    Runs in a background thread to keep the chat fast.
    """
    if created:
        def send_email_thread():
            try:
                message = instance
                conversation = message.conversation
                sender_user = message.sender
                
                # 1. Identify Recipient (Who gets the alert?)
                if sender_user == conversation.customer:
                    recipient = conversation.store.owner
                    recipient_name = conversation.store.name
                else:
                    recipient = conversation.customer
                    recipient_name = recipient.username

                # 💎 2. BUILD THE CORRECT LINK (Hardcoded Domain)
                # This fixes the "http://127.0.0.1:8000" issue permanently.
                chat_path = reverse('chat_room', args=[conversation.id])
                chat_url = f"{LIVE_DOMAIN}{chat_path}"

                # 3. Email Content
                subject = f"New Message from {sender_user.username} | Nukr"
                
                email_body = (
                    f"Hello {recipient_name},\n\n"
                    f"You have received a new message on Nukr.\n\n"
                    f"From: {sender_user.username}\n"
                    f"Message: \"{message.text if message.text else '[Image Sent]'}\"\n\n"
                    f"Click here to reply immediately:\n"
                    f"{chat_url}\n\n"  # <--- This will now be https://nukr.store/...
                    f"-----------------------------------------\n"
                    f"This is an automated notification from Nukr Marketplace."
                )

                # 4. Send via Standard Django Mail (Handled by Vercel/Brevo)
                if recipient.email:
                    send_mail(
                        subject,
                        email_body,
                        settings.DEFAULT_FROM_EMAIL,
                        [recipient.email],
                        fail_silently=True, 
                    )
                    print(f"💬 Signal: Chat Notification sent to {recipient.email}")

            except Exception as e:
                print(f"❌ Signal Error (Chat): {e}")

        # Run in separate thread
        email_thread = threading.Thread(target=send_email_thread)
        email_thread.start()