from django import forms
from .models import UploadedFile, UserProfile
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

class FileUploadForm(forms.ModelForm):
    class Meta:
        model = UploadedFile
        fields = ['field']
        labels = {'field': 'رشته'}

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            profile = UserProfile.objects.get(user=user)
            # اگر مدیر رشته است، باید اجازه دهد که رشته‌هایی که هنوز آپلود نشده‌اند، انتخاب شوند
            if profile.user_type == 'FieldManager':
                # برای مدیر رشته، تمام رشته‌هایی که هنوز فایل برای آنها آپلود نشده را نشان بده
                used_fields = UploadedFile.objects.filter(user=user).values_list('field', flat=True)
                available_choices = [(code, name) for code, name in UserProfile.FIELD_CHOICES if code not in used_fields]
                if available_choices:
                    self.fields['field'].choices = available_choices
                else:
                    self.fields['field'].disabled = True
                    self.fields['field'].help_text = "شما در تمام رشته‌ها فایل آپلود کرده‌اید. برای آپلود فایل جدید، ابتدا فایل‌های قبلی را حذف کنید."
            else:
                # برای کاربر عادی، فقط رشته‌هایی که هنوز آپلود نشده‌اند
                used_fields = UploadedFile.objects.filter(user=user).values_list('field', flat=True)
                available_choices = [(code, name) for code, name in UserProfile.FIELD_CHOICES if code not in used_fields]
                if available_choices:
                    self.fields['field'].choices = available_choices
                else:
                    self.fields['field'].disabled = True
                    self.fields['field'].help_text = "شما در تمام رشته‌ها فایل آپلود کرده‌اید. برای آپلود فایل جدید، ابتدا فایل‌های قبلی را حذف کنید."
class CreateUserForm(UserCreationForm):
    user_type = forms.ChoiceField(choices=UserProfile.USER_TYPE_CHOICES, label='نوع کاربر')
    region = forms.ChoiceField(choices=UserProfile.REGION_CHOICES, label='پژوهشسرا')
    allowed_storage_gb = forms.IntegerField(
        initial=0, label='فضای ذخیره‌سازی (گیگابایت)', required=False, min_value=0
    )
    field = forms.ChoiceField(choices=UserProfile.FIELD_CHOICES, label='رشته', required=False)

    class Meta:
        model = User
        fields = ['username', 'password1', 'password2', 'user_type', 'region', 'allowed_storage_gb', 'field']
        labels = {'username': 'نام کاربری', 'password1': 'رمز عبور', 'password2': 'تکرار رمز عبور'}

    def clean(self):
        cleaned_data = super().clean()
        user_type = cleaned_data.get('user_type')
        allowed_storage_gb = cleaned_data.get('allowed_storage_gb')
        field = cleaned_data.get('field')

        if not cleaned_data.get('region'):
            self.add_error('region', 'انتخاب پژوهشسرا الزامی است.')
        if user_type == 'Normal':
            if not allowed_storage_gb:
                self.add_error('allowed_storage_gb', 'فضای ذخیره‌سازی برای کاربر عادی الزامی است.')
            if field:
                self.add_error('field', 'کاربر عادی نمی‌تواند رشته انتخاب کند.')
            cleaned_data['field'] = None
        elif user_type == 'FieldManager':
            if not field:
                self.add_error('field', 'انتخاب رشته برای مدیر رشته الزامی است.')
            if not allowed_storage_gb:
                cleaned_data['allowed_storage_gb'] = 50  # پیش‌فرض 50 گیگابایت برای مدیر رشته
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
            # پروفایل به صورت خودکار توسط سیگنال post_save ساخته می‌شود
            profile = UserProfile.objects.get(user=user)
            profile.user_type = self.cleaned_data['user_type']
            profile.region = self.cleaned_data['region']
            profile.allowed_storage = self.cleaned_data['allowed_storage_gb'] * 1024 * 1024 * 1024
            profile.field = self.cleaned_data['field']
            profile.save()
        return user