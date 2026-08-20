from allauth.account.forms import LoginForm
from django import forms
from django.contrib.auth import get_user_model

class TitaniumLoginForm(LoginForm):
    def clean(self):
        # 1. Get the email user typed
        login = self.cleaned_data.get('login')
        
        # 2. INTERCEPTOR: Manually check if email exists in DB
        if login:
            User = get_user_model()
            # If email is NOT found, stop everything and yell "Unregistered"
            if not User.objects.filter(email=login).exists():
                raise forms.ValidationError("Email not registered")
        
        # 3. If email exists, let Django check the password standard way
        return super().clean()