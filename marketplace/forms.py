from django import forms
from django.forms import ClearableFileInput
from .models import (
    Store, Product, Order, DiscountCode, 
    StoreVerification, Review, Collection, Message, ProductRequest # 💎 Added ProductRequest
)

# ==========================================
# 0. CONSTANTS & UTILS
# ==========================================

# 🏙️ COMPREHENSIVE CITY LIST FOR DROPDOWNS
PAKISTAN_CITIES = [
    ('', 'Choose your city...'),
    ('Lahore', 'Lahore'), ('Karachi', 'Karachi'), ('Islamabad', 'Islamabad'),
    ('Rawalpindi', 'Rawalpindi'), ('Faisalabad', 'Faisalabad'), ('Multan', 'Multan'),
    ('Peshawar', 'Peshawar'), ('Quetta', 'Quetta'), ('Gujranwala', 'Gujranwala'),
    ('Sialkot', 'Sialkot'), ('Bahawalpur', 'Bahawalpur'), ('Sargodha', 'Sargodha'),
    ('Sukkur', 'Sukkur'), ('Larkana', 'Larkana'), ('Sheikhupura', 'Sheikhupura'),
    ('Jhang', 'Jhang'), ('Gujrat', 'Gujrat'), ('Mardan', 'Mardan'),
    ('Kasur', 'Kasur'), ('Rahim Yar Khan', 'Rahim Yar Khan'), ('Sahiwal', 'Sahiwal'),
    ('Okara', 'Okara'), ('Wah Cantonment', 'Wah Cantonment'), ('Dera Ghazi Khan', 'Dera Ghazi Khan'),
    ('Mirpur Khas', 'Mirpur Khas'), ('Nawabshah', 'Nawabshah'), ('Mingora', 'Mingora'),
    ('Chiniot', 'Chiniot'), ('Kamoke', 'Kamoke'), ('Mandi Bahauddin', 'Mandi Bahauddin'),
    ('Jhelum', 'Jhelum'), ('Sadiqabad', 'Sadiqabad'), ('Khanewal', 'Khanewal'),
    ('Hafizabad', 'Hafizabad'), ('Kohat', 'Kohat'), ('Jacobabad', 'Jacobabad'),
    ('Shikarpur', 'Shikarpur'), ('Muzaffargarh', 'Muzaffargarh'), ('Khanpur', 'Khanpur'),
    ('Gojra', 'Gojra'), ('Bahawalnagar', 'Bahawalnagar'), ('Abbottabad', 'Abbottabad'),
    ('Muridke', 'Muridke'), ('Pakpattan', 'Pakpattan'), ('Khuzdar', 'Khuzdar'),
    ('Jaranwala', 'Jaranwala'), ('Chishtian', 'Chishtian'), ('Daska', 'Daska'),
    ('Muzaffarabad', 'Muzaffarabad'), ('Gilgit', 'Gilgit'), ('Skardu', 'Skardu')
]

class MultipleFileInput(ClearableFileInput):
    allow_multiple_selected = True

