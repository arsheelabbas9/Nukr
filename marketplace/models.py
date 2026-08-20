import uuid
import math
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Avg, Sum
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.text import slugify

# ==============================================================================
# 0. GLOBAL CONSTANTS & CONFIGURATION
# ==============================================================================

# 💎 CATEGORY CHOICES (Global Variable)
# Used by 'Store' and 'ProductRequest' for the Talash Engine.
CATEGORY_CHOICES = [
    ('FASHION', 'Fashion & Wearables'),
    ('TECH', 'Electronics & Gadgets'),
    ('HOME', 'Home & Lifestyle'),
    ('BEAUTY', 'Health & Beauty'),
    ('AUTO', 'Automotive & Parts'),
    ('FOOD', 'Food & Groceries'),
    ('OTHER', 'Other / Custom Request'),
]

# ==============================================================================
# 🛡️ TITANIUM MANAGERS (Advanced Filtering Logic)
# ==============================================================================

class LocalMarketManager(models.Manager):
    """
    Titanium Logic: Automatically filters results by the user's selected city 
    retrieved from the 'nukr_city' cookie.
    """
    def local(self, request):
        city = request.COOKIES.get('nukr_city')
        if city:
            return self.get_queryset().filter(city__iexact=city)
        return self.get_queryset()

    def verified(self):
        return self.get_queryset().filter(is_verified=True)

class LocalProductManager(models.Manager):
    """
    Filters products based on the store's location.
    """
    def local(self, request):
        city = request.COOKIES.get('nukr_city')
        if city:
            return self.get_queryset().filter(store__city__iexact=city)
        return self.get_queryset()

# ==============================================================================
# 1. THE STORE (Vendor Entity)
# ==============================================================================

class Store(models.Model):
    # Relationship: A User can own multiple stores
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stores')
    
    # --- 1. Identity & Branding ---
    name = models.CharField(max_length=255, unique=True, verbose_name="Store Name")
    slug = models.SlugField(max_length=255, unique=True, blank=True, null=True, help_text="Auto-generated for URLs")
    description = models.TextField(verbose_name="About the Store")
    image = models.ImageField(upload_to='store_logos/', blank=True, null=True, verbose_name="Store Logo")
    
    # 💎 NEW: Store Category (Critical for Talash Logic)
    # This acts as the routing key for leads. A 'Mechanic' gets 'AUTO' leads.
    category = models.CharField(
        max_length=20, 
        choices=CATEGORY_CHOICES, 
        default='OTHER',
        verbose_name="Store Category"
    )

    # --- 2. Location & Logistics ---
    city = models.CharField(max_length=100, verbose_name="Base City") 
    
    # Nationwide Logic
    deliver_nationwide = models.BooleanField(default=False, verbose_name="Delivers Across Pakistan")
    secondary_cities = models.TextField(blank=True, null=True, help_text="Comma-separated list (e.g. Lahore, Islamabad)")
    
    # Delivery Configuration
    delivery_time = models.CharField(
        max_length=50, 
        default="3-5 Business Days",
        help_text="e.g., 2-3 Days, Same Day Delivery"
    )
    delivery_charges = models.DecimalField(
        max_digits=10, 
        decimal_places=0, 
        default=0, 
        verbose_name="Standard Delivery Fee"
    )

    # --- 3. Policies ---
    policy = models.TextField(blank=True, null=True, help_text="Return & Privacy Policy")

    # --- 4. Social & External ---
    facebook_link = models.URLField(blank=True, null=True, help_text="Full Facebook Page URL")
    instagram_link = models.URLField(blank=True, null=True, help_text="Full Instagram Profile URL")

    # --- 5. Financials & Banking ---
    PAYMENT_CHOICES = [
        ('COD', 'Cash on Delivery Only'),
        ('OL', 'Online Transfer / Bank Deposit'),
        ('BOTH', 'Both COD and Online Transfer'),
    ]
    payment_method = models.CharField(max_length=4, choices=PAYMENT_CHOICES, default='COD')
    
    # SafePay Integration Toggle
    card_payments_enabled = models.BooleanField(default=False, verbose_name="Accept Card Payments")

    # Bank Vault (Encrypted Conceptually)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    payment_account_title = models.CharField(max_length=100, blank=True, null=True)
    payment_account_number = models.CharField(max_length=100, blank=True, null=True)

    # --- 6. System Status ---
    is_verified = models.BooleanField(default=False, verbose_name="Verified Badge")
    is_featured = models.BooleanField(default=False, verbose_name="Featured Store")
    created_at = models.DateTimeField(auto_now_add=True)

    # Managers
    objects = models.Manager() # Standard
    titanium = LocalMarketManager() # Location-aware

    class Meta:
        ordering = ['-is_verified', '-created_at']
        verbose_name = "Store"
        verbose_name_plural = "Stores"

    # --- Methods ---
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('store_detail', args=[str(self.id)])

    def average_rating(self):
        """Calculates dynamic rating based on reviews."""
        avg = self.reviews.aggregate(Avg('rating'))['rating__avg']
        return round(avg, 1) if avg else 0

    def review_count(self):
        return self.reviews.count()

    def __str__(self):
        return f"{self.name} ({self.city})"

