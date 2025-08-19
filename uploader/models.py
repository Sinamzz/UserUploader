from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    allowed_storage = models.BigIntegerField(default=50 * 1024 * 1024 * 1024)  # 50 GB in bytes


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


class UploadedFile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    title = models.CharField(max_length=255, blank=True)
    size = models.BigIntegerField(default=0)  # Size in bytes
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.size = self.file.size
        super().save(*args, **kwargs)
