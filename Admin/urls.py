from django.urls import path
from . import views

# Miscellaneous endpoints
misc_list = views.MiscellaneousViewSet.as_view({
    'get': 'list'
})
misc_retrieve = views.MiscellaneousViewSet.as_view({
    'get': 'retrieve'
})
misc_partial_update = views.MiscellaneousViewSet.as_view({
    'patch': 'partial_update'
})
misc_get_by_key = views.MiscellaneousViewSet.as_view({
    'get': 'get_by_key'
})

# Admin Profile endpoints
admin_profile_list = views.AdminProfileViewSet.as_view({
    'get': 'list'
})
admin_profile_retrieve = views.AdminProfileViewSet.as_view({
    'get': 'retrieve'
})

# Dashboard endpoints
dashboard_overview = views.DashboardViewSet.as_view({
    'get': 'overview'
})

urlpatterns = [
    # Miscellaneous
    path('misc/', misc_list, name='miscellaneous-list'),
    path('misc/<int:pk>/', misc_retrieve, name='miscellaneous-retrieve'),
    path('misc/<int:pk>/update/', misc_partial_update, name='miscellaneous-update'),
    path('misc/by-key/<str:key>/', misc_get_by_key, name='miscellaneous-by-key'),
    
    # Admin Profile
    path('profiles/', admin_profile_list, name='admin-profile-list'),
    path('profiles/<int:pk>/', admin_profile_retrieve, name='admin-profile-retrieve'),
    
    # Dashboard
    path('dashboard/overview/', dashboard_overview, name='dashboard-overview'),
]