# ==========================================
# 1. STORE FORM
# ==========================================
class StoreForm(forms.ModelForm):
    city = forms.ChoiceField(
        choices=PAKISTAN_CITIES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    deliver_nationwide = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox', 'id': 'id_deliver_nationwide'})
    )

    class Meta:
        model = Store
        fields = [
            'name', 'description', 'category', 'city', 'image', # 💎 Added 'category'
            'delivery_time', 'delivery_charges', 'policy',
            'deliver_nationwide', 'secondary_cities',
            'facebook_link', 'instagram_link',
            'payment_method', 'card_payments_enabled',
            'bank_name', 'payment_account_title', 'payment_account_number'
        ]
        
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Butterfly Jewellery', 'class': 'form-input'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Tell us about your brand...', 'class': 'form-input'}),
            'category': forms.Select(attrs={'class': 'form-select'}), # 💎 Category Widget
            'policy': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Return & Privacy Policy...', 'class': 'form-input'}),
            'delivery_time': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 3-5 Business Days'}),
            'delivery_charges': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Standard Delivery Fee (PKR)'}),
            'facebook_link': forms.URLInput(attrs={'placeholder': 'https://facebook.com/... (Optional)', 'class': 'form-input'}),
            'instagram_link': forms.URLInput(attrs={'placeholder': 'https://instagram.com/... (Optional)', 'class': 'form-input'}),
            'payment_method': forms.Select(attrs={'class': 'form-select', 'id': 'id_payment_method'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. HBL, Meezan...'}),
            'payment_account_title': forms.TextInput(attrs={'placeholder': 'Account Title', 'class': 'form-input'}),
            'payment_account_number': forms.TextInput(attrs={'placeholder': 'IBAN / Account Number', 'class': 'form-input'}),
            'image': forms.FileInput(attrs={'class': 'form-file'}),
            'secondary_cities': forms.HiddenInput(),
            'card_payments_enabled': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if self.instance.pk is None:
            if Store.objects.filter(name__iexact=name).exists():
                raise forms.ValidationError("This store name is already taken. Please choose a unique one.")
        return name

# ==========================================
# 2. PRODUCT FORM
# ==========================================
class ProductForm(forms.ModelForm):
    # Multiple images handling for Gallery
    gallery_images = forms.FileField(
        widget=MultipleFileInput(attrs={'multiple': True, 'class': 'form-file'}), 
        required=False, 
        label="Gallery Images (Select Multiple)"
    )

    class Meta:
        model = Product
        fields = [
            'store', 'collection', 'name', 'description', 'price', 'old_price', 
            'stock', 'is_active', 'image'
        ]
        
        widgets = {
            'store': forms.Select(attrs={'class': 'form-select'}),
            'collection': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Butterfly Keychain'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 4}),
            'price': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Base Price'}),
            'old_price': forms.NumberInput(attrs={'class': 'form-input'}),
            'stock': forms.NumberInput(attrs={'class': 'form-input', 'min': '0', 'placeholder': 'Qty Available'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-file'}),
        }

    def __init__(self, user=None, store=None, *args, **kwargs):
        # Handle both direct 'store' kwarg (from views) and 'user' logic
        super().__init__(*args, **kwargs)
        
        # If a specific store is passed (from view), use it to filter collections
        if store:
            self.fields['store'].initial = store
            self.fields['store'].widget = forms.HiddenInput()
            self.fields['collection'].queryset = Collection.objects.filter(store=store)
        
        # Fallback for user-based filtering (legacy support)
        elif user and user.is_authenticated:
            self.fields['store'].queryset = Store.objects.filter(owner=user)
            self.fields['collection'].queryset = Collection.objects.filter(store__owner=user)
        else:
             self.fields['store'].queryset = Store.objects.none()
             self.fields['collection'].queryset = Collection.objects.none()

# ==========================================
# 3. CHECKOUT FORM
# ==========================================
class CheckoutForm(forms.ModelForm):
    shipping_city = forms.ChoiceField(
        choices=PAKISTAN_CITIES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    payment_choice = forms.ChoiceField(
        choices=[('COD', 'Cash on Delivery'), ('ONLINE', 'Online Payment')],
        widget=forms.RadioSelect(attrs={'class': 'payment-radio'})
    )

    class Meta:
        model = Order
        fields = [
            'shipping_name', 'shipping_email', 'shipping_phone', 
            'shipping_city', 'shipping_address', 'payment_screenshot'
        ]
        
        widgets = {
            'shipping_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Full Name'}),
            'shipping_email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Email Address'}),
            'shipping_phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '0300-1234567'}),
            'shipping_address': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'House #, Street, Area...'}),
            'payment_screenshot': forms.FileInput(attrs={'class': 'form-file', 'id': 'id_payment_screenshot'}),
        }