# ==============================================================================
# 2. STORE VERIFICATION (KYC Module)
# ==============================================================================

class StoreVerification(models.Model):
    """
    Titanium Module: Handles the logic for store verification requests.
    Stores sensitive data (CNIC) separately from the public Store model.
    """
    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    store = models.OneToOneField(Store, on_delete=models.CASCADE, related_name='verification')
    
    # Identity Data
    full_name = models.CharField(max_length=100, verbose_name="Full Legal Name")
    cnic_number = models.CharField(max_length=20, verbose_name="CNIC Number", help_text="e.g. 42101-1234567-1")
    contact_number = models.CharField(max_length=20, verbose_name="Contact Number")
    email = models.EmailField(verbose_name="Official Email Address")
    office_address = models.TextField(verbose_name="Physical Office/Headquarters Address")
    
    # Proof Documents
    cnic_front = models.ImageField(upload_to='verification_docs/', verbose_name="CNIC Front Image")
    cnic_back = models.ImageField(upload_to='verification_docs/', verbose_name="CNIC Back Image")
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"KYC: {self.store.name} - {self.status}"

    def save(self, *args, **kwargs):
        """
        Automation: If admin approves this record, automatically flip 
        the Store's 'is_verified' switch to True.
        """
        super().save(*args, **kwargs)
        if self.status == 'approved':
            self.store.is_verified = True
            self.store.save()
        else:
            self.store.is_verified = False
            self.store.save()

# ==============================================================================
# 3. MARKETING (Collections & Coupons)
# ==============================================================================

class Collection(models.Model):
    """
    Grouping mechanism for products (e.g. 'Winter Sale', 'Eid Collection').
    """
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='collections')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='collection_covers/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.store.name}"

class DiscountCode(models.Model):
    DISCOUNT_TYPES = [
        ('PERCENT', 'Percentage (%)'),
        ('FIXED', 'Fixed Amount (Rs)'),
    ]
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='discounts')
    code = models.CharField(max_length=20, verbose_name="Coupon Code", unique=True)
    
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES, default='PERCENT')
    value = models.PositiveIntegerField(help_text="Enter percentage (e.g. 10) or amount (e.g. 200)")
    
    active = models.BooleanField(default=True)
    valid_until = models.DateTimeField(blank=True, null=True)

    def is_valid(self):
        now = timezone.now()
        if not self.active: return False
        if self.valid_until and self.valid_until < now: return False
        return True

    def __str__(self):
        return f"{self.code} ({self.store.name})"

class CouponUsage(models.Model):
    """Tracks who used which coupon to prevent abuse."""
    coupon = models.ForeignKey(DiscountCode, on_delete=models.CASCADE, related_name='usages')
    email = models.EmailField()
    used_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('coupon', 'email') # One use per email per coupon

