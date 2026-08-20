from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Store, Product, ProductImage, 
    ProductVariantType, ProductVariantItem, 
    Order, DiscountCode, StoreVerification,
    Review, Collection, CouponUsage,
    UserProfile, StoreWallet, Conversation, Message
)

# ==========================================
# 1. INLINES (Helper sections inside other pages)
# ==========================================
class ProductImageInline(admin.TabularInline):
    """Allows uploading gallery images directly inside the Product page."""
    model = ProductImage
    extra = 1

class VariantItemInline(admin.TabularInline):
    """Allows adding sizes/colors directly inside the Variant Type page."""
    model = ProductVariantItem
    extra = 1

class VariantTypeInline(admin.StackedInline):
    """Allows creating Variant Types (Size, Color) inside the Product page."""
    model = ProductVariantType
    extra = 0

class MessageInline(admin.TabularInline):
    """Allows viewing chat messages directly inside the Conversation page."""
    model = Message
    extra = 0
    readonly_fields = ('sender', 'text', 'image', 'timestamp')
    can_delete = False
    ordering = ('timestamp',)

# ==========================================
# 2. MAIN ADMINS (Store & Products)
# ==========================================

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    # 💎 FIXED: Added 'card_payments_enabled' to list_display so it can be edited
    list_display = ('name', 'owner', 'city', 'is_verified', 'card_payments_enabled', 'created_at')
    list_filter = ('is_verified', 'city', 'deliver_nationwide', 'card_payments_enabled')
    search_fields = ('name', 'owner__username')
    list_editable = ('is_verified', 'card_payments_enabled') # 🛡️ Quick toggle for verification & cards

@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'created_at')
    list_filter = ('store',)
    search_fields = ('name', 'store__name')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # 🚨 ADDED: 'collection' to list display
    list_display = ('name', 'store', 'collection', 'price', 'stock', 'is_available', 'is_active')
    list_filter = ('store', 'is_available', 'is_active', 'collection')
    search_fields = ('name', 'store__name')
    # This puts Images & Variants inside the Product page
    inlines = [ProductImageInline, VariantTypeInline]

@admin.register(ProductVariantType)
class VariantTypeAdmin(admin.ModelAdmin):
    inlines = [VariantItemInline]

# ==========================================
# 3. ORDER MANAGEMENT (💎 UPDATED: Unified ID)
# ==========================================

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # 💎 Display 'order_group_id' first
    list_display = ('order_group_id', 'id', 'customer', 'store', 'product', 'status', 'total_price', 'is_paid', 'created_at')
    list_filter = ('status', 'is_paid', 'created_at', 'store')
    search_fields = ('order_group_id', 'id', 'customer__username', 'product__name', 'store__name')
    readonly_fields = ('created_at', 'order_group_id', 'safepay_tracker')
    
    # Organize fields for easy reading
    fieldsets = (
        ('Order Identity', {
            'fields': ('order_group_id', 'status', 'is_paid')
        }),
        ('Product Details', {
            'fields': ('store', 'customer', 'product', 'selected_variant', 'quantity')
        }),
        ('Financials', {
            'fields': ('subtotal_price', 'delivery_fee', 'discount_amount', 'total_price')
        }),
        ('Shipping & Payment', {
            'fields': ('shipping_name', 'shipping_email', 'shipping_phone', 'shipping_address', 'payment_method_selected', 'payment_screenshot', 'safepay_tracker')
        }),
    )

# ==========================================
# 4. CHAT SYSTEM (💎 NEW ADMINS)
# ==========================================

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'store', 'updated_at')
    list_filter = ('updated_at',)
    search_fields = ('customer__username', 'store__name')
    inlines = [MessageInline] # 💎 View messages inside the conversation

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'conversation', 'short_text', 'has_image', 'timestamp', 'is_read')
    list_filter = ('is_read', 'timestamp')
    search_fields = ('text', 'sender__username')
    
    def short_text(self, obj):
        return obj.text[:50] + "..." if obj.text else ""
    
    def has_image(self, obj):
        return bool(obj.image)
    has_image.boolean = True

# ==========================================
# 5. USER & WALLET
# ==========================================

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'address')
    search_fields = ('user__username', 'phone')

@admin.register(StoreWallet)
class StoreWalletAdmin(admin.ModelAdmin):
    list_display = ('store', 'current_balance', 'total_earnings', 'updated_at')
    search_fields = ('store__name',)

# ==========================================
# 6. REVIEWS & COUPONS
# ==========================================

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'rating', 'store', 'product', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('comment', 'store__name', 'product__name')

@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'store', 'value', 'discount_type', 'active', 'valid_until')
    list_filter = ('active', 'discount_type', 'store')
    search_fields = ('code', 'store__name')

@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ('coupon', 'email', 'used_at')
    search_fields = ('email', 'coupon__code')
    readonly_fields = ('used_at',)

# ==========================================
# 🛡️ 7. STORE VERIFICATION CENTER
# ==========================================
@admin.register(StoreVerification)
class StoreVerificationAdmin(admin.ModelAdmin):
    # What you see in the list
    list_display = ('store', 'full_name', 'cnic_number', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('store__name', 'full_name', 'cnic_number', 'email')
    readonly_fields = ('created_at',)
    
    # Organize the layout so it's easy for you to review documents
    fieldsets = (
        ('Application Status', {
            'fields': ('store', 'status')
        }),
        ('Applicant Details', {
            'fields': ('full_name', 'cnic_number', 'contact_number', 'email', 'office_address')
        }),
        ('Documents (Review Carefully)', {
            'fields': ('cnic_front', 'cnic_back'),
            'description': 'Please verify that the name on the CNIC matches the applicant details.'
        }),
    )

    # 🛡️ CUSTOM ACTIONS: One-click Approve/Reject
    actions = ['approve_applications', 'reject_applications']

    def approve_applications(self, request, queryset):
        # Automatically updates the Store's is_verified status via model logic
        for app in queryset:
            app.status = 'approved'
            app.save()
        self.message_user(request, "Selected applications have been APPROVED. Stores are now verified.")
    approve_applications.short_description = "✅ Approve selected applications"

    def reject_applications(self, request, queryset):
        queryset.update(status='rejected')
        self.message_user(request, "Selected applications have been REJECTED.")
    reject_applications.short_description = "❌ Reject selected applications"