# ==========================================
# 4. COUPON FORMS
# ==========================================
class CouponApplyForm(forms.Form):
    code = forms.CharField(
        max_length=20, 
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter Discount Code'})
    )

class DiscountCodeForm(forms.ModelForm):
    valid_until = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}), 
        required=False
    )

    class Meta:
        model = DiscountCode
        fields = ['code', 'discount_type', 'value', 'active', 'valid_until']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. SUMMER10'}),
            'discount_type': forms.Select(attrs={'class': 'form-select'}),
            'value': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Enter Amount (Rs) or Percentage (%)'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
    
    def clean_code(self):
        code = self.cleaned_data.get('code')
        return code.upper() if code else code

# ==========================================
# 5. VERIFICATION FORM
# ==========================================
class StoreVerificationForm(forms.ModelForm):
    class Meta:
        model = StoreVerification
        fields = [
            'full_name', 'cnic_number', 'contact_number', 'email', 
            'office_address', 'cnic_front', 'cnic_back'
        ]
        
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'As appearing on CNIC'}),
            'cnic_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '42101-1234567-1'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '0300-1234567'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Official Business Email'}),
            'office_address': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Full physical address of your business'}),
            'cnic_front': forms.FileInput(attrs={'class': 'form-file'}),
            'cnic_back': forms.FileInput(attrs={'class': 'form-file'}),
        }
        
        labels = {
            'full_name': 'Full Legal Name',
            'cnic_front': 'Upload CNIC Front',
            'cnic_back': 'Upload CNIC Back',
        }

# ==========================================
# 6. REVIEW FORM
# ==========================================
class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment', 'image'] 
        widgets = {
            'rating': forms.Select(choices=[
                (5, '★★★★★ (5/5)'), 
                (4, '★★★★☆ (4/5)'), 
                (3, '★★★☆☆ (3/5)'), 
                (2, '★★☆☆☆ (2/5)'), 
                (1, '★☆☆☆☆ (1/5)')
            ], attrs={'class': 'form-select'}),
            'comment': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Share your experience...'}),
            'image': forms.FileInput(attrs={'class': 'form-file'}),
        }

# ==========================================
# 7. COLLECTION FORM
# ==========================================
class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = ['name', 'description', 'image'] 
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Winter Collection'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Optional description...'}), 
            'image': forms.FileInput(attrs={'class': 'form-file'}),
        }

# ==========================================
# 8. ORDER MANAGEMENT FORM
# ==========================================
class OrderUpdateForm(forms.ModelForm):
    """
    Used in manage_order.html for vendors to update status
    """
    class Meta:
        model = Order
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'})
        }

# ==========================================
# 9. CHAT SYSTEM FORM (💎 NEW FEATURE)
# ==========================================
class MessageForm(forms.ModelForm):
    """
    Handles user input for the chat system.
    Supports text and/or image.
    """
    class Meta:
        model = Message
        fields = ['text', 'image']
        widgets = {
            'text': forms.TextInput(attrs={
                'class': 'chat-input-field', 
                'placeholder': 'Type a message...',
                'autocomplete': 'off'
            }),
            # Image input is handled by a custom button/label in the UI, 
            # so we keep standard FileInput here
            'image': forms.FileInput(attrs={'class': 'hidden-chat-file-input', 'style': 'display:none;'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        text = cleaned_data.get("text")
        image = cleaned_data.get("image")

        # Validation: Message must have either text OR an image
        if not text and not image:
            raise forms.ValidationError("Message cannot be empty.")
        return cleaned_data

# ==========================================
# 10. NUKR TALASH FORM (💎 REVERSE MARKETPLACE)
# ==========================================
class TalashForm(forms.ModelForm):
    class Meta:
        model = ProductRequest
        fields = ['title', 'description', 'category', 'budget', 'reference_image']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Golden Bridal Clutch'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Describe exactly what you need...'}),
            'budget': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Max Price (Rs)'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'reference_image': forms.FileInput(attrs={'class': 'form-control'}),
        }