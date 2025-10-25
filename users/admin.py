from django.contrib import admin
from .models import UserProfile, UserGoogleToken, GmailCredential


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "email", "phone", "occupation", "income")


@admin.register(UserGoogleToken)
class UserGoogleTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "client_id", "scopes")


@admin.register(GmailCredential)
class GmailCredentialAdmin(admin.ModelAdmin):
    list_display = ("user",)
