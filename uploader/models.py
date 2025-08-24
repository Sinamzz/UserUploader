from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Phase(models.Model):
    is_phase_one = models.BooleanField(default=True)  # True for Phase 1, False for Phase 2

@receiver(post_save, sender=Phase)
def ensure_single_phase(sender, instance, created, **kwargs):
    if created:
        Phase.objects.exclude(id=instance.id).delete()

class UserProfile(models.Model):
    REGION_CHOICES = [
        ('Mashhad', 'مشهد'),
        ('Quchan', 'قوچان'),
        ('Neyshabur', 'نیشابور'),
    ]

    USER_TYPE_CHOICES = [
        ('Normal', 'کاربر عادی'),
        ('FieldManager', 'مدیر رشته'),
    ]

    FIELD_CHOICES = [
        ('Literature', 'ادبیات و علوم انسانی'),
        ('LabSciences', 'آزمایشگاه علوم تجربی'),
        ('RoboticsAI', 'رباتیک و هوش مصنوعی'),
        ('Coding', 'کدنویسی'),
        ('Nanotechnology', 'نانوفناوری'),
        ('StemCells', 'سلول‌های بنیادی'),
        ('SpaceTech', 'فناوری‌های حوزه فضایی'),
        ('Astronomy', 'نجوم'),
        ('MedicinalPlants', 'گیاهان دارویی'),
        ('NuclearTech', 'علوم و فنون هسته‌ای'),
        ('RenewableEnergy', 'انرژی‌های نوین'),
        ('Biotechnology', 'زیست‌فناوری'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    allowed_storage = models.BigIntegerField(default=0)
    region = models.CharField(max_length=50, choices=REGION_CHOICES, blank=True, null=True)
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='Normal')
    field = models.CharField(max_length=50, choices=FIELD_CHOICES, blank=True, null=True)

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

class UploadedFile(models.Model):
    FIELD_CHOICES = UserProfile.FIELD_CHOICES

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    field = models.CharField(max_length=50, choices=FIELD_CHOICES)
    size = models.BigIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.size = self.file.size
        super().save(*args, **kwargs)