import json
import uuid 
import requests 
import os 
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib import messages
from django.db import transaction 
from django.db.models import Q, Sum, Avg, Count, Max
from django.conf import settings
from django.utils import timezone
from django.urls import reverse

# --- AUTHENTICATION & ACCOUNTS ---
from django.contrib.auth.models import User
from allauth.account.models import EmailAddress
from allauth.account.utils import send_email_confirmation

# --- MODELS & FORMS ---
from .models import (
    Store, Product, Order, ProductImage, ProductVariantType, ProductVariantItem, 
    DiscountCode, StoreVerification, CouponUsage, Review, Collection, UserProfile,
    StoreWallet, Conversation, Message, ProductRequest
)
from .forms import (
    StoreForm, ProductForm, CheckoutForm, DiscountCodeForm, 
    StoreVerificationForm, ReviewForm, CollectionForm, OrderUpdateForm,
    MessageForm, TalashForm
)

# ==============================================================================
# 0. CONFIGURATION & HELPERS (TITANIUM INFRASTRUCTURE)
# ==============================================================================

# 💎 SECURITY FIX: Load API Key from Environment
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "xkeysib-PLACEHOLDER-IF-MISSING")

# 💎 SENDER IDENTITIES: Dictionary format for Brevo API
ORDER_SENDER = {"name": "Nukr", "email": "orders@nukr.store"}
SUPPORT_SENDER = {"name": "Nukr", "email": "support@nukr.store"}

