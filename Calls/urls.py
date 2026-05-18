from django.urls import path

from . import views

urlpatterns = [
    path('logs/', views.CallLogsView.as_view(), name='call-logs'),
    path('', views.CallCreateView.as_view(), name='call-create'),
    path('<uuid:call_id>/', views.CallDetailView.as_view(), name='call-detail'),
    path('<uuid:call_id>/token/', views.CallTokenView.as_view(), name='call-token'),
    path('<uuid:call_id>/leave/', views.CallLeaveView.as_view(), name='call-leave'),
    path('<uuid:call_id>/end/', views.CallEndView.as_view(), name='call-end'),
    path('<uuid:call_id>/summary/', views.CallSummaryView.as_view(), name='call-summary'),
]
