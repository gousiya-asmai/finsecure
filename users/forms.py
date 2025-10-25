from django import forms
from django.contrib.auth.models import User
from .models import UserProfile


class UserUpdateForm(forms.ModelForm):
    """
    Form to update the default Django User fields.
    Example: username, email.
    """
    class Meta:
        model = User
        fields = ['username', 'email']


class ProfileUpdateForm(forms.ModelForm):
    """
    Form to update UserProfile fields (without financial_behavior).
    Includes profile photo, income, occupation, and personal info.
    """
    class Meta:
        model = UserProfile
        fields = [
            'name',
            'phone',
            'address',
            'dob',
            'gender',
            'occupation',
            'income',
            'profile_photo',   # ✅ profile photo field
        ]
        widgets = {
            'dob': forms.DateInput(attrs={'type': 'date'}),  # calendar picker
            'address': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Enter your address'
            }),
        }
