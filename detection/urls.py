from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/tool-activity/', views.tool_activity_dashboard, name='tool_activity_dashboard'),
    path('inventory/', views.inventory_view, name='inventory'),
    path('tool_creation/', views.tool_creation_view, name='tool_creation'),
    path('tool_purchase/', views.tool_purchase_view, name='tool_purchase'),
    path('service-stations/create/', views.create_service_station, name='create_service_station'),
    path('service-stations/', views.service_station_list, name='service_station_list'),
    path('service-stations/<int:station_id>/units/create/', views.create_unit, name='create_unit'),
    path('units/<int:unit_id>/trays/create/', views.create_tray, name='create_tray'),
    path('trays/<int:tray_id>/assign-tools/', views.assign_tools, name='assign_tools'),
    path('trays/<int:tray_id>/assigned-tools/', views.assigned_tools_list, name='assigned_tools_list'),
    path('assigned-tools/', views.global_assigned_tools, name='global_assigned_tools'),
    path('users/manage/', views.manage_users, name='manage_users'),
    path('users/assigned/', views.user_assigned_list, name='user_assigned_list'),
    path('inventory/update/', views.inventory_update_api, name='inventory_update_api'),
    path('api/detections/', views.receive_detections, name='receive_detections'),
    path('tools-tracking/', views.tools_tracking_list, name='tools_tracking_list'),
    path('logout/', views.logout_view, name='logout'),
]