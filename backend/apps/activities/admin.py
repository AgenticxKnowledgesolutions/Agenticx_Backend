from django.contrib import admin
from apps.activities.models import Activity

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'price', 'is_free', 'duration', 'created_at')
    list_filter = ('is_free', 'created_at')
    search_fields = ('title', 'description')
    ordering = ('-created_at',)
