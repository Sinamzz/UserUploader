from django.urls import path
from .views import home, delete_file, admin_dashboard, admin_delete_file, admin_delete_user, download_file, \
    field_manager_dashboard, field_manager_delete_file

urlpatterns = [
    path('', home, name='home'),
    path('delete/<int:file_id>/', delete_file, name='delete_file'),
    path('admin-dashboard/', admin_dashboard, name='admin_dashboard'),
    path('admin-delete/<int:file_id>/', admin_delete_file, name='admin_delete_file'),
    path('admin-delete-user/<int:user_id>/', admin_delete_user, name='admin_delete_user'),
    path('download/<int:file_id>/', download_file, name='download_file'),
    path('field-manager-dashboard/', field_manager_dashboard, name='field_manager_dashboard'),
    path('field-manager-delete/<int:file_id>/', field_manager_delete_file, name='field_manager_delete_file')
]