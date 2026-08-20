"""
Nukr URL Configuration - TITANIUM EDITION (Stable Build)

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
"""
import os
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from marketplace import views 

# ==============================================================================
# 🛡️ GLOBAL CONFIGURATION
# ==============================================================================

# Custom Sender Identity for Authentication Emails (Password Reset)
# This ensures users see "Nukr" instead of "webmaster@localhost"
SUPPORT_IDENTITY = "Nukr <support@nukr.store>"

urlpatterns = [
    
    # ==========================================
    # 1. SUPER ADMIN PANEL
    # ==========================================
    path('admin/', admin.site.urls),

    # ==========================================
    # 2. LEGAL, HELP & STATIC PAGES
    # ==========================================
    path('help/', views.help_center, name='help_center'),
    path('privacy/', views.privacy_policy, name='privacy_policy'),
    path('terms/', views.terms_of_service, name='terms_of_service'),

    # ==========================================
    # 3. USER ACCOUNT & PROFILE
    # ==========================================
    path('account/settings/', views.account_settings, name='account_settings'),
    path('account/orders/', views.my_orders, name='my_orders'),

    # ==========================================
    # 💎 4. NUKR TALASH (REVERSE MARKETPLACE)
    # ==========================================
    # Buyer: Post a request
    path('talash/new/', views.create_talash, name='create_talash'),
    
    # Seller: View leads (Filtered by Category & City)
    path('talash/feed/', views.talash_feed, name='talash_feed'),
    
    # Seller: Respond to a lead (Auto-creates chat)
    path('talash/respond/<int:request_id>/', views.respond_to_talash, name='respond_to_talash'),

    # ==========================================
    # 💎 5. CHAT SYSTEM (REAL-TIME MESSAGING)
    # ==========================================
    # List all conversations (Buyer & Seller view)
    path('chats/', views.my_chats, name='my_chats'),
    
    # Start or Open a Chat with a Store
    path('chat/start/<int:store_id>/', views.start_chat, name='start_chat'),
    
    # The Chat Room Interface
    path('chat/room/<int:conversation_id>/', views.chat_room, name='chat_room'),
    
    # Deletion Logic
    path('chat/delete/<int:conversation_id>/', views.delete_conversation, name='delete_conversation'),
    
    # --- AJAX API ENDPOINTS (For JS Fetch) ---
    path('api/chat/<int:conversation_id>/send/', views.send_message_api, name='send_message_api'),
    path('api/chat/<int:conversation_id>/get/', views.get_messages_api, name='get_messages_api'),
    path('api/message/delete/<int:message_id>/', views.delete_message_api, name='delete_message_api'),

    # ==========================================
    # 6. MARKETPLACE BROWSING (BUYER)
    # ==========================================
    # Homepage (Mall View)
    path('', views.mall_home, name='home'),
    
    # Specific Store Front
    path('store/<int:store_id>/', views.store_detail, name='store_detail'),
    
    # Product Details
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),

    # ==========================================
    # 7. VENDOR DASHBOARD & STORE MANAGEMENT
    # ==========================================
    # Onboarding
    path('store/create/', views.create_store, name='create_store'),
    
    # Dashboard Routing (Redirects to correct store if multiple)
    path('store/dashboard/', views.dashboard_redirect, name='dashboard_redirect'),
    
    # Main Dashboard
    path('store/<int:store_id>/dashboard/', views.store_dashboard, name='store_dashboard'),
    
    # Settings & Edits
    path('store/<int:store_id>/edit/', views.edit_store, name='edit_store'),
    
    # Verification Request
    path('store/<int:store_id>/verify/', views.request_verification, name='request_verification'),

    # ==========================================
    # 8. PRODUCT INVENTORY MANAGEMENT
    # ==========================================
    
    # 💎 CRITICAL FIX: Explicitly matches the template call {% url 'add_product_to_store' store.id %}
    # This prevents the NoReverseMatch (4,) error.
    path('store/<int:store_id>/add-product/', views.add_product_to_store, name='add_product_to_store'),
    
    # Legacy/Fallback Add URL (Optional but kept for safety)
    path('product/add/', views.add_product, name='add_product'), 
       
    # Edit Existing Product
    path('product/<int:product_id>/edit/', views.edit_product, name='edit_product'),

    # ==========================================
    # 9. MARKETING TOOLS (COUPONS & COLLECTIONS)
    # ==========================================
    # Collections
    path('store/<int:store_id>/collections/add/', views.add_collection, name='add_collection'),
    path('collection/<int:collection_id>/delete/', views.delete_collection, name='delete_collection'),

    # Coupons
    path('store/<int:store_id>/coupons/', views.manage_coupons, name='manage_coupons'),
    path('coupon/<int:coupon_id>/delete/', views.delete_coupon, name='delete_coupon'),
    path('store/<int:store_id>/coupon/apply/', views.apply_coupon, name='apply_coupon'),

    # ==========================================
    # 10. ORDER FULFILLMENT (VENDOR SIDE)
    # ==========================================
    # View Order Details
    path('order/<int:order_id>/manage/', views.manage_order, name='manage_order'),
    
    # Update Status (Shipped, Delivered, Cancelled)
    path('order/<int:order_id>/update-status/', views.update_order_status, name='update_order_status'),

    # ==========================================
    # 11. REVIEWS & RATINGS
    # ==========================================
    path('store/<int:store_id>/review/', views.store_review, name='store_review'),
    path('product/<int:product_id>/review/', views.product_review, name='product_review'),
    path('review/<int:review_id>/delete/', views.delete_review, name='delete_review'),

    # ==========================================
    # 12. CART & CHECKOUT ENGINE
    # ==========================================
    # Add Item
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    
    # View Cart
    path('cart/<int:store_id>/', views.view_cart, name='view_cart'),
    
    # Manipulate Cart
    path('cart/update/<int:store_id>/<str:item_key>/<str:action>/', views.update_cart_quantity, name='update_cart_quantity'),
    path('cart/remove/<int:store_id>/<str:item_key>/', views.remove_from_cart, name='remove_from_cart'),
    
    # Checkout Process
    path('checkout/<int:store_id>/', views.checkout, name='checkout'),
    
    # "Buy Now" (Skip Cart)
    path('checkout/direct/<int:product_id>/', views.checkout_direct, name='checkout_direct'),
    
    # Order Confirmation
    path('order/success/<int:order_id>/', views.order_success_view, name='order_success_view'),

    # ==========================================
    # 13. AUTHENTICATION (ALLAUTH)
    # ==========================================
    path('accounts/', include('allauth.urls')),

    # ==========================================
    # 14. PASSWORD RESET (CUSTOM BRANDING)
    # ==========================================
    # We override standard auth views to use our custom templates and Sender Identity
    
    path('reset_password/', 
         auth_views.PasswordResetView.as_view(
             template_name="accounts/password_reset.html",
             from_email=SUPPORT_IDENTITY
         ), 
         name="reset_password"),

    path('reset_password_sent/', 
        auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_sent.html"), 
        name="password_reset_done"),

    path('reset/<uidb64>/<token>/', 
        auth_views.PasswordResetConfirmView.as_view(template_name="accounts/password_reset_form.html"), 
        name="password_reset_confirm"),

    path('reset_password_complete/', 
        auth_views.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_done.html"), 
        name="password_reset_complete"),
    # Buyer: Post a request
    path('talash/new/', views.create_talash, name='create_talash'),
    
    # 💎 NEW: Buyer delete request
    path('talash/delete/<int:request_id>/', views.delete_talash, name='delete_talash'),

    # Seller: View leads
    path('talash/feed/', views.talash_feed, name='talash_feed'),
    # ... inside Chat System section ...
    path('api/chat/<int:conversation_id>/offer/', views.create_custom_offer, name='create_custom_offer'),
]

# ==========================================
# 15. MEDIA SERVING (DEV MODE ONLY)
# ==========================================
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)