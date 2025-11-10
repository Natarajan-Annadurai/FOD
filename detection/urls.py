from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views


urlpatterns = [
    path('', views.login_view, name='login'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/tool-activity/', views.tool_activity_dashboard, name='tool_activity_dashboard'),
    path('tools-in-use/', views.tools_in_use, name='tools_in_use'),
    path('inventory/', views.inventory_view, name='inventory'),
    path('tool_creation/', views.tool_creation_view, name='tool_creation'),
    path('tool_creation/delete/<int:id>/', views.tool_delete, name='tool_delete'),
    path('tool_purchase/', views.tool_purchase_view, name='tool_purchase'),
    path('service-stations/create/', views.create_service_station, name='create_service_station'),
    path('service-station/<int:pk>/edit/', views.edit_service_station, name='edit_service_station'),
    path('service-station/<int:pk>/delete/', views.delete_service_station, name='delete_service_station'),
    path('service-stations/', views.service_station_list, name='service_station_list'),
    path('service-stations/<int:station_id>/units/create/', views.create_unit, name='create_unit'),
    path('service-stations/<int:station_id>/units/<int:unit_id>/delete/', views.delete_unit, name='delete_unit'),
    path('units/<int:unit_id>/trays/create/', views.create_tray, name='create_tray'),
    path('trays/<int:tray_id>/edit/', views.edit_tray, name='edit_tray'),
    path('trays/<int:tray_id>/delete/', views.delete_tray, name='delete_tray'),
    path('trays/<int:tray_id>/assign-tools/', views.assign_tools, name='assign_tools'),
    path('trays/<int:tray_id>/assigned-tools/', views.assigned_tools_list, name='assigned_tools_list'),
    path('assigned-tools/', views.global_assigned_tools, name='global_assigned_tools'),
    path('users/manage/', views.manage_users, name='manage_users'),
    path('users/assigned/', views.user_assigned_list, name='user_assigned_list'),
    path('inventory/update/', views.inventory_update_api, name='inventory_update_api'),
    path('api/detections/', views.receive_detections, name='receive_detections'),
    path('logout/', views.logout_view, name='logout'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)