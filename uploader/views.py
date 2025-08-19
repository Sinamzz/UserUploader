from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import UploadedFile, UserProfile
from .forms import FileUploadForm, CreateUserForm
from django.db.models import Sum
from django.contrib import messages
from django.http import FileResponse
import mimetypes
import os


@login_required
def home(request):
    if request.user.is_superuser:
        return redirect('admin_dashboard')
    profile = UserProfile.objects.get(user=request.user)
    used_storage = UploadedFile.objects.filter(user=request.user).aggregate(total=Sum('size'))['total'] or 0
    allowed_storage = profile.allowed_storage
    percentage_used = (used_storage / allowed_storage * 100) if allowed_storage > 0 else 0

    files = UploadedFile.objects.filter(user=request.user)

    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            new_file = form.save(commit=False)
            new_file.user = request.user
            if used_storage + new_file.file.size > allowed_storage:
                form.add_error(None, "Upload would exceed your storage limit.")
            else:
                new_file.save()
                return redirect('home')
    else:
        form = FileUploadForm()

    context = {
        'form': form,
        'files': files,
        'used_storage': used_storage,
        'allowed_storage': allowed_storage,
        'percentage_used': percentage_used,
    }
    return render(request, 'home.html', context)


@login_required
def delete_file(request, file_id):
    file = get_object_or_404(UploadedFile, id=file_id, user=request.user)
    if file.file:
        try:
            file.file.delete()
        except ValueError:
            pass
    file.delete()
    return redirect('home')


@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        return redirect('home')

    users = User.objects.exclude(is_superuser=True)
    user_data = []
    for user in users:
        profile = UserProfile.objects.get(user=user)
        used_storage = UploadedFile.objects.filter(user=user).aggregate(total=Sum('size'))['total'] or 0
        files = UploadedFile.objects.filter(user=user)
        user_data.append({
            'user': user,
            'profile': profile,
            'used_storage': used_storage,
            'files': files,
        })

    if request.method == 'POST':
        form = CreateUserForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'User created successfully.')
            return redirect('admin_dashboard')
    else:
        form = CreateUserForm()

    context = {
        'user_data': user_data,
        'form': form,
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
    if not user.is_superuser:  # Prevent deleting superuser
        # Delete all files associated with the user
        files = UploadedFile.objects.filter(user=user)
        for file in files:
            if file.file:
                try:
                    file.file.delete()
                except ValueError:
                    pass
            file.delete()
        user.delete()
        messages.success(request, 'User and their files deleted successfully.')
    else:
        messages.error(request, 'Cannot delete superuser.')
    return redirect('admin_dashboard')


@login_required
def download_file(request, file_id):
    file_obj = get_object_or_404(UploadedFile, id=file_id)
    if not (request.user.is_superuser or file_obj.user == request.user):
        return redirect('home')

    file_path = file_obj.file.path
    # Get the file extension from the original file
    file_extension = os.path.splitext(file_path)[1] or '.bin'  # Fallback to .bin if no extension
    # Construct filename: username-title-fileid.format
    title = file_obj.title.replace(' ', '_') if file_obj.title else 'untitled'
    file_name = f"{file_obj.user.username}-{title}-{file_obj.id}{file_extension}"

    # Determine content type
    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = 'application/octet-stream'

    response = FileResponse(open(file_path, 'rb'), content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{file_name}"'
    return response