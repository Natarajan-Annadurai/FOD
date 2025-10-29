from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('inventory/', views.inventory_view, name='inventory'),
    path('tool_creation/', views.tool_creation_view, name='tool_creation'),
    path('tool_purchase/', views.tool_purchase_view, name='tool_purchase'),
    path('logout/', views.logout_view, name='logout'),
]