from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, UploadedFile
from django.utils.html import format_html

class UploadedFileInline(admin.TabularInline):
    model = UploadedFile
    extra = 0
    fields = ('title', 'file', 'size', 'download_link', 'delete_button')
    readonly_fields = ('download_link', 'delete_button')

    def download_link(self, obj):
        if obj.file:
            return format_html('<a href="{}" download>Download</a>', obj.file.url)
        return "-"
    download_link.short_description = "Download"

    def delete_button(self, obj):
        return format_html('<a href="/admin/uploader/uploadedfile/{}/delete/" class="grp-state-focus grp-remove">Delete</a>', obj.id)
    delete_button.short_description = "Delete"

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ('allowed_storage',)

class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline, UploadedFileInline)

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)