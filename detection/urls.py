from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views


urlpatterns = [
    path('', views.login_view, name='login'),
    path("add-user/", views.add_user, name="add_user"),
    path('create-role/', views.create_role, name='create_role'),
    path('users/manage/', views.manage_users, name='manage_users'),
    path('update-user-status/', views.update_user_status, name='update_user_status'),
    path('edit-user/', views.edit_user, name='edit_user'),
    path("delete-user/<int:user_id>/", views.delete_user, name="delete_user"),

    path('dashboard/', views.dashboard, name='dashboard'),
    path("dashboard/service-stations/", views.centralized_service_station_dashboard, name="centralized_system_monitoring"),
    path("api/station/<int:station_id>/units/", views.get_units_by_station, name="api_units_by_station"),
    path("api/unit/<int:unit_id>/trays/", views.get_trays_by_unit, name="api_trays_by_unit"),
    path("api/tray/<int:tray_id>/tools/", views.get_tools_by_tray, name="api_tools_by_tray"),
    path('jobcards/station/<int:station_id>/', views.jobcard_list_by_station, name='jobcard_list_by_station'),

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
    path('users/assigned/', views.user_assigned_list, name='user_assigned_list'),
    path('inventory/update/', views.inventory_update_api, name='inventory_update_api'),
    path('api/detections/', views.receive_detections, name='receive_detections'),

    path('aircraft/', views.aircraft_list, name='aircraft_list'),
    path('aircraft/edit/<int:pk>/', views.aircraft_edit, name='aircraft_edit'),
    path('aircraft/delete/<int:pk>/', views.aircraft_delete, name='aircraft_delete'),

    path('jobcards/', views.jobcard_list, name='jobcard_list'),
    path('jobcards/create/', views.jobcard_create, name='jobcard_create'),
    path("jobcard/<str:job_id>/notes/", views.jobcard_notes, name="jobcard_notes"),
    path('<str:job_id>/edit/', views.jobcard_edit, name='jobcard_edit'),
    path('<str:job_id>/delete/', views.jobcard_delete, name='jobcard_delete'),

    path('jobcards/<str:job_id>/', views.jobcard_detail, name='jobcard_detail'),
    path('jobcards/<str:job_id>/close/', views.jobcard_close, name='jobcard_close'),



    path('logout/', views.logout_view, name='logout'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)