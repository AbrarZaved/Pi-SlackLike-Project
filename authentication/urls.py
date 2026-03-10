from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from . import views

urlpatterns = [
    # User Management
    path('users/', views.UserViewSet.as_view({'get': 'list', 'post': 'create'}), name='user-list'),
    path('users/<int:pk>/', views.UserViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='user-detail'),
    
    # Role Management
    path('roles/', views.RoleViewSet.as_view({'get': 'list'}), name='role-list'),
    path('roles/<int:pk>/', views.RoleViewSet.as_view({'get': 'retrieve'}), name='role-detail'),
    
    # OTP-based Passwordless Authentication
    path('auth/send-otp/', views.SendOTPView.as_view(), name='send-otp'),
    path('auth/verify-otp/', views.VerifyOTPView.as_view(), name='verify-otp'),  # Returns JWT tokens
    
    # JWT Token Management
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token-verify'),
    
    # API Views
    path('permissions/me/', views.MyPermissionsView.as_view(), name='my-permissions'),
    path('health/', views.HealthCheckView.as_view(), name='health-check'),
]
