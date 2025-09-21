import uuid

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from .models import UploadedFile, UserProfile, Phase
from .forms import FileUploadForm, CreateUserForm
from django.db.models import Sum
from django.contrib import messages
from django.http import FileResponse
import mimetypes
import os
from .forms import CreateUserForm
from urllib.parse import quote
import boto3
from botocore.client import Config
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from botocore.exceptions import ClientError
def get_current_phase():
    phase = Phase.objects.first()
    return phase.is_phase_one if phase else True


@login_required
def home(request):
    profile = UserProfile.objects.get(user=request.user)
    is_phase_one = get_current_phase()
    if request.user.is_superuser:
        return redirect('admin_dashboard')
    elif profile.user_type == 'FieldManager' and not is_phase_one:
        return redirect('field_manager_dashboard')

    used_storage = UploadedFile.objects.filter(user=request.user).aggregate(total=Sum('size'))['total'] or 0
    allowed_storage = profile.allowed_storage
    percentage_used = (used_storage / allowed_storage * 100) if allowed_storage > 0 else 0

    files = UploadedFile.objects.filter(user=request.user)

    if request.method == 'POST' and (
            profile.user_type == 'Normal' or (profile.user_type == 'FieldManager' and is_phase_one)):
        form = FileUploadForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            new_file = form.save(commit=False)
            new_file.user = request.user
            existing_file = UploadedFile.objects.filter(user=request.user, field=new_file.field).exists()
            if existing_file:
                form.add_error('field', "شما قبلاً فایلی در این رشته آپلود کرده‌اید. ابتدا فایل قبلی را حذف کنید.")
            elif used_storage + new_file.file.size > allowed_storage:
                form.add_error(None, "آپلود از حد مجاز فضای ذخیره‌سازی شما فراتر می‌رود.")
            else:
                new_file.save()
                return redirect('home')
    else:
        form = FileUploadForm(user=request.user)

    context = {
        'form': form,
        'files': files,
        'used_storage': used_storage,
        'allowed_storage': allowed_storage,
        'percentage_used': percentage_used,
        'is_normal_user': profile.user_type == 'Normal' or (profile.user_type == 'FieldManager' and is_phase_one),
    }
    return render(request, 'home.html', context)


@login_required
def delete_file(request, file_id):
    profile = UserProfile.objects.get(user=request.user)
    is_phase_one = get_current_phase()
    if not (profile.user_type == 'Normal' or (profile.user_type == 'FieldManager' and is_phase_one)):
        return redirect('home')
    file = get_object_or_404(UploadedFile, id=file_id, user=request.user)
    if file.file:
        try:
            file.file.delete()
        except ValueError:
            pass
    file.delete()
    return redirect('home')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_dashboard(request):
    # دریافت یا ایجاد نمونه Phase
    phase, created = Phase.objects.get_or_create(id=1, defaults={'is_phase_one': True})

    if request.method == 'POST':
        if 'phase_select' in request.POST:  # پردازش تغییر فاز
            selected_phase = request.POST.get('phase_select')
            if selected_phase == '1':  # فاز اول
                phase.is_phase_one = True
            elif selected_phase == '2':  # فاز دوم
                phase.is_phase_one = False
            phase.save()
            messages.success(request, 'فاز پروژه با موفقیت به‌روزرسانی شد.')
            return redirect('admin_dashboard')
        elif 'create_user' in request.POST:  # پردازش ایجاد کاربر
            form = CreateUserForm(request.POST)
            if form.is_valid():
                user = form.save()
                # استفاده از get_or_create برای جلوگیری از خطای UNIQUE
                profile, created = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'user_type': form.cleaned_data['user_type'],
                        'region': form.cleaned_data['region'],
                        'allowed_storage': form.cleaned_data.get('allowed_storage_gb', 0) * 1024 * 1024 * 1024,
                        'field': form.cleaned_data.get('field')  # فقط برای FieldManager
                    }
                )
                # اگر پروفایل جدید نباشد، آن را به‌روزرسانی کنید
                if not created:
                    profile.user_type = form.cleaned_data['user_type']
                    profile.region = form.cleaned_data['region']
                    profile.allowed_storage = form.cleaned_data.get('allowed_storage_gb', 0) * 1024 * 1024 * 1024
                    profile.field = form.cleaned_data.get('field')
                    profile.save()

                messages.success(request, 'کاربر با موفقیت ایجاد شد.')
                return redirect('admin_dashboard')
            else:
                messages.error(request, 'خطا در ایجاد کاربر. لطفاً اطلاعات را بررسی کنید.')
                # تعریف user_data برای زمانی که فرم نامعتبر است
                user_data = []
                for profile in UserProfile.objects.select_related('user').all():
                    if profile.user:
                        used_storage = UploadedFile.objects.filter(user=profile.user).aggregate(total=Sum('size'))[
                                           'total'] or 0
                        files = UploadedFile.objects.filter(user=profile.user)
                        user_data.append(
                            {'profile': profile, 'used_storage': used_storage, 'files': files, 'user': profile.user})
                context = {
                    'phase': phase,
                    'user_data': user_data,
                    'form': form  # فرم با خطاها به تمپلیت برگردانده می‌شود
                }
                return render(request, 'admin_dashboard.html', context)

    # محاسبه اطلاعات کاربران برای حالت GET
    user_data = []
    for profile in UserProfile.objects.select_related('user').all():
        if profile.user:
            used_storage = UploadedFile.objects.filter(user=profile.user).aggregate(total=Sum('size'))['total'] or 0
            files = UploadedFile.objects.filter(user=profile.user)
            user_data.append({'profile': profile, 'used_storage': used_storage, 'files': files, 'user': profile.user})

    context = {
        'phase': phase,
        'user_data': user_data,
        'form': CreateUserForm()
    }
    return render(request, 'admin_dashboard.html', context)


