from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict

from .models import AdminProfile, Miscellaneous
from .serializers import (
    AdminProfileSerializer,
    MiscellaneousSerializer,
    MiscellaneousUpdateSerializer,
    DashboardOverviewSerializer
)
from Communication.models import Workspace, Channel
from authentication.models import User


# ====================
# Admin Profile ViewSet
# ====================

class AdminProfileViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing admin profiles"""
    queryset = AdminProfile.objects.all()
    serializer_class = AdminProfileSerializer
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        description="Get all admin profiles",
        tags=['Admin - Profiles']
    )
    def list(self, request, *args, **kwargs):
        """List all admin profiles"""
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        description="Get a specific admin profile",
        tags=['Admin - Profiles']
    )
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a specific admin profile"""
        return super().retrieve(request, *args, **kwargs)


# ====================
# Miscellaneous ViewSet
# ====================

class MiscellaneousViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing miscellaneous configuration entries.
    
    Provides GET and PATCH operations for system settings and configurations.
    """
    queryset = Miscellaneous.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Use appropriate serializer based on action"""
        if self.action == 'partial_update':
            return MiscellaneousUpdateSerializer
        return MiscellaneousSerializer
    
    @extend_schema(
        description="Get all miscellaneous entries",
        parameters=[
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                description='Search by key',
                required=False
            ),
            OpenApiParameter(
                name='key',
                type=OpenApiTypes.STR,
                description='Filter by specific key',
                required=False
            )
        ],
        tags=['Admin - Miscellaneous']
    )
    def list(self, request):
        """List all miscellaneous entries with optional filters"""
        queryset = self.get_queryset()
        
        # Filter by specific key
        key = request.query_params.get('key', None)
        if key:
            queryset = queryset.filter(key=key)
        
        # Search by key (partial match)
        search = request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(key__icontains=search)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        description="Get a specific miscellaneous entry by ID",
        responses={200: MiscellaneousSerializer},
        tags=['Admin - Miscellaneous']
    )
    def retrieve(self, request, pk=None):
        """Get a specific miscellaneous entry"""
        misc = self.get_object()
        serializer = self.get_serializer(misc)
        return Response(serializer.data)
    
    @extend_schema(
        description="Update a miscellaneous entry (value only)",
        request=MiscellaneousUpdateSerializer,
        responses={200: MiscellaneousSerializer},
        tags=['Admin - Miscellaneous']
    )
    def partial_update(self, request, pk=None):
        """Partially update miscellaneous entry (value only)"""
        misc = self.get_object()
        serializer = self.get_serializer(misc, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Return full serializer response
        response_serializer = MiscellaneousSerializer(misc)
        return Response(response_serializer.data)
    
    @extend_schema(
        description="Get miscellaneous entry by key",
        parameters=[
            OpenApiParameter(
                name='key',
                type=OpenApiTypes.STR,
                description='The key to retrieve',
                required=True,
                location=OpenApiParameter.PATH
            )
        ],
        responses={200: MiscellaneousSerializer},
        tags=['Admin - Miscellaneous']
    )
    @action(detail=False, methods=['get'], url_path='by-key/(?P<key>[^/]+)')
    def get_by_key(self, request, key=None):
        """Get miscellaneous entry by key"""
        try:
            misc = Miscellaneous.objects.get(key=key)
            serializer = self.get_serializer(misc)
            return Response(serializer.data)
        except Miscellaneous.DoesNotExist:
            return Response(
                {'error': f'Miscellaneous entry with key "{key}" not found'},
                status=status.HTTP_404_NOT_FOUND
            )


# ====================
# Dashboard ViewSet
# ====================

class DashboardViewSet(viewsets.ViewSet):
    """ViewSet for admin dashboard"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    @extend_schema(
        description="Get complete dashboard overview with metrics, charts, and recent activity",
        tags=['Admin - Dashboard']
    )
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get complete dashboard overview"""
        # Get current and previous month dates
        now = timezone.now()
        current_month_start = now.replace(day=1)
        last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
        last_month_end = current_month_start - timedelta(days=1)
        
        # Current month metrics
        current_businesses = Workspace.objects.filter(created_at__gte=current_month_start).count()
        current_active_users = User.objects.filter(is_active=True).count()
        current_channels = Channel.objects.filter(created_at__gte=current_month_start).count()
        
        # Previous month metrics
        previous_businesses = Workspace.objects.filter(
            created_at__gte=last_month_start,
            created_at__lte=last_month_end
        ).count()
        previous_active_users = User.objects.filter(
            is_active=True,
            created_at__lte=last_month_end
        ).count()
        previous_channels = Channel.objects.filter(
            created_at__gte=last_month_start,
            created_at__lte=last_month_end
        ).count()
        
        # Calculate growth percentages
        businesses_growth = self._calculate_growth(current_businesses, previous_businesses)
        users_growth = self._calculate_growth(current_active_users, previous_active_users)
        channels_growth = self._calculate_growth(current_channels, previous_channels)
        
        # Get total counts (all time)
        total_businesses = Workspace.objects.count()
        total_active_users = User.objects.filter(is_active=True).count()
        total_channels = Channel.objects.count()
        
        # Get business growth by month (last 6 months)
        business_growth = self._get_business_growth()
        
        # Get user activity (last 7 days)
        user_activity = self._get_user_activity()
        
        # Get recent activity
        recent_activity = self._get_recent_activity()
        
        metrics = {
            'total_businesses': total_businesses,
            'active_users': total_active_users,
            'active_channels': total_channels,
            'businesses_growth': businesses_growth,
            'users_growth': users_growth,
            'channels_growth': channels_growth,
        }
        
        data = {
            'metrics': metrics,
            'business_growth': business_growth,
            'user_activity': user_activity,
            'recent_activity': recent_activity,
        }
        
        serializer = DashboardOverviewSerializer(data)
        return Response(serializer.data)
    
    def _calculate_growth(self, current, previous):
        """Calculate percentage growth"""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 1)
    
    def _get_business_growth(self):
        """Get business registration data for last 6 months"""
        months_data = []
        now = timezone.now()
        
        for i in range(5, -1, -1):
            # Calculate the start and end of the month
            current_date = now.replace(day=1) - timedelta(days=i*30)
            month_start = current_date.replace(day=1)
            
            if i == 0:
                month_end = now
            else:
                month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            count = Workspace.objects.filter(
                created_at__gte=month_start,
                created_at__lte=month_end
            ).count()
            
            months_data.append({
                'month': month_start.strftime('%b'),
                'count': count
            })
        
        return months_data
    
    def _get_user_activity(self):
        """Get active users per day for last 7 days"""
        activity_data = []
        days_mapping = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        
        for i in range(6, -1, -1):
            date = timezone.now().date() - timedelta(days=i)
            day_name = days_mapping[date.weekday()]
            
            # Count users with activity (created_at) on this date
            count = User.objects.filter(
                created_at__date=date,
                is_active=True
            ).count()
            
            activity_data.append({
                'day': day_name,
                'date': date,
                'count': count
            })
        
        return activity_data
    
    def _get_recent_activity(self):
        """Get recent activity across platform"""
        recent_items = []
        
        # Recent workspaces (businesses)
        recent_workspaces = Workspace.objects.all().order_by('-created_at')[:3]
        for workspace in recent_workspaces:
            time_diff = self._get_time_difference(workspace.created_at)
            recent_items.append({
                'id': workspace.id,
                'business_name': workspace.name,
                'timestamp': workspace.created_at,
                'action': 'New business registered',
                'description': f'{workspace.name} was registered {time_diff}',
            })
        
        # Recent user additions to workspaces
        recent_users = User.objects.filter(is_active=True).order_by('-created_at')[:2]
        for user in recent_users:
            time_diff = self._get_time_difference(user.created_at)
            workspace = Workspace.objects.filter(users=user).first()
            if workspace:
                recent_items.append({
                    'id': user.id,
                    'business_name': workspace.name,
                    'timestamp': user.created_at,
                    'action': 'User joined',
                    'description': f'{user.name or user.email} joined the platform {time_diff}',
                })
        
        # Sort by timestamp, most recent first
        recent_items.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return recent_items[:5]
    
    def _get_time_difference(self, dt):
        """Get human-readable time difference"""
        diff = timezone.now() - dt
        
        if diff.total_seconds() < 60:
            return 'just now'
        elif diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() / 60)
            return f'{minutes} minute{"s" if minutes > 1 else ""} ago'
        elif diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() / 3600)
            return f'{hours} hour{"s" if hours > 1 else ""} ago'
        elif diff.total_seconds() < 604800:
            days = int(diff.total_seconds() / 86400)
            return f'{days} day{"s" if days > 1 else ""} ago'
        else:
            return dt.strftime('%d %b')

