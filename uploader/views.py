import uuid

from botocore.config import Config
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from .models import UploadedFile, UserProfile, Phase
from .forms import FileUploadForm, CreateUserForm
from django.db.models import Sum
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import boto3
from botocore.exceptions import ClientError
from datetime import datetime


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


@csrf_exempt
@login_required
def save_file_metadata(request):
    if request.method == 'POST':
        file_key = request.POST.get('file_key')
        field = request.POST.get('field')
        size = request.POST.get('size')
        profile = UserProfile.objects.get(user=request.user)
        is_phase_one = get_current_phase()

        # توی فاز دوم، هیچ‌کس نمی‌تونه آپلود کنه
        if not is_phase_one:
            return JsonResponse({'error': 'در فاز دوم، آپلود فایل غیرفعال است. فقط مشاهده و حذف امکان‌پذیر است.'}, status=403)

        # توی فاز اول، فقط Normal و Field Manager می‌تونن آپلود کنن
        if not (profile.user_type == 'Normal' or profile.user_type == 'FieldManager'):
            return JsonResponse({'error': 'شما اجازه آپلود ندارید'}, status=403)

        used_storage = UploadedFile.objects.filter(user=request.user).aggregate(total=Sum('size'))['total'] or 0
        try:
            size = int(size)
            if used_storage + size > profile.allowed_storage:
                return JsonResponse({'error': 'آپلود از حد مجاز فضای ذخیره‌سازی شما فراتر می‌رود'}, status=400)
        except ValueError:
            return JsonResponse({'error': 'اندازه فایل نامعتبر است'}, status=400)

        existing_file = UploadedFile.objects.filter(user=request.user, field=field).exists()
        if existing_file:
            return JsonResponse({'error': 'شما قبلاً فایلی در این رشته آپلود کرده‌اید'}, status=400)

        try:
            UploadedFile.objects.create(
                user=request.user,
                file_key=file_key,
                field=field,
                size=size
            )
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid method'}, status=405)


@csrf_exempt
@login_required
def generate_upload_url(request):
    if request.method == 'POST':
        file_name = request.POST.get('file_name', f'upload_{uuid.uuid4()}')
        file_type = request.POST.get('file_type', 'application/octet-stream')
        current_date = datetime.now().strftime('%Y/%m/%d')
        file_key = file_name
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        endpoint_url = settings.AWS_S3_ENDPOINT_URL

        s3_client = boto3.client('s3',
                          endpoint_url='https://c589428.parspack.net',
                          region_name='us-east-1',
                          config=Config(signature_version='s3v4'),
                          aws_access_key_id='3pybWMXMRKvlYrJU',
                          aws_secret_access_key='1wPlGLzHQCj5hejQBHcYDRZx8yaDfNpF'
                          )

        response = s3_client.list_objects_v2(Bucket='c589428')
        print(response)

        try:
            print("*********")
            print(file_name)
            print("*********")
            presigned_url = s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': "c589428",
                    'Key': file_key,
                },
                ExpiresIn=3600
            )
            return JsonResponse({
                'upload_url': presigned_url,
                'file_key': file_key,
                'content_type': file_type
            })
        except ClientError as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid method'}, status=405)

@login_required
def delete_file(request, file_id):
    profile = UserProfile.objects.get(user=request.user)
    is_phase_one = get_current_phase()
    if not (profile.user_type == 'Normal' or (profile.user_type == 'FieldManager' and is_phase_one)):
        return redirect('home')
    file = get_object_or_404(UploadedFile, id=file_id, user=request.user)

    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL
    )
    try:
        s3_client.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=file.file_key)
    except ClientError as e:
        messages.error(request, f'خطا در حذف فایل از bucket: {str(e)}')

    file.delete()
    messages.success(request, 'فایل با موفقیت حذف شد.')
    return redirect('home')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_dashboard(request):
    phase, created = Phase.objects.get_or_create(id=1, defaults={'is_phase_one': True})

    if request.method == 'POST':
        if 'phase_select' in request.POST:
            selected_phase = request.POST.get('phase_select')
            phase.is_phase_one = selected_phase == '1'
            phase.save()
            messages.success(request, 'فاز پروژه با موفقیت به‌روزرسانی شد.')
            return redirect('admin_dashboard')
        elif 'create_user' in request.POST:
            form = CreateUserForm(request.POST)
            if form.is_valid():
                user = form.save()
                messages.success(request, 'کاربر با موفقیت ایجاد شد.')
                return redirect('admin_dashboard')
            else:
                messages.error(request, 'خطا در ایجاد کاربر. لطفاً اطلاعات را بررسی کنید.')
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
                    'form': form
                }
                return render(request, 'admin_dashboard.html', context)

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

    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL
    )
    try:
        s3_client.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=file.file_key)
    except ClientError as e:
        messages.error(request, f'خطا در حذف فایل از bucket: {str(e)}')

    file.delete()
    messages.success(request, 'فایل با موفقیت حذف شد.')
    return redirect('admin_dashboard')


@login_required
def admin_delete_user(request, user_id):
    if not request.user.is_superuser:
        return redirect('home')
    user = get_object_or_404(User, id=user_id)
    if not user.is_superuser:
        files = UploadedFile.objects.filter(user=user)
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=settings.AWS_S3_ENDPOINT_URL
        )
        for file in files:
            try:
                s3_client.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=file.file_key)
            except ClientError as e:
                messages.error(request, f'خطا در حذف فایل از bucket: {str(e)}')
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
        return JsonResponse({'error': 'شما اجازه دانلود این فایل را ندارید'}, status=403)

    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL
    )
    try:
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Key': file_obj.file_key},
            ExpiresIn=3600
        )
        return JsonResponse({'download_url': presigned_url})
    except ClientError as e:
        return JsonResponse({'error': str(e)}, status=400)


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

    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL
    )
    try:
        s3_client.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=file.file_key)
    except ClientError as e:
        messages.error(request, f'خطا در حذف فایل از bucket: {str(e)}')

    file.delete()
    messages.success(request, 'فایل با موفقیت حذف شد.')
    return redirect('field_manager_dashboard')

