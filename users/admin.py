from django.contrib import admin
from .models import UserProfile, GmailCredential


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "email", "phone", "occupation", "income")



@admin.register(GmailCredential)
class GmailCredentialAdmin(admin.ModelAdmin):
    list_display = ("user",)
