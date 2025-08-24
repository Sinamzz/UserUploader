from django import forms
from .models import UploadedFile, UserProfile
from django.contrib.auth.models import User

class FileUploadForm(forms.ModelForm):
    class Meta:
        model = UploadedFile
        fields = ('file', 'field')
        labels = {'field': 'رشته'}

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            used_fields = UploadedFile.objects.filter(user=user).values_list('field', flat=True)
            available_choices = [(code, name) for code, name in UserProfile.FIELD_CHOICES if code not in used_fields]
            self.fields['field'].choices = available_choices
            if not available_choices:
                self.fields['field'].disabled = True
                self.fields['field'].help_text = "شما در تمام رشته‌ها فایل آپلود کرده‌اید. برای آپلود فایل جدید، ابتدا فایل‌های قبلی را حذف کنید."

class CreateUserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label='رمز عبور')
    allowed_storage_gb = forms.IntegerField(initial=50, label='فضای ذخیره‌سازی (گیگابایت)', required=False)
    region = forms.ChoiceField(choices=UserProfile.REGION_CHOICES, label='منطقه')
    user_type = forms.ChoiceField(choices=UserProfile.USER_TYPE_CHOICES, label='نوع کاربر')
    field = forms.ChoiceField(choices=UserProfile.FIELD_CHOICES, label='رشته', required=False)

    class Meta:
        model = User
        fields = ('username', 'password', 'user_type', 'region', 'allowed_storage_gb', 'field')
        labels = {'username': 'نام کاربری'}

    def clean(self):
        cleaned_data = super().clean()
        user_type = cleaned_data.get('user_type')
        if not cleaned_data.get('region'):
            self.add_error('region', 'انتخاب منطقه الزامی است.')
        if user_type == 'Normal':
            if not cleaned_data.get('allowed_storage_gb'):
                self.add_error('allowed_storage_gb', 'برای کاربر عادی، فضای ذخیره‌سازی الزامی است.')
            cleaned_data['field'] = None
        elif user_type == 'FieldManager':
            if not cleaned_data.get('field'):
                self.add_error('field', 'برای مدیر رشته، انتخاب رشته الزامی است.')
            cleaned_data['allowed_storage_gb'] = cleaned_data.get('allowed_storage_gb', 50)  # Default storage
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            profile = UserProfile.objects.get(user=user)
            profile.user_type = self.cleaned_data['user_type']
            profile.region = self.cleaned_data['region']
            profile.field = self.cleaned_data.get('field')
            profile.allowed_storage = self.cleaned_data.get('allowed_storage_gb', 0) * 1024 * 1024 * 1024
            profile.save()
        return user