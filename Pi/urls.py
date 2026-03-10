from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

# ====================
# OpenAPI 3.0 Schema Configuration (drf-spectacular)
# ====================

# ====================
# URL Patterns
# ====================

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API Documentation (OpenAPI 3.0)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # API Routes
    path('api/v1/auth/', include('authentication.urls')),
    path('api/v1/admin/', include('Admin.urls')),
    
    # DRF Browsable API Authentication
    path('api-auth/', include('rest_framework.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
