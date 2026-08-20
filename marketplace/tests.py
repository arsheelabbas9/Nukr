import json
import shutil
import tempfile
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from django.conf import settings

# Import YOUR models
from .models import (
    Store, Product, Order, ProductImage, ProductVariantType, ProductVariantItem, 
    DiscountCode, StoreVerification, CouponUsage, Review, Collection, UserProfile,
    StoreWallet, Conversation, Message, ProductRequest
)

# 1. Create a temporary media root for tests
TEMP_MEDIA_ROOT = tempfile.mkdtemp()

# 🛡️ GLOBAL OVERRIDE: Forces ALL ImageFields to use local temp storage
@override_settings(
    MEDIA_ROOT=TEMP_MEDIA_ROOT,
    DEFAULT_FILE_STORAGE='django.core.files.storage.FileSystemStorage',
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
)
class NukrTitaniumFullSuite(TestCase):
    """
    🛡️ TITANIUM FULL-STACK QA SUITE
    Tests based strictly on the provided views.py logic.
    """

    @classmethod
    def tearDownClass(cls):
        # Cleanup temp media after tests
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def get_new_image(self):
        """Helper to create a fresh image file for every usage to avoid Seek/Empty errors."""
        img_content = (
            b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x05\x04\x04'
            b'\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44'
            b'\x01\x00\x3b'
        )
        return SimpleUploadedFile("test.gif", img_content, content_type="image/gif")

    def setUp(self):
        """
        🏗️ SETUP: Infrastructure for the Marketplace
        """
        self.client = Client()
        
        # 1. Users
        self.seller = User.objects.create_user('seller', 'seller@nukr.com', 'Pass1234')
        self.buyer = User.objects.create_user('buyer', 'buyer@nukr.com', 'Pass1234')

        # 3. Store
        self.store = Store(
            owner=self.seller,
            name="Outfitters",
            city="Karachi",
            category="FASHION",
            delivery_charges=200,
            is_verified=True,
            payment_method='BOTH' 
        )
        self.store.image.save('store.gif', self.get_new_image(), save=False)
        self.store.save()

        # 4. Product (Simple)
        self.product = Product(
            store=self.store,
            name="Black Tee",
            price=1000,
            stock=10,
            is_active=True
        )
        self.product.image.save('prod.gif', self.get_new_image(), save=False)
        self.product.save()

        # 5. Product (With Variants)
        self.v_product = Product(
            store=self.store,
            name="Sneakers",
            price=5000,
            stock=5,
            is_active=True
        )
        self.v_product.image.save('vprod.gif', self.get_new_image(), save=False)
        self.v_product.save()

        # Create Variant Type & Item
        self.v_type = ProductVariantType.objects.create(product=self.v_product, name="Size")
        self.v_item = ProductVariantItem.objects.create(
            variant_type=self.v_type, 
            value="42", 
            stock=5, 
            price=5500 
        )

    # ======================================================================
    # 🛒 SECTION 1: CART LOGIC
    # ======================================================================

    def test_add_simple_product_to_cart(self):
        """Test adding a non-variant product to session cart."""
        url = reverse('add_to_cart', args=[self.product.id])
        response = self.client.post(url, {'quantity': 2})
        
        self.assertEqual(response.status_code, 302) 
        
        cart = self.client.session['cart']
        store_id = str(self.store.id)
        
        self.assertIn(store_id, cart)
        
        key = f"{self.product.id}_Standard"
        self.assertIn(key, cart[store_id])
        self.assertEqual(cart[store_id][key]['quantity'], 2)
        self.assertEqual(cart[store_id][key]['price'], 1000.0)

    def test_add_variant_product_to_cart(self):
        """Test adding a product with variants (Size: 42)."""
        url = reverse('add_to_cart', args=[self.v_product.id])
        
        data = {
            'quantity': 1,
            f'variant_{self.v_type.name}': self.v_item.value
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        
        cart = self.client.session['cart']
        store_id = str(self.store.id)
        
        key = f"{self.v_product.id}_42"
        
        self.assertIn(key, cart[store_id])
        self.assertEqual(cart[store_id][key]['price'], 5500.0) 

    # ======================================================================
    # 💳 SECTION 2: CHECKOUT & EMAILS
    # ======================================================================

    @patch('marketplace.views.requests.post') 
    def test_checkout_flow(self, mock_post):
        """
        Full integration test: Login -> Cart -> Checkout -> DB -> Email.
        """
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        self.client.force_login(self.buyer)

        # 1. Setup Session Cart
        session = self.client.session
        store_id = str(self.store.id)
        item_key = f"{self.product.id}_Standard"
        
        session['cart'] = {
            store_id: {
                item_key: {
                    'product_id': self.product.id,
                    'name': self.product.name,
                    'price': 1000.0,
                    'quantity': 2,
                    'variant': 'Standard',
                    'variant_ids': []
                }
            }
        }
        session.save()

        # 2. Submit Checkout
        url = reverse('checkout', args=[self.store.id])
        data = {
            'shipping_name': 'Test User',
            'shipping_email': 'test@user.com',
            'shipping_phone': '03001234567',
            'shipping_address': 'House 123',
            'shipping_city': 'Karachi',
            'payment_choice': 'COD'
        }
        response = self.client.post(url, data)

        # 3. Verify Redirect
        self.assertEqual(response.status_code, 302)
        self.assertIn('/order/success/', response.url)

        # 4. Verify DB Order
        order = Order.objects.first()
        self.assertIsNotNone(order)
        self.assertEqual(order.total_price, 2200) # (1000*2) + 200 delivery
        self.assertEqual(order.store, self.store)

        # 5. Verify Email Trigger
        self.assertEqual(mock_post.call_count, 2)

    # ======================================================================
    # 🔍 SECTION 3: MALL SEARCH & FILTERS
    # ======================================================================

    def test_mall_search(self):
        """Test search query filtering."""
        response = self.client.get(reverse('home'), {'q': 'Outfitters'})
        self.assertContains(response, 'Outfitters')
        
        response = self.client.get(reverse('home'), {'q': 'NonExistent'})
        self.assertNotContains(response, 'Outfitters')

    def test_mall_city_filter_cookie(self):
        """Test if 'nukr_city' cookie filters results."""
        # Create Lahore store
        store = Store(
            owner=self.seller, name="Lahore Store", city="Lahore", slug="lh-store"
        )
        store.image.save('lh.gif', self.get_new_image(), save=False)
        store.save()
        
        self.client.cookies['nukr_city'] = 'Karachi'
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'Outfitters')
        self.assertNotContains(response, 'Lahore Store')

    # ======================================================================
    # 🕵️ SECTION 4: NUKR TALASH (Reverse Marketplace)
    # ======================================================================

    @patch('marketplace.views.requests.post')
    def test_create_talash_request(self, mock_post):
        """Test creating a lead and notifying sellers."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        self.client.force_login(self.buyer)
        
        url = reverse('create_talash')
        data = {
            'title': 'Need White Sneakers',
            'category': 'FASHION',
            'budget': 5000,
            'description': 'Looking for size 42 white sneakers.',
            'reference_image': self.get_new_image()
        }
        
        self.client.cookies['nukr_city'] = 'Karachi'
        
        response = self.client.post(url, data)
        
        talash = ProductRequest.objects.first()
        self.assertIsNotNone(talash)
        self.assertEqual(talash.title, 'Need White Sneakers')
        self.assertEqual(talash.city, 'Karachi')
        
        self.assertTrue(mock_post.called)

    def test_talash_feed_access(self):
        """Test that only store owners can see the feed."""
        self.client.force_login(self.buyer)
        response = self.client.get(reverse('talash_feed'))
        self.assertEqual(response.status_code, 302) 

        self.client.force_login(self.seller)
        response = self.client.get(reverse('talash_feed'))
        self.assertEqual(response.status_code, 200)

    # ======================================================================
    # 💬 SECTION 5: CHAT & JSON APIs
    # ======================================================================

    def test_send_message_api(self):
        """Test the AJAX message sending endpoint."""
        self.client.force_login(self.buyer)
        
        convo = Conversation.objects.create(customer=self.buyer, store=self.store)
        
        url = reverse('send_message_api', args=[convo.id])
        data = {'text': 'Is this available?'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 200)
        json_data = json.loads(response.content)
        self.assertEqual(json_data['status'], 'success')
        
        msg = Message.objects.first()
        self.assertEqual(msg.text, 'Is this available?')

    def test_custom_offer_creation(self):
        """Test seller creating a 'Ghost Product' offer in chat."""
        self.client.force_login(self.seller)
        convo = Conversation.objects.create(customer=self.buyer, store=self.store)
        
        url = reverse('create_custom_offer', args=[convo.id])
        data = {
            'offer_title': 'Special Discount Item',
            'offer_price': 800,
            'offer_image': self.get_new_image()
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        
        ghost_prod = Product.objects.get(name='Special Discount Item')
        self.assertEqual(ghost_prod.price, 800)
        
        msg = Message.objects.last()
        self.assertIn("[OFFER]", msg.text)
        self.assertIn(str(ghost_prod.id), msg.text)

    # ======================================================================
    # ⚙️ SECTION 6: VENDOR DASHBOARD & KYC
    # ======================================================================

    @patch('marketplace.views.requests.post')
    def test_create_store(self, mock_post):
        """Test store creation logic and notification."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        new_user = User.objects.create_user('newguy', 'new@nukr.com', 'pass')
        self.client.force_login(new_user)
        
        url = reverse('create_store')
        
        # 💎 FIXED: Added 'delivery_time' because your model requires it
        data = {
            'name': 'New Shop',
            'description': 'Desc',
            'city': 'Lahore',
            'category': 'TECH',
            'delivery_charges': 100,
            'payment_method': 'COD',
            'delivery_time': '2-3 Days', # Added this field
            'image': self.get_new_image() 
        }
        
        response = self.client.post(url, data)
        
        if response.status_code == 200:
            print("Create Store Form Errors:", response.context['form'].errors)

        self.assertTrue(Store.objects.filter(name='New Shop').exists())
        store = Store.objects.get(name='New Shop')
        self.assertTrue(hasattr(store, 'storewallet'))
        self.assertTrue(mock_post.called) 

    def test_kyc_approval_flow(self):
        """Test that verifying a KYC document flips the Store's 'is_verified' switch."""
        new_store = Store(
            owner=self.seller, 
            name="Unverified Shop", 
            city="LHR",
            category="OTHER"
        )
        new_store.image.save('s.gif', self.get_new_image(), save=False)
        new_store.save()
        
        new_store.is_verified = False
        new_store.save()

        # Create KYC
        kyc = StoreVerification(
            store=new_store,
            full_name="Seller",
            cnic_number="42101",
            contact_number="0300",
            email="s@nukr.com",
            status='pending'
        )
        kyc.cnic_front.save('front.gif', self.get_new_image(), save=False)
        kyc.cnic_back.save('back.gif', self.get_new_image(), save=False)
        kyc.save()

        # Admin Approves
        kyc.status = 'approved'
        kyc.save()

        new_store.refresh_from_db()
        self.assertTrue(new_store.is_verified)

    def test_update_order_status(self):
        """Test seller updating order status."""
        self.client.force_login(self.seller)
        
        order = Order.objects.create(
            customer=self.buyer, product=self.product, store=self.store,
            total_price=1200, status='Pending'
        )
        
        url = reverse('update_order_status', args=[order.id])
        self.client.post(url, {'status': 'Shipped'})
        
        order.refresh_from_db()
        self.assertEqual(order.status, 'Shipped')