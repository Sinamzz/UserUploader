from django import forms
from .models import UploadedFile
from django.contrib.auth.models import User
from .models import UserProfile


class FileUploadForm(forms.ModelForm):
    class Meta:
        model = UploadedFile
        fields = ('file', 'title')


class CreateUserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    allowed_storage_gb = forms.IntegerField(initial=50, label='فضای مجاز (GB)')

    class Meta:
        model = User
        fields = ('username', 'password')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            profile = UserProfile.objects.get(user=user)
            profile.allowed_storage = self.cleaned_data['allowed_storage_gb'] * 1024 * 1024 * 1024
            profile.save()
        return user