def _send_brevo(to_email, template_id, params, sender_identity):
    """ 
    💎 DIRECT API FIX: Uses requests to send emails directly to Brevo V3 API.
    Prevents SMTP crashes and handles Vercel environment limitations.
    """
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }
    
    # Ensure sender is strictly in dictionary format
    if isinstance(sender_identity, str):
        sender_data = {"name": "Nukr", "email": "hello@nukr.store"} 
    else:
        sender_data = sender_identity

    payload = {
        "sender": sender_data,
        "to": [{"email": to_email}],
        "templateId": template_id,
        "params": params
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        if response.status_code in [200, 201, 202]:
            print(f"✅ Email Sent: Template {template_id} to {to_email}")
        else:
            print(f"❌ Brevo Error {response.status_code}: {response.text}")
            # We log but do NOT raise, to ensure orders complete even if email fails
    except Exception as e:
        print(f"❌ Critical Email Network Fail: {e}")

def _get_cart_count(request, store_id):
    """
    Calculates total items in cart for a specific store.
    Includes auto-healing for corrupted sessions.
    """
    cart = request.session.get('cart', {})
    store_cart = cart.get(str(store_id), {})
    count = 0
    is_corrupt = False
    
    if isinstance(store_cart, dict):
        for item in store_cart.values():
            if isinstance(item, dict):
                count += item.get('quantity', 0)
            else:
                is_corrupt = True
                break
    else:
        is_corrupt = True

    if is_corrupt:
        if str(store_id) in cart:
            del cart[str(store_id)]
            request.session['cart'] = cart
        return 0
    return count

# ==============================================================================
# 1. MARKETPLACE BROWSING (MALL LOGIC)
# ==============================================================================

def mall_home(request):
    query = request.GET.get('q', '') 
    user_city = request.COOKIES.get('nukr_city')
    sort_by = request.GET.get('sort', '') 

    # Base Query: Optimize with annotations
    stores = Store.objects.annotate(
        avg_rating=Avg('reviews__rating'),
        review_count=Count('reviews')
    )

    # 1. City Filtering (Geo-Logic)
    if user_city:
        stores = stores.filter(
            Q(city__iexact=user_city) |                
            Q(deliver_nationwide=True) |                
            Q(secondary_cities__icontains=user_city)    
        ).distinct()
    
    # 2. Search Query
    if query:
        stores = stores.filter(
            Q(name__icontains=query) | 
            Q(description__icontains=query) |
            Q(products__name__icontains=query) 
        ).distinct()

    # 3. Sorting Logic
    if sort_by == 'rating':
        stores = stores.order_by('-is_verified', '-avg_rating')
    elif sort_by == 'reviews':
        stores = stores.order_by('-is_verified', '-review_count')
    else:
        stores = stores.order_by('-is_verified', '-created_at')
        
    return render(request, 'marketplace/mall_home.html', {
        'stores': stores, 
        'query': query, 
        'sort': sort_by
    })

def store_detail(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    collection_id = request.GET.get('collection')
    search_query = request.GET.get('q', '')

    products = store.products.filter(is_active=True)
    page_title = "All Products"

    if collection_id:
        try:
            selected_col = Collection.objects.get(id=collection_id)
            products = products.filter(collection=selected_col)
            page_title = selected_col.name 
        except Collection.DoesNotExist: pass
    
    if search_query:
        products = products.filter(name__icontains=search_query)
        page_title = f'Results for "{search_query}"'

    context = {
        'store': store,
        'products': products,
        'collections': store.collections.all(),
        'reviews': store.reviews.all().order_by('-created_at'),
        'cart_count': _get_cart_count(request, store.id),
        'search_query': search_query,
        'active_collection': int(collection_id) if collection_id else None,
        'page_title': page_title,
    }
    return render(request, 'marketplace/store_detail.html', context)

def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)
    return render(request, 'marketplace/product_detail.html', {
        'product': product, 
        'gallery': product.gallery_images.all(), 
        'variant_types': product.variant_types.prefetch_related('items').all(),
        'cart_count': _get_cart_count(request, product.store.id),
        'store': product.store,
        'reviews': product.reviews.all().order_by('-created_at'),
        'review_form': ReviewForm(),
        'collections': Collection.objects.filter(store=product.store)
    })

# ==============================================================================
# 2. CHAT SYSTEM (MESSAGING ENGINE)
# ==============================================================================

@login_required
def my_chats(request):
    """
    Aggregated Chat View:
    - Displays chats where user is a Customer
    - Displays chats where user is a Store Owner
    """
    user = request.user
    
    # 1. As a Customer
    customer_chats = Conversation.objects.filter(customer=user).annotate(
        last_msg_time=Max('messages__timestamp')
    ).order_by('-last_msg_time')
    
    # 2. As a Store Owner
    owner_chats = []
    user_stores = Store.objects.filter(owner=user)
    if user_stores.exists():
        owner_chats = Conversation.objects.filter(store__in=user_stores).annotate(
            last_msg_time=Max('messages__timestamp')
        ).order_by('-last_msg_time')

    return render(request, 'marketplace/chat/chat_list.html', {
        'customer_chats': customer_chats,
        'owner_chats': owner_chats
    })

@login_required
def start_chat(request, store_id):
    """
    Initiates a chat room for a specific store.
    """
    store = get_object_or_404(Store, id=store_id)
    
    if request.user == store.owner:
        messages.warning(request, "You cannot chat with your own store.")
        return redirect('store_detail', store_id=store.id)

    # Get or Create Conversation
    conversation, created = Conversation.objects.get_or_create(customer=request.user, store=store)
    return redirect('chat_room', conversation_id=conversation.id)

@login_required
def chat_room(request, conversation_id):
    """
    The Main Chat Interface.
    """
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    # Security Check: Only participants can access
    if request.user != conversation.customer and request.user != conversation.store.owner:
        return redirect('home')

    # Mark incoming messages as read
    Message.objects.filter(conversation=conversation).exclude(sender=request.user).update(is_read=True)

    return render(request, 'marketplace/chat/chat_room.html', {
        'conversation': conversation,
        'messages': conversation.messages.all(),
        'form': MessageForm()
    })

@login_required
@require_POST
def send_message_api(request, conversation_id):
    """
    AJAX Endpoint: Handles sending messages (Text + Image support).
    """
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if request.user != conversation.customer and request.user != conversation.store.owner:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    form = MessageForm(request.POST, request.FILES)
    if form.is_valid():
        msg = form.save(commit=False)
        msg.conversation = conversation
        msg.sender = request.user
        msg.save()
        
        # Update timestamp for sorting
        conversation.updated_at = timezone.now()
        conversation.save()

        return JsonResponse({
            'status': 'success',
            'text': msg.text,
            'image_url': msg.image.url if msg.image else None,
            'timestamp': msg.timestamp.strftime("%I:%M %p"),
            'sender': msg.sender.username
        })
    return JsonResponse({'status': 'error', 'message': 'Invalid form'}, status=400)

@login_required
def get_messages_api(request, conversation_id):
    """
    AJAX Polling Endpoint: Fetches new messages dynamically.
    """
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if request.user != conversation.customer and request.user != conversation.store.owner:
        return JsonResponse({'status': 'error'}, status=403)

    msgs = conversation.messages.select_related('sender').all()
    data = []
    for m in msgs:
        data.append({
            'sender': m.sender.username,
            'is_me': m.sender == request.user,
            'text': m.text,
            'image_url': m.image.url if m.image else None,
            'timestamp': m.timestamp.strftime("%I:%M %p")
        })
        
        # Mark as read if it's incoming
        if m.sender != request.user and not m.is_read:
            m.is_read = True
            m.save()

    return JsonResponse({'messages': data})

@login_required
def delete_conversation(request, conversation_id):
    """
    Permanently deletes a conversation.
    """
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    if request.user == conversation.customer or request.user == conversation.store.owner:
        conversation.delete()
        messages.success(request, "Conversation deleted successfully.")
    else:
        messages.error(request, "Unauthorized action.")
        
    return redirect('my_chats')

@login_required
@require_POST
def delete_message_api(request, message_id):
    """
    AJAX: Permanently deletes a single message.
    """
    message = get_object_or_404(Message, id=message_id)
    if message.sender == request.user:
        message.delete()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

# ==============================================================================
# 3. STATIC PAGES
# ==============================================================================

def help_center(request):
    return render(request, 'help.html')

def privacy_policy(request):
    return render(request, 'privacy.html')

def terms_of_service(request):
    return render(request, 'terms.html')

# ==============================================================================
# 4. ACCOUNT & SETTINGS
# ==============================================================================

@login_required
def account_settings(request):
    user = request.user
    try: user_profile, created = UserProfile.objects.get_or_create(user=user)
    except: user_profile = None

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        username = request.POST.get('username', '').strip()
        new_email = request.POST.get('email', '').strip()
        
        user.first_name = first_name
        user.last_name = last_name

        if username and username != user.username:
            if User.objects.filter(username=username).exists():
                messages.error(request, "Username already taken.")
                return redirect('account_settings')
            user.username = username

        if new_email and new_email != user.email:
            if EmailAddress.objects.filter(email=new_email).exists():
                messages.error(request, "Email already in use.")
            else:
                try:
                    EmailAddress.objects.add_email(request, user, new_email, confirm=True)
                    messages.info(request, f"Verification sent to {new_email}.")
                except: messages.error(request, "Error sending verification.")

        if 'profile_image' in request.FILES and user_profile:
            user_profile.image = request.FILES['profile_image']
            user_profile.save()

        user.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('account_settings')
    
    return render(request, 'account/settings.html')

@login_required
def my_orders(request):
    orders = Order.objects.filter(customer=request.user).select_related('store', 'product').order_by('-created_at')
    total_spent = orders.exclude(status='Cancelled').aggregate(Sum('total_price'))['total_price__sum'] or 0
    return render(request, 'account/my_orders.html', {'orders': orders, 'total_spent': total_spent, 'total_orders': orders.count()})

# ==============================================================================
# 5. VENDOR DASHBOARD
# ==============================================================================

@login_required
def create_store(request):
    if hasattr(request.user, 'store'):
        return redirect('store_dashboard', store_id=request.user.store.id)

    if request.method == 'POST':
        form = StoreForm(request.POST, request.FILES)
        if form.is_valid():
            store = form.save(commit=False)
            store.owner = request.user 
            store.save()
            # Send notification (Safe outside transaction)
            _send_brevo(store.owner.email, 7, {'OWNER_NAME': store.owner.username, 'STORE_NAME': store.name, 'STORE_ID': str(store.id)}, SUPPORT_SENDER)
            messages.success(request, "Store created!")
            return redirect('store_dashboard', store_id=store.id)
    else:
        form = StoreForm()
    return render(request, 'marketplace/create_store.html', {'form': form})

@login_required
def store_dashboard(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    if request.user != store.owner: return redirect('home')

    orders = Order.objects.filter(store=store).order_by('-created_at')
    valid_orders = orders.exclude(status='Cancelled')
    revenue_data = valid_orders.aggregate(Sum('total_price'))
    
    return render(request, 'marketplace/dashboard.html', {
        'store': store, 'orders': orders, 'products': store.products.all(),
        'coupons': store.discounts.all(), 'collections': store.collections.all(),
        'total_revenue': revenue_data['total_price__sum'] or 0, 'total_orders': orders.count()
    })

@login_required
def dashboard_redirect(request):
    """Smart redirect to the user's first store dashboard."""
    if hasattr(request.user, 'store'): return redirect('store_dashboard', store_id=request.user.store.id)
    if request.user.stores.exists(): return redirect('store_dashboard', store_id=request.user.stores.first().id)
    return redirect('create_store')

@login_required
def edit_store(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    if request.user != store.owner: return redirect('home')
    
    if request.method == 'POST':
        form = StoreForm(request.POST, request.FILES, instance=store)
        if form.is_valid():
            form.save()
            messages.success(request, "Store settings updated!")
            return redirect('store_dashboard', store_id=store.id)
    else:
        form = StoreForm(instance=store)
    return render(request, 'marketplace/edit_store.html', {'form': form, 'store': store})

# ==============================================================================
# 6. PRODUCT MANAGEMENT (💎 FIX: URL ALIGNMENT)
# ==============================================================================

@login_required
def add_product_to_store(request, store_id):
    """
    💎 FIXED: Explicitly handles the 'store_id' passed from the dashboard button.
    This resolves the NoReverseMatch error for {% url 'add_product_to_store' store.id %}
    """
    store = get_object_or_404(Store, id=store_id, owner=request.user)
    
    if request.method == 'POST':
        form = ProductForm(store=store, data=request.POST, files=request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.store = store
            product.is_active = request.POST.get('is_active') == 'on'
            product.save()
            
            # Save Gallery Images
            for img in request.FILES.getlist('gallery_images'): 
                ProductImage.objects.create(product=product, image=img)
            
            # --- Dynamic Variants Engine ---
            type_names = request.POST.getlist('variant_type_name[]')
            type_descs = request.POST.getlist('variant_type_desc[]')
            
            for i, name in enumerate(type_names):
                if name.strip():
                    v_type = ProductVariantType.objects.create(product=product, name=name, description=type_descs[i] if i < len(type_descs) else "")
                    if f'variant_type_image_{i}' in request.FILES:
                        v_type.image = request.FILES[f'variant_type_image_{i}']; v_type.save()
                    
                    vals = request.POST.getlist(f'variant_values_{i}[]')
                    stocks = request.POST.getlist(f'variant_stocks_{i}[]')
                    prices = request.POST.getlist(f'variant_prices_{i}[]')
                    old_prices = request.POST.getlist(f'variant_old_prices_{i}[]')
                    
                    for j, val in enumerate(vals):
                        if val.strip():
                            v_item = ProductVariantItem.objects.create(
                                variant_type=v_type, value=val, stock=stocks[j] or 0,
                                price=prices[j] or None, old_price=old_prices[j] or None
                            )
                            if f'variant_image_{i}_{j}' in request.FILES:
                                v_item.image = request.FILES[f'variant_image_{i}_{j}']; v_item.save()

            messages.success(request, "Product added successfully!")
            return redirect('store_dashboard', store_id=store.id)
    else:
        form = ProductForm(store=store)
    
    return render(request, 'marketplace/add_product.html', {'form': form, 'store': store, 'is_edit': False})

@login_required
def add_product(request, store_id=None):
    """
    Legacy Wrapper: Redirects to the specific store add logic if ID provided,
    or redirects to dashboard if missing.
    """
    if store_id:
        return add_product_to_store(request, store_id)
    elif hasattr(request.user, 'store'):
        return add_product_to_store(request, request.user.store.id)
    return redirect('create_store')

@login_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if product.store.owner != request.user: return redirect('home')

    if request.method == 'POST':
        form = ProductForm(store=product.store, data=request.POST, files=request.FILES, instance=product)
        if form.is_valid():
            product = form.save(commit=False)
            product.is_active = request.POST.get('is_active') == 'on'
            product.save()

            delete_ids = request.POST.getlist('delete_images')
            if delete_ids: ProductImage.objects.filter(id__in=delete_ids, product=product).delete()
            for img in request.FILES.getlist('gallery_images'): 
                ProductImage.objects.create(product=product, image=img)

            # --- Variants Logic (Wipe & Recreate Strategy) ---
            product.variant_types.all().delete()
            type_names = request.POST.getlist('variant_type_name[]')
            type_descs = request.POST.getlist('variant_type_desc[]')
            
            for i, name in enumerate(type_names):
                if name.strip():
                    v_type = ProductVariantType.objects.create(product=product, name=name, description=type_descs[i] if i < len(type_descs) else "")
                    if f'variant_type_image_{i}' in request.FILES:
                        v_type.image = request.FILES[f'variant_type_image_{i}']; v_type.save()
                    
                    vals = request.POST.getlist(f'variant_values_{i}[]')
                    stocks = request.POST.getlist(f'variant_stocks_{i}[]')
                    prices = request.POST.getlist(f'variant_prices_{i}[]')
                    old_prices = request.POST.getlist(f'variant_old_prices_{i}[]')
                    
                    for j, val in enumerate(vals):
                        if val.strip():
                            v_item = ProductVariantItem.objects.create(
                                variant_type=v_type, value=val, stock=stocks[j] or 0,
                                price=prices[j] or None, old_price=old_prices[j] or None
                            )
                            if f'variant_image_{i}_{j}' in request.FILES:
                                v_item.image = request.FILES[f'variant_image_{i}_{j}']; v_item.save()

            messages.success(request, "Product updated!")
            return redirect('store_dashboard', store_id=product.store.id)
    else:
        form = ProductForm(store=product.store, instance=product)

    return render(request, 'marketplace/add_product.html', {
        'form': form, 'store': product.store, 'product': product, 'is_edit': True,
        'variant_types': product.variant_types.prefetch_related('items').all()
    })

# ==============================================================================
# 7. COUPONS, VERIFICATION & COLLECTIONS
# ==============================================================================

@login_required
def manage_coupons(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    if request.user != store.owner: return redirect('home')
    
    if request.method == 'POST':
        form = DiscountCodeForm(request.POST)
        if form.is_valid():
            coupon = form.save(commit=False)
            coupon.store = store
            coupon.save()
            messages.success(request, "Coupon created!")
            return redirect('manage_coupons', store_id=store.id)
    else:
        form = DiscountCodeForm()
    
    coupons = store.discounts.all().order_by('-active')
    return render(request, 'marketplace/manage_coupons.html', {'store': store, 'form': form, 'coupons': coupons})

@login_required
def delete_coupon(request, coupon_id):
    coupon = get_object_or_404(DiscountCode, id=coupon_id)
    if request.user == coupon.store.owner:
        store_id = coupon.store.id
        coupon.delete()
        messages.success(request, "Coupon deleted.")
        return redirect('manage_coupons', store_id=store_id)
    return redirect('home')

@login_required
def add_collection(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    if request.user != store.owner: return redirect('home')
    
    if request.method == 'POST':
        form = CollectionForm(request.POST, request.FILES)
        if form.is_valid():
            collection = form.save(commit=False)
            collection.store = store
            collection.save()
            messages.success(request, "Collection created!")
            return redirect('store_dashboard', store_id=store.id)
    else:
        form = CollectionForm()
    return render(request, 'marketplace/add_collection.html', {'form': form, 'store': store})

@login_required
def delete_collection(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)
    if request.user == collection.store.owner:
        collection.delete()
        messages.success(request, "Collection deleted.")
        return redirect('store_dashboard', store_id=collection.store.id)
    return redirect('home')

@login_required
def request_verification(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    if request.user != store.owner: return redirect('home')

    if hasattr(store, 'verification'): return redirect('store_dashboard', store_id=store.id)

    if request.method == 'POST':
        form = StoreVerificationForm(request.POST, request.FILES)
        if form.is_valid():
            app = form.save(commit=False)
            app.store = store
            app.save()
            messages.success(request, "Verification request submitted!")
            return redirect('store_dashboard', store_id=store.id)
    else:
        form = StoreVerificationForm(initial={'email': request.user.email})
    
    return render(request, 'marketplace/create_store.html', {'form': form}) 

# ==============================================================================
# 8. REVIEWS & ORDER MANAGEMENT
# ==============================================================================

@login_required
@require_POST
def store_review(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    form = ReviewForm(request.POST, request.FILES)
    if form.is_valid():
        review = form.save(commit=False)
        review.store = store
        review.user = request.user
        review.save()
        messages.success(request, "Store review submitted successfully!")
    else:
        messages.error(request, "Error submitting review.")
    return redirect('store_detail', store_id=store.id)

@login_required
@require_POST
def product_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    form = ReviewForm(request.POST, request.FILES)
    if form.is_valid():
        review = form.save(commit=False)
        review.product = product
        review.user = request.user
        review.store = product.store
        review.save()
        messages.success(request, "Review submitted successfully!")
    else:
        messages.error(request, "Error submitting review.")
    return redirect('product_detail', product_id=product.id)

@login_required
def delete_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    if request.user == review.store.owner:
        review.delete()
        messages.success(request, "Review removed.")
    return redirect(request.META.get('HTTP_REFERER', 'home'))

@login_required
def manage_order(request, order_id):
    main_order = get_object_or_404(Order, id=order_id)
    if request.user != main_order.store.owner: 
        return redirect('home')
    
    if main_order.order_group_id:
        all_items = Order.objects.filter(order_group_id=main_order.order_group_id)
    else:
        all_items = [main_order]

    subtotal = sum(item.subtotal_price for item in all_items)
    delivery = sum(item.delivery_fee for item in all_items)
    discount = sum(item.discount_amount for item in all_items)
    grand_total = sum(item.total_price for item in all_items)

    return render(request, 'marketplace/manage_order.html', {
        'order': main_order,
        'orders': all_items,
        'store': main_order.store,
        'subtotal': subtotal,
        'delivery': delivery,
        'discount': discount,
        'grand_total': grand_total
    })

@login_required
@require_POST
def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.user != order.store.owner: return redirect('home')

    new_status = request.POST.get('status')
    if new_status in ['Confirmed', 'Shipped', 'Delivered', 'Cancelled']:
        old_status = order.status
        order.status = new_status
        order.save()
        
        if old_status != new_status:
            if new_status == 'Cancelled': 
                send_cancelled_email(order, "Order cancelled by store owner.")
            elif new_status in ['Shipped', 'Delivered']: 
                send_status_email(order, new_status)
            messages.success(request, f"Order updated to {new_status}")
            
    return redirect('manage_order', order_id=order.id)

# ==============================================================================
# 9. CART SYSTEM (TITANIUM VARIANT LOGIC)
# ==============================================================================

@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    store_id = str(product.store.id)
    qty = int(request.POST.get('quantity', 1))
    
    final_price = product.price 
    variant_desc = []
    variant_ids = []  
    
    # 1. Parse Variants from POST
    for key, value in request.POST.items():
        if key.startswith('variant_'):
            variant_desc.append(value)
            try:
                v_item = ProductVariantItem.objects.filter(variant_type__product=product, value=value).first()
                if v_item:
                    # STRICT STOCK CHECK
                    if v_item.stock < qty:
                        messages.error(request, f"Variant '{value}' out of stock (Only {v_item.stock} left).")
                        return redirect(request.META.get('HTTP_REFERER', 'home'))
                    
                    variant_ids.append(v_item.id)
                    if v_item.price: final_price = v_item.price
            except: pass

    # 2. STRICT AUTHORITY CHECK
    if product.has_variants:
        if not variant_ids:
            messages.error(request, "Please select required options.")
            return redirect(request.META.get('HTTP_REFERER', 'home'))
        variant_str = ", ".join(variant_desc)
    else:
        if product.stock < qty:
            messages.error(request, f"Out of stock. Only {product.stock} left.")
            return redirect(request.META.get('HTTP_REFERER', 'home'))
        variant_str = "Standard"

    # 3. Add to Session
    item_key = f"{product.id}_{variant_str.replace(' ', '_')}"
    cart = request.session.get('cart', {})
    if store_id not in cart: cart[store_id] = {}
    
    if item_key in cart[store_id]:
        cart[store_id][item_key]['quantity'] += qty
    else:
        cart[store_id][item_key] = {
            'product_id': product.id, 'name': product.name, 'price': float(final_price),
            'quantity': qty, 'variant': variant_str, 'variant_ids': variant_ids,
            'image_url': product.image.url if product.image else None
        }
    
    request.session['cart'] = cart
    messages.success(request, "Added to cart!")
    return redirect(request.META.get('HTTP_REFERER', 'home'))

def update_cart_quantity(request, store_id, item_key, action):
    cart = request.session.get('cart', {})
    store_cart = cart.get(str(store_id), {})

    if item_key in store_cart:
        item = store_cart[item_key]
        current_qty = item['quantity']
        product = get_object_or_404(Product, id=item['product_id'])
        
        variant_ids = item.get('variant_ids', [])
        max_stock = float('inf') 
        
        if variant_ids:
            for vid in variant_ids:
                try:
                    v_item = ProductVariantItem.objects.get(id=vid)
                    if v_item.stock < max_stock: max_stock = v_item.stock
                except: pass
        else:
            max_stock = product.stock

        if action == 'plus':
            if current_qty < max_stock: item['quantity'] += 1
            else: messages.error(request, "Max stock reached.")
        elif action == 'minus':
            if current_qty > 1: item['quantity'] -= 1
        
        request.session['cart'] = cart
    return redirect('view_cart', store_id=store_id)

def remove_from_cart(request, store_id, item_key):
    cart = request.session.get('cart', {})
    s_id = str(store_id)
    if s_id in cart and item_key in cart[s_id]:
        del cart[s_id][item_key]
        request.session['cart'] = cart
        messages.success(request, "Item removed.")
    return redirect('view_cart', store_id=store_id)

def view_cart(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    cart = request.session.get('cart', {})
    store_cart = cart.get(str(store.id), {})
    
    clean_items = []
    if isinstance(store_cart, dict):
        for k, v in store_cart.items():
            if isinstance(v, dict):
                v['key'] = k
                v['total'] = v['price'] * v['quantity']
                clean_items.append(v)
            
    return render(request, 'marketplace/cart.html', {
        'cart_items': clean_items, 
        'total_price': sum(x['total'] for x in clean_items), 
        'store': store
    })

def apply_coupon(request, store_id):
    if request.method == 'POST':
        code = request.POST.get('code')
        store = get_object_or_404(Store, id=store_id)
        try:
            coupon = DiscountCode.objects.get(store=store, code__iexact=code, active=True)
            if coupon.is_valid():
                if request.user.is_authenticated:
                    if CouponUsage.objects.filter(coupon=coupon, email=request.user.email).exists():
                        messages.error(request, "Already used.")
                        return redirect('checkout', store_id=store_id)
                request.session[f'discount_{store.id}'] = {'id': coupon.id, 'value': str(coupon.value), 'type': coupon.discount_type, 'code': coupon.code}
                messages.success(request, f"Applied {coupon.code}!")
            else: messages.error(request, "Coupon expired.")
        except: messages.error(request, "Invalid code.")
    return redirect('checkout', store_id=store_id)

# ==============================================================================
# 10. CHECKOUT (GROUPED ORDERS + ATOMIC TRANSACTIONS)
# ==============================================================================

@login_required
def checkout(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    cart = request.session.get('cart', {})
    store_cart = cart.get(str(store.id), {})

    # Auto-clean broken cart data
    if not store_cart or not isinstance(store_cart, dict):
        messages.warning(request, "Your cart is empty.")
        return redirect('store_detail', store_id=store.id)

    subtotal = sum(item['price'] * item['quantity'] for item in store_cart.values())
    delivery = store.delivery_charges
    
    discount_data = request.session.get(f'discount_{store.id}')
    discount_amt = 0
    if discount_data:
        try:
            val = float(discount_data['value'])
            if discount_data['type'] == 'PERCENT':
                discount_amt = (subtotal * val) / 100
            else: 
                discount_amt = val
        except: 
            del request.session[f'discount_{store.id}']

    grand_total = max(subtotal + float(delivery) - discount_amt, 0)

    # --- Handle Form Submission ---
    if request.method == 'POST':
        form = CheckoutForm(request.POST, request.FILES)
        
        # Payment Choices
        payment_opts = []
        if store.payment_method in ['COD', 'BOTH']: payment_opts.append(('COD', 'Cash on Delivery'))
        if store.payment_method in ['OL', 'BOTH']: payment_opts.append(('ONLINE', 'Online Payment'))
        form.fields['payment_choice'].choices = payment_opts

        if form.is_valid():
            email_tasks = []
            final_order_id = None

            # 💎 ERROR HANDLING: Raise exception to logs if crash occurs
            try:
                with transaction.atomic(): # 🛡️ START ATOMIC TRANSACTION
                    
                    # 1. Generate GROUP ID for this checkout
                    group_id = str(uuid.uuid4())[:8].upper()

                    # 2. Phase 1: Pre-Validation (Check ALL items first)
                    items_to_process = [] 
                    
                    for key, item in store_cart.items():
                        try: 
                            p = Product.objects.select_for_update().get(id=item['product_id'])
                        except Product.DoesNotExist:
                            raise ValueError(f"Product {item['name']} no longer exists.")

                        qty_needed = item['quantity']
                        variant_ids = item.get('variant_ids', [])
                        
                        # --- Inventory Check Logic ---
                        if p.has_variants:
                            if not variant_ids:
                                raise ValueError(f"{p.name} requires options. Please remove and re-add.")
                            
                            variants_checked = []
                            for vid in variant_ids:
                                try:
                                    v_obj = ProductVariantItem.objects.select_for_update().get(id=vid)
                                    if v_obj.stock < qty_needed:
                                        raise ValueError(f"Sorry, variant '{v_obj.value}' of {p.name} is out of stock.")
                                    variants_checked.append(v_obj)
                                except ProductVariantItem.DoesNotExist:
                                    del cart[str(store.id)][key]
                                    request.session.modified = True
                                    raise ValueError(f"The option you selected for '{p.name}' is no longer available.")
                            
                            items_to_process.append({
                                'product': p, 'cart_item': item,
                                'variants': variants_checked, 'key': key
                            })
                            
                        else:
                            if p.stock < qty_needed:
                                raise ValueError(f"Sorry, {p.name} is out of stock.")
                            
                            items_to_process.append({
                                'product': p, 'cart_item': item,
                                'variants': [], 'key': key
                            })

                    # 3. Phase 2: Execution (Deduct & Create Orders)
                    created_orders = []
                    
                    for i, valid_item in enumerate(items_to_process):
                        p = valid_item['product']
                        item_data = valid_item['cart_item']
                        variants = valid_item['variants']
                        
                        # Deduct Stock
                        if p.has_variants:
                            for v in variants:
                                v.stock -= item_data['quantity']
                                v.save()
                                if v.stock == 0: send_low_stock_email(p)
                        else:
                            p.stock -= item_data['quantity']
                            p.save()
                            if p.stock == 0: send_low_stock_email(p)

                        # Financials per Item
                        i_total = item_data['price'] * item_data['quantity']
                        ratio = i_total / subtotal if subtotal > 0 else 0
                        i_disc = float(discount_amt) * float(ratio)
                        
                        # Apply Delivery Fee ONLY to the First Order row
                        row_delivery = delivery if i == 0 else 0

                        # Create Order Row
                        o = Order.objects.create(
                            customer=request.user,
                            store=store,
                            product=p,
                            order_group_id=group_id,
                            order_ref=group_id, 
                            selected_variant=item_data['variant'],
                            shipping_name=form.cleaned_data['shipping_name'],
                            shipping_email=form.cleaned_data['shipping_email'],
                            shipping_phone=form.cleaned_data['shipping_phone'],
                            shipping_address=form.cleaned_data['shipping_address'],
                            shipping_city=form.cleaned_data['shipping_city'],
                            payment_method_selected=form.cleaned_data['payment_choice'],
                            payment_screenshot=form.cleaned_data.get('payment_screenshot'),
                            quantity=item_data['quantity'],
                            subtotal_price=i_total,
                            discount_amount=i_disc,
                            delivery_fee=row_delivery,
                            total_price=i_total + float(row_delivery) - i_disc,
                            status='Confirmed'
                        )
                        created_orders.append(o)
                        
                        # Remove from Session Cart
                        del cart[str(store.id)][valid_item['key']]

                    # 4. Phase 3: Cleanup & Queue Emails
                    if discount_data:
                        try:
                            c = DiscountCode.objects.get(id=discount_data['id'])
                            CouponUsage.objects.create(coupon=c, email=request.user.email)
                        except: pass
                        if f'discount_{store.id}' in request.session:
                            del request.session[f'discount_{store.id}']

                    request.session['cart'] = cart
                    
                    # Prepare Email Data
                    first_o = created_orders[0]
                    final_order_id = first_o.id
                    items_summary = "\n".join([f"{o.quantity}x {o.product.name} ({o.selected_variant})" for o in created_orders])
                    pay_method = "COD" if first_o.payment_method_selected == 'COD' else "Online"

                    # Vendor Email Params
                    v_params = {
                        'VENDOR_NAME': store.owner.username,
                        'STORE_NAME': store.name,
                        'ORDER_ID': f"#{group_id}",
                        'TOTAL': str(grand_total),
                        'PAYMENT_METHOD': pay_method,
                        'CUSTOMER_NAME': first_o.shipping_name,
                        'PHONE': first_o.shipping_phone,
                        'EMAIL': first_o.shipping_email,
                        'ADDRESS': f"{first_o.shipping_address}, {first_o.shipping_city}",
                        'ITEMS_SUMMARY': items_summary,
                        'PAYMENT_SCREENSHOT_URL': "Check Dashboard", 
                        'DASHBOARD_URL': f"https://nukr.store/store/{store.id}/dashboard/",
                        'QTY': str(sum(o.quantity for o in created_orders))
                    }
                    email_tasks.append({'to': store.owner.email, 'template': 5, 'params': v_params, 'sender': ORDER_SENDER})

                    # Customer Email Params
                    c_params = {
                        'NAME': first_o.shipping_name, 
                        'ORDER_ID': f"#{group_id}", 
                        'DATE': timezone.now().strftime("%b %d, %Y"), 
                        'TOTAL': str(grand_total), 
                        'ITEMS_SUMMARY': items_summary, 
                        'ADDRESS': f"{first_o.shipping_address}, {first_o.shipping_city}", 
                        'DELIVERY_TIME': store.delivery_time, 
                        'STORE_NAME': store.name
                    }
                    email_tasks.append({'to': first_o.shipping_email, 'template': 4, 'params': c_params, 'sender': ORDER_SENDER})

                # 💎 TRANSACTION COMMITTED. NOW SAFE TO SEND EMAILS
                for task in email_tasks:
                    _send_brevo(task['to'], task['template'], task['params'], task['sender'])

                return redirect('order_success_view', order_id=final_order_id)

            except ValueError as e:
                messages.error(request, str(e))
                return redirect('view_cart', store_id=store.id)
            
            except Exception as e:
                print(f"🛑 CRITICAL CHECKOUT ERROR: {str(e)}")
                raise e 

        else:
            messages.error(request, "Please check your form details.")
    else:
        form = CheckoutForm()
        payment_opts = []
        if store.payment_method in ['COD', 'BOTH']: payment_opts.append(('COD', 'Cash on Delivery'))
        if store.payment_method in ['OL', 'BOTH']: payment_opts.append(('ONLINE', 'Online Payment'))
        form.fields['payment_choice'].choices = payment_opts

    # Prepare Display Items
    cart_items = []
    for k, v in store_cart.items():
        v['key'] = k
        v['total'] = v['price'] * v['quantity']
        cart_items.append(v)

    return render(request, 'marketplace/checkout.html', {
        'store': store, 'form': form, 'cart_items': cart_items, 
        'subtotal': subtotal, 'delivery_fee': delivery, 
        'discount_amount': discount_amt, 'grand_total': grand_total
    })

@login_required
def checkout_direct(request, product_id):
    """
    Buy Now: Single Item Checkout with Unified ID
    """
    product = get_object_or_404(Product, id=product_id)
    store = product.store
    
    if product.stock < 1:
        messages.error(request, "Out of stock.")
        return redirect('product_detail', product_id=product.id)

    subtotal = float(product.price)
    delivery = float(store.delivery_charges)
    grand_total = subtotal + delivery
    
    payment_opts = []
    if store.payment_method in ['COD', 'BOTH']: payment_opts.append(('COD', 'Cash on Delivery'))
    if store.payment_method in ['OL', 'BOTH']: payment_opts.append(('ONLINE', 'Online Payment'))

    if request.method == 'POST':
        form = CheckoutForm(request.POST, request.FILES)
        form.fields['payment_choice'].choices = payment_opts
        
        if form.is_valid():
            email_tasks = []
            final_order_id = None

            try:
                with transaction.atomic():
                    # 1. Generate Unified ID
                    group_id = str(uuid.uuid4())[:8].upper()

                    product.stock -= 1
                    product.save()
                    if product.stock == 0: send_low_stock_email(product)

                    order = Order.objects.create(
                        customer=request.user,
                        store=store,
                        product=product,
                        order_group_id=group_id,
                        order_ref=group_id, 
                        selected_variant="Standard",
                        shipping_name=form.cleaned_data['shipping_name'],
                        shipping_email=form.cleaned_data['shipping_email'],
                        shipping_phone=form.cleaned_data['shipping_phone'],
                        shipping_address=form.cleaned_data['shipping_address'],
                        shipping_city=form.cleaned_data['shipping_city'],
                        payment_method_selected=form.cleaned_data['payment_choice'],
                        payment_screenshot=form.cleaned_data.get('payment_screenshot'),
                        quantity=1,
                        subtotal_price=subtotal,
                        delivery_fee=delivery,
                        total_price=grand_total,
                        status='Confirmed'
                    )
                    
                    final_order_id = order.id
                    
                    # Prepare Emails
                    items_summary = f"{order.quantity}x {order.product.name} ({order.selected_variant})"
                    c_params = {
                        'NAME': order.shipping_name, 
                        'ORDER_ID': str(order.id), 
                        'DATE': timezone.now().strftime("%b %d, %Y"), 
                        'TOTAL': str(order.total_price), 
                        'ITEMS_SUMMARY': items_summary, 
                        'ADDRESS': f"{order.shipping_address}, {order.shipping_city}", 
                        'DELIVERY_TIME': "3-5 Days", 
                        'STORE_NAME': order.product.store.name
                    }
                    email_tasks.append({'to': order.shipping_email, 'template': 4, 'params': c_params, 'sender': ORDER_SENDER})

                # Send Emails
                for task in email_tasks:
                    _send_brevo(task['to'], task['template'], task['params'], task['sender'])

                return redirect('order_success_view', order_id=final_order_id)

            except Exception as e:
                print(f"🛑 CRITICAL DIRECT CHECKOUT ERROR: {str(e)}")
                raise e
    else:
        form = CheckoutForm()
        form.fields['payment_choice'].choices = payment_opts

    return render(request, 'marketplace/checkout.html', {
        'store': store, 'form': form, 
        'cart_items': [{'name': product.name, 'price': product.price, 'quantity': 1, 'total': product.price, 'image_url': product.image.url if product.image else None}],
        'subtotal': subtotal, 'delivery_fee': delivery, 'grand_total': grand_total
    })

def order_success_view(request, order_id):
    main_order = get_object_or_404(Order, id=order_id)
    orders = Order.objects.filter(order_group_id=main_order.order_group_id)
    
    grand_total = sum(o.total_price for o in orders)
    subtotal = sum(o.subtotal_price for o in orders)
    discount_amount = sum(o.discount_amount for o in orders)
    delivery_fee = sum(o.delivery_fee for o in orders)

    return render(request, 'marketplace/order_success.html', {
        'store': main_order.store,
        'orders': orders,
        'grand_total': grand_total,
        'subtotal': subtotal,
        'discount_amount': discount_amount,
        'delivery_fee': delivery_fee,
        'group_id': main_order.order_group_id,
    })

#==============================================================================
# 11. NUKR TALASH (LEAD COMMAND CENTER VIEWS)
# ==============================================================================

@login_required
def create_talash(request):
    """
    Buyer View: Create a request AND Manage existing ones.
    """
    user_city = request.COOKIES.get('nukr_city', 'Karachi')
    
    # Fetch user's existing active requests
    my_requests = ProductRequest.objects.filter(customer=request.user, is_active=True).order_by('-created_at')

    if request.method == 'POST':
        form = TalashForm(request.POST, request.FILES)
        if form.is_valid():
            req = form.save(commit=False)
            req.customer = request.user
            req.city = user_city
            req.save()
            
            # Smart Notification Logic
            matching_stores = Store.objects.filter(
                city__iexact=req.city, 
                category=req.category
            ).select_related('owner')
            
            for store in matching_stores:
                if store.owner.email:
                    email_params = {
                        'VENDOR_NAME': store.owner.username,
                        'REQUEST_TITLE': req.title,
                        'BUDGET': str(req.budget),
                        'CITY': req.city,
                        'CUSTOMER_NAME': req.customer.username,
                        'FEED_URL': "https://nukr.store/talash/feed/" 
                    }
                    _send_brevo(store.owner.email, 10, email_params, SUPPORT_SENDER)

            messages.success(request, "Your request is live! Relevant sellers have been notified.")
            return redirect('create_talash') # Stay on page to see the new list
    else:
        form = TalashForm()
    
    return render(request, 'marketplace/talash/create.html', {
        'form': form,
        'my_requests': my_requests # Pass the list to the template
    })

@login_required
def delete_talash(request, request_id):
    """
    Allows a buyer to delete/close their own request.
    """
    talash_req = get_object_or_404(ProductRequest, id=request_id)
    
    # Security: Ensure only the owner can delete
    if talash_req.customer == request.user:
        talash_req.delete()
        messages.success(request, "Request removed successfully.")
    else:
        messages.error(request, "You cannot remove this request.")
        
    return redirect('create_talash')

@login_required
def talash_feed(request):
    """
    Seller View: The 'Lead Generation' Board (Command Center).
    Shows requests filtered by the seller's city AND Category.
    """
    # 1. Security: Only Store Owners allowed
    if not hasattr(request.user, 'stores') or not request.user.stores.exists():
        messages.warning(request, "You must own a store to see leads.")
        return redirect('create_store')

    # 2. Get the Seller's Primary Store
    store = request.user.stores.first() 
    
    # 3. 💎 SMART LOGIC: Filter by Store's City
    requests = ProductRequest.objects.filter(is_active=True)

    # 💎 CRITICAL FIX: Define Categories LOCALLY to avoid AttributeError
    # This prevents the crash "type object 'Store' has no attribute 'CATEGORY_CHOICES'"
    CATEGORY_OPTS = [
        ('FASHION', 'Fashion & Wearables'),
        ('TECH', 'Electronics & Gadgets'),
        ('HOME', 'Home & Lifestyle'),
        ('BEAUTY', 'Health & Beauty'),
        ('AUTO', 'Automotive & Parts'),
        ('FOOD', 'Food & Groceries'),
        ('OTHER', 'Other / Custom Request')
    ]

    # Filter logic from Sidebar
    filter_city = request.GET.get('city')
    filter_cat = request.GET.get('category')
    search_q = request.GET.get('q')

    # Apply City Filter (Default to store's city, unless overridden)
    if filter_city:
        requests = requests.filter(city__iexact=filter_city)
    elif not filter_city and not filter_cat and not search_q:
        # Default state: Show local leads
        requests = requests.filter(city__iexact=store.city)

    # Apply Category Filter
    if filter_cat:
        requests = requests.filter(category=filter_cat)
    
    # Apply Search
    if search_q:
        requests = requests.filter(
            Q(title__icontains=search_q) | 
            Q(description__icontains=search_q)
        )

    return render(request, 'marketplace/talash/feed.html', {
        'requests': requests.order_by('-created_at'),
        'store': store,
        'categories': CATEGORY_OPTS, # 💎 Using Local Definition
        'today': timezone.now()
    })

@login_required
def respond_to_talash(request, request_id):
    """
    The 'I Have This' Button Logic.
    Creates a chat and pre-fills the message.
    """
    # 1. Get the Request
    talash_req = get_object_or_404(ProductRequest, id=request_id)
    
    # 2. Get Seller's Store
    if not hasattr(request.user, 'stores'): return redirect('home')
    store = request.user.stores.first()

    # 3. Create/Get Conversation
    conversation, created = Conversation.objects.get_or_create(
        customer=talash_req.customer, 
        store=store
    )

    # 4. Auto-Send the "Lead Message"
    if created:
        Message.objects.create(
            conversation=conversation,
            sender=request.user,
            text=f" Hi! I saw your Talash request for '{talash_req.title}'. I have this item available in your budget."
        )

    return redirect('chat_room', conversation_id=conversation.id)

# ==============================================================================
# 12. CHAT COMMERCE (CUSTOM OFFERS)
# ==============================================================================

@login_required
@require_POST
def create_custom_offer(request, conversation_id):
    """
    Allows a seller to create a 'Hidden Product' instantly inside the chat
    and send it as a buyable card to the customer.
    """
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    # Security: Only the store owner can create offers
    if request.user != conversation.store.owner:
        return JsonResponse({'status': 'error', 'message': 'Only sellers can make offers.'}, status=403)

    # 1. Create the 'Ghost' Product
    # We set minimal fields. You might want to filter 'is_active=True' in your mall_home view 
    # to prevent these from showing up in public search results if desired.
    try:
        product = Product.objects.create(
            store=conversation.store,
            name=request.POST.get('offer_title'),
            price=request.POST.get('offer_price'),
            description=f"Custom offer for {conversation.customer.username}",
            stock=1,
            image=request.FILES.get('offer_image'),
            is_active=True # Active so it can be bought
        )

        # 2. Generate the "Buy Now" Link
        buy_link = reverse('checkout_direct', args=[product.id])

        # 3. Send the Offer Message (Structured Text)
        # We use a special prefix [OFFER] so the template knows to render a card
        offer_text = (
            f"[OFFER]\n"
            f"Title: {product.name}\n"
            f"Price: {product.price}\n"
            f"Link: {buy_link}\n"
            f"Image: {product.image.url if product.image else ''}"
        )

        Message.objects.create(
            conversation=conversation,
            sender=request.user,
            text=offer_text
        )
        
        # 4. Update Conversation Timestamp
        conversation.updated_at = timezone.now()
        conversation.save()

        return JsonResponse({'status': 'success'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# ==================== HELPERS ====================
def send_low_stock_email(product):
    params = {'VENDOR_NAME': product.store.owner.username, 'PRODUCT_NAME': product.name, 'STORE_ID': str(product.store.id)}
    _send_brevo(product.store.owner.email, 8, params, SUPPORT_SENDER)

def send_cancelled_email(order, reason):
    params = {'NAME': order.shipping_name, 'ORDER_ID': str(order.id), 'REASON': reason}
    _send_brevo(order.shipping_email, 9, params, SUPPORT_SENDER)

def send_status_email(order, status):
    if status == 'Pending': return 
    msgs = {'Shipped': 'Your package is on the way!', 'Delivered': 'Your package has been delivered.'}
    params = {'STATUS': status, 'ORDER_ID': str(order.id), 'STATUS_MESSAGE': msgs.get(status, 'Updated'), 'PRODUCT_NAME': order.product.name, 'NAME': order.shipping_name, 'QTY': str(order.quantity)}
    _send_brevo(order.shipping_email, 6, params, ORDER_SENDER)