# ==============================================================================
# 4. PRODUCT ENGINE (With Variants)
# ==============================================================================

class Product(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products')
    collection = models.ForeignKey(Collection, on_delete=models.SET_NULL, related_name='products', blank=True, null=True)
    
    # Basic Info
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Selling Price")
    old_price = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True, verbose_name="Price Before Discount")

    # Inventory & Status
    stock = models.PositiveIntegerField(default=1, verbose_name="Base Stock")
    is_available = models.BooleanField(default=True, verbose_name="In Stock")
    is_active = models.BooleanField(default=True, verbose_name="Visible", help_text="Uncheck to hide product.")
    
    # Media
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Managers
    objects = models.Manager()
    titanium = LocalProductManager()

    class Meta:
        ordering = ['-created_at']

    # --- Logic ---
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def has_variants(self):
        """Returns True if the product has complex options (Size/Color)."""
        return self.variant_types.exists()

    def get_real_stock(self):
        """
        Calculates true stock. 
        If variants exist, it sums up the variant stock. 
        If not, it returns the base stock.
        """
        if self.has_variants:
            total = 0
            for v_type in self.variant_types.all():
                total += v_type.items.aggregate(Sum('stock'))['stock__sum'] or 0
            return total
        return self.stock

    def average_rating(self):
        if self.reviews.exists():
            avg = self.reviews.aggregate(Avg('rating'))['rating__avg']
            return round(avg, 1) if avg else 0
        return 0

    def get_discount_percentage(self):
        if self.old_price and self.old_price > self.price:
            discount = ((self.old_price - self.price) / self.old_price) * 100
            return math.ceil(discount)
        return 0

    def get_absolute_url(self):
        return reverse('product_detail', args=[str(self.id)])

    def __str__(self):
        return self.name

class ProductImage(models.Model):
    """Additional Gallery Images"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='gallery_images')
    image = models.ImageField(upload_to='product_gallery/')

class ProductVariantType(models.Model):
    """The Dimension (e.g. Size, Color, Material)"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variant_types')
    name = models.CharField(max_length=100, verbose_name="Variant Name (e.g. Size)")
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='variant_details/', blank=True, null=True)

    def __str__(self):
        return f"{self.product.name} - {self.name}"

class ProductVariantItem(models.Model):
    """The Specific Option (e.g. Small, Red, Cotton)"""
    variant_type = models.ForeignKey(ProductVariantType, on_delete=models.CASCADE, related_name='items')
    value = models.CharField(max_length=100, verbose_name="Value (e.g. Small)")
    
    # This is the stock that matters for variants
    stock = models.PositiveIntegerField(default=0, verbose_name="Variant Stock")

    # Overrides
    price = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True, verbose_name="Override Price")
    old_price = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    image = models.ImageField(upload_to='variant_images/', blank=True, null=True)

    def __str__(self):
        return f"{self.value} (Stock: {self.stock})"

# ==============================================================================
# 5. REVIEWS & RATINGS
# ==============================================================================

class Review(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='reviews')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews', blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField()
    image = models.ImageField(upload_to='review_images/', blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.rating}★ Review"

# ==============================================================================
# 6. ORDER SYSTEM (Unified Logic)
# ==============================================================================

