from django.contrib import admin
from .models import Review

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('name', 'rating', 'source', 'is_active', 'created_at')
    list_filter = ('rating', 'source', 'is_active')
    search_fields = ('name', 'review', 'role')
    ordering = ('-created_at',)
    list_editable = ('is_active',)

    fieldsets = (
        ("Basic Info", {
            "fields": ("name", "role", "image")
        }),
        ("Review Content", {
            "fields": ("rating", "review", "source")
        }),
        ("Status", {
            "fields": ("is_active",)
        }),
    )
