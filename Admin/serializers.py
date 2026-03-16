"""
Serializers for Admin APIs
"""

from rest_framework import serializers
from .models import AdminProfile, Miscellaneous, Automation
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


# ====================
# Activation Serializers
# ====================


class ActivationStatusSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class AutomationSerializer(serializers.ModelSerializer):
    workspace_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    workspace = serializers.SerializerMethodField(read_only=True)
    created_by = serializers.SerializerMethodField(read_only=True)
    executions_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Automation
        fields = [
            'id',
            'name',
            'workspace',
            'workspace_id',
            'trigger_type',
            'action_type',
            'message_content',
            'email_subject',
            'is_enabled',
            'created_by',
            'executions_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'workspace', 'created_by', 'executions_count', 'created_at', 'updated_at']

    def get_workspace(self, obj):
        if not obj.workspace_id:
            return None
        return {'id': obj.workspace_id, 'name': obj.workspace.name}

    def get_created_by(self, obj):
        if not obj.created_by_id:
            return None
        return {'id': obj.created_by_id, 'email': obj.created_by.email, 'name': getattr(obj.created_by, 'name', None)}

    def validate(self, attrs):
        trigger_type = attrs.get('trigger_type', getattr(self.instance, 'trigger_type', None))
        action_type = attrs.get('action_type', getattr(self.instance, 'action_type', None))
        message_content = attrs.get('message_content', getattr(self.instance, 'message_content', None))

        if action_type == Automation.ACTION_SEND_MESSAGE and not message_content:
            raise serializers.ValidationError({'message_content': 'message_content is required for send_message automations'})

        if action_type == Automation.ACTION_SEND_EMAIL and not message_content:
            raise serializers.ValidationError({'message_content': 'message_content is required for send_email automations'})

        if trigger_type not in (Automation.TRIGGER_USER_JOINS, Automation.TRIGGER_NEW_MESSAGE):
            raise serializers.ValidationError({'trigger_type': 'Invalid trigger_type'})

        if action_type not in (Automation.ACTION_SEND_MESSAGE, Automation.ACTION_SEND_EMAIL):
            raise serializers.ValidationError({'action_type': 'Invalid action_type'})

        return attrs

    def create(self, validated_data):
        workspace_id = validated_data.pop('workspace_id', None)
        if workspace_id is not None:
            from Communication.models import Workspace
            validated_data['workspace'] = Workspace.objects.get(id=workspace_id)

        request = self.context.get('request')
        if request and getattr(request, 'user', None) and request.user.is_authenticated:
            validated_data['created_by'] = request.user

        return super().create(validated_data)

    def update(self, instance, validated_data):
        _missing = object()
        workspace_id = validated_data.pop('workspace_id', _missing)
        if workspace_id is not _missing:
            if workspace_id is None:
                instance.workspace = None
            else:
                from Communication.models import Workspace
                instance.workspace = Workspace.objects.get(id=workspace_id)
        return super().update(instance, validated_data)
