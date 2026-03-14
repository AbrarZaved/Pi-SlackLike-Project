"""
Serializers for Admin APIs
"""

from rest_framework import serializers
from .models import AdminProfile, Miscellaneous
from authentication.models import User
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta


# ====================
# Admin Profile Serializers
# ====================

class AdminProfileSerializer(serializers.ModelSerializer):
    """Serializer for AdminProfile model"""
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = AdminProfile
        fields = ['id', 'user', 'user_email', 'bio', 'department', 'location', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


# ====================
# Miscellaneous Serializers
# ====================

class MiscellaneousSerializer(serializers.ModelSerializer):
    """Serializer for Miscellaneous model"""
    
    class Meta:
        model = Miscellaneous
        fields = ['id', 'key', 'value', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_key(self, value):
        """Ensure key is unique (except for current instance during update)"""
        request = self.context.get('request')
        if request and request.method == 'PATCH':
            instance = self.instance
            if instance and Miscellaneous.objects.filter(key=value).exclude(pk=instance.pk).exists():
                raise serializers.ValidationError("A miscellaneous entry with this key already exists.")
        elif request and request.method in ['POST', 'PUT']:
            if Miscellaneous.objects.filter(key=value).exists():
                raise serializers.ValidationError("A miscellaneous entry with this key already exists.")
        return value


class MiscellaneousUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Miscellaneous model (patch only)"""
    
    class Meta:
        model = Miscellaneous
        fields = ['value']


# ====================
# Dashboard Serializers
# ====================

class DashboardMetricSerializer(serializers.Serializer):
    """Serializer for dashboard metrics"""
    total_businesses = serializers.IntegerField()
    active_users = serializers.IntegerField()
    active_channels = serializers.IntegerField()
    businesses_growth = serializers.FloatField()
    users_growth = serializers.FloatField()
    channels_growth = serializers.FloatField()


class BusinessGrowthPointSerializer(serializers.Serializer):
    """Serializer for a single data point in business growth chart"""
    month = serializers.CharField()
    count = serializers.IntegerField()


class UserActivityPointSerializer(serializers.Serializer):
    """Serializer for a single data point in user activity chart"""
    day = serializers.CharField()
    date = serializers.DateField()
    count = serializers.IntegerField()


class RecentActivitySerializer(serializers.Serializer):
    """Serializer for recent activity items"""
    id = serializers.IntegerField()
    business_name = serializers.CharField()
    timestamp = serializers.DateTimeField()
    action = serializers.CharField()
    description = serializers.CharField()


class DashboardOverviewSerializer(serializers.Serializer):
    """Serializer for complete dashboard overview"""
    metrics = DashboardMetricSerializer()
    business_growth = BusinessGrowthPointSerializer(many=True)
    user_activity = UserActivityPointSerializer(many=True)
    recent_activity = RecentActivitySerializer(many=True)