@login_required
def admin_delete_file(request, file_id):
    if not request.user.is_superuser:
        return redirect('home')
    file = get_object_or_404(UploadedFile, id=file_id)
    if file.file:
        try:
            file.file.delete()
        except ValueError:
            pass
    file.delete()
    return redirect('admin_dashboard')


@login_required
def admin_delete_user(request, user_id):
    if not request.user.is_superuser:
        return redirect('home')
    user = get_object_or_404(User, id=user_id)
    if not user.is_superuser:
        files = UploadedFile.objects.filter(user=user)
        for file in files:
            if file.file:
                try:
                    file.file.delete()
                except ValueError:
                    pass
            file.delete()
        user.delete()
        messages.success(request, 'کاربر و فایل‌هایش با موفقیت حذف شدند.')
    else:
        messages.error(request, 'نمی‌توان سوپریوزر را حذف کرد.')
    return redirect('admin_dashboard')


@login_required
def download_file(request, file_id):
    file_obj = get_object_or_404(UploadedFile, id=file_id)
    profile = UserProfile.objects.get(user=request.user)
    is_phase_one = get_current_phase()

    if not (request.user.is_superuser or file_obj.user == request.user or
            (profile.user_type == 'FieldManager' and not is_phase_one and file_obj.field == profile.field)):
        return redirect('home')

    file_path = file_obj.file.path
    file_name = os.path.basename(file_path)
    content_type, _ = mimetypes.guess_type(file_path)

    if not content_type:
        content_type = 'application/octet-stream'

    encoded_file_name = quote(file_name)

    # تنظیمات پاسخ برای دانلود
    response = FileResponse(open(file_path, 'rb'), content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename*=UTF-8\'\'{encoded_file_name}'

    return response


@login_required
def field_manager_dashboard(request):
    profile = UserProfile.objects.get(user=request.user)
    is_phase_one = get_current_phase()
    if profile.user_type != 'FieldManager' or is_phase_one:
        return redirect('home')

    regions = UserProfile.REGION_CHOICES
    region_display_names = dict(regions)
    files_by_region = {}
    for region_code, region_name in regions:
        region_users = UserProfile.objects.filter(region=region_code)
        users_files = []
        for user_profile in region_users:
            user_files = UploadedFile.objects.filter(user=user_profile.user, field=profile.field)
            if user_files.exists():
                users_files.append({
                    'user': user_profile.user,
                    'files': user_files
                })
        if users_files:
            files_by_region[region_code] = {
                'display_name': region_name,
                'users_files': users_files
            }

    own_files = UploadedFile.objects.filter(user=request.user)
    context = {
        'files_by_region': files_by_region,
        'regions': regions,
        'manager_field': dict(UserProfile.FIELD_CHOICES).get(profile.field),
        'own_files': own_files,
    }
    return render(request, 'field_manager_dashboard.html', context)


@login_required
def field_manager_delete_file(request, file_id):
    profile = UserProfile.objects.get(user=request.user)
    is_phase_one = get_current_phase()
    if profile.user_type != 'FieldManager' or is_phase_one:
        return redirect('home')
    file = get_object_or_404(UploadedFile, id=file_id, field=profile.field)
    if file.file:
        try:
            file.file.delete()
        except ValueError:
            pass
    file.delete()
    return redirect('field_manager_dashboard')



@csrf_exempt
def generate_upload_url(request):
    if request.method == 'POST':
        file_name = request.POST.get('file_name', f'upload_{uuid.uuid4()}.ext')
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        endpoint_url = settings.AWS_S3_ENDPOINT_URL

        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=endpoint_url
        )

        try:
            presigned_url = s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': file_name,
                    'ACL': 'private'
                },
                ExpiresIn=36000
            )
            return JsonResponse({'upload_url': presigned_url, 'file_key': file_name})
        except ClientError as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid method'}, status=405)