class Order(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Shipped', 'Shipped'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
        ('Returned', 'Returned'),
    ]

    # 💎 FEATURE: Unified Alpha-Numeric ID (e.g. 8X92B)
    # This ID connects multiple items bought in one cart session.
    order_group_id = models.CharField(
        max_length=20, 
        blank=True, null=True, 
        help_text="Public Group ID for Cart Checkout"
    )
    
    # Internal DB Reference (synced with group_id)
    order_ref = models.CharField(max_length=20, blank=True, null=True)

    # Links
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='orders')
    
    # Item Details
    selected_variant = models.CharField(max_length=255, blank=True, null=True)
    quantity = models.PositiveIntegerField(default=1)
    
    # Logistics Info
    shipping_name = models.CharField(max_length=100, default="")
    shipping_email = models.EmailField(default="") 
    shipping_phone = models.CharField(max_length=20, default="")
    shipping_address = models.TextField(default="", help_text="Detailed Address")
    shipping_city = models.CharField(max_length=100, default="")
    
    # Logistics Tracking (Added Back)
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    courier_name = models.CharField(max_length=100, blank=True, null=True)
    
    # Payment
    payment_method_selected = models.CharField(max_length=20, default='COD')
    payment_screenshot = models.ImageField(upload_to='payment_proofs/', blank=True, null=True)
    is_paid = models.BooleanField(default=False)
    
    # 💎 SAFEPAY TRACKER (Restored)
    safepay_tracker = models.CharField(max_length=100, blank=True, null=True)
    
    # Financials (Snapshot at time of purchase)
    subtotal_price = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-generate ID if missing
        if not self.order_group_id:
            unique_id = str(uuid.uuid4())[:8].upper()
            self.order_group_id = unique_id
            if not self.order_ref:
                self.order_ref = unique_id

        # Auto-calculate totals if missing
        if not self.total_price and self.product:
            price = self.product.price
            self.subtotal_price = price * self.quantity
            self.total_price = self.subtotal_price + self.delivery_fee - self.discount_amount
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"#{self.order_group_id} - {self.product.name}"

# ==============================================================================
# 7. CHAT SYSTEM (Real-Time Communication)
# ==============================================================================

class Conversation(models.Model):
    """Container for a chat between a User and a Store."""
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customer_chats')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='store_chats')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('customer', 'store')
        ordering = ['-updated_at']

    def __str__(self):
        return f"Chat: {self.customer.username} <-> {self.store.name}"

class Message(models.Model):
    """Individual message (Text or Image)"""
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    
    text = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='chat_images/', blank=True, null=True)
    
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Msg from {self.sender.username}: {self.text[:20] if self.text else 'Image'}"

# ==============================================================================
# 💎 8. NUKR TALASH (The Reverse Marketplace)
# ==============================================================================

class ProductRequest(models.Model):
    """
    Represents a buyer's request for a product.
    Sellers with matching Categories receive these leads.
    """
    # Uses the Global Category Choices defined at top of file
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='OTHER')

    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_requests')
    
    title = models.CharField(max_length=255, verbose_name="I am looking for...")
    description = models.TextField(verbose_name="Details (Color, Size, Urgency)")
    
    # Visual Reference is Mandatory for better leads
    reference_image = models.ImageField(upload_to='talash_refs/', verbose_name="Reference Photo")
    
    budget = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="My Budget (Rs)")
    city = models.CharField(max_length=100, default="Karachi") 
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Talash: {self.title} in {self.city} ({self.category})"

# ==============================================================================
# 9. USER UTILITIES & WALLET
# ==============================================================================

class StoreWallet(models.Model):
    """Tracks earnings for a store."""
    store = models.OneToOneField(Store, on_delete=models.CASCADE)
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Bank Info for Payouts
    payout_bank_name = models.CharField(max_length=100, blank=True, null=True)
    payout_account_no = models.CharField(max_length=100, blank=True, null=True)
    
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet: {self.store.name} - Rs. {self.current_balance}"

class UserProfile(models.Model):
    """Extended user data (Profile Pic, Phone)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    image = models.ImageField(upload_to='profile_pics/', default='profile_pics/default.png', blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True) # Added City for auto-fill

    def __str__(self):
        return self.user.username

# --- Signals to Auto-Create UserProfile & Wallet ---
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if not hasattr(instance, 'userprofile'):
        UserProfile.objects.create(user=instance)
    instance.userprofile.save()

@receiver(post_save, sender=Store)
def create_store_wallet(sender, instance, created, **kwargs):
    if created:
        StoreWallet.objects.create(store=instance)