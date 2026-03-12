from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router and register viewsets
router = DefaultRouter()
router.register(r'channels', views.ChannelViewSet, basename='channel')
router.register(r'workspaces', views.WorkspaceViewSet, basename='workspace')

urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
]
