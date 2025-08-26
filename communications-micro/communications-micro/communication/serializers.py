from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Broadcast, Event, Media, Group, BroadcastView, EventRSVPLog


class UserSerializer(serializers.ModelSerializer):
    """Basic user serializer"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class MediaSerializer(serializers.ModelSerializer):
    """Media file serializer"""
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Media
        fields = ['id', 'file', 'file_url', 'file_name', 'file_type', 'file_size', 'uploaded_at']
        read_only_fields = ['file_name', 'file_type', 'file_size', 'uploaded_at']

    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None


class GroupSerializer(serializers.ModelSerializer):
    """Group serializer"""
    members_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Group
        fields = ['id', 'name', 'description', 'group_type', 'department', 'members_count', 'created_at']
        read_only_fields = ['created_at']

    def get_members_count(self, obj):
        return obj.members.count()


class BroadcastListSerializer(serializers.ModelSerializer):
    """Broadcast list serializer (minimal fields)"""
    created_by_name = serializers.SerializerMethodField()
    attachments_count = serializers.SerializerMethodField()
    is_acknowledged = serializers.SerializerMethodField()
    is_viewed = serializers.SerializerMethodField()
    acknowledgment_rate = serializers.ReadOnlyField()
    total_recipients = serializers.ReadOnlyField()
    
    class Meta:
        model = Broadcast
        fields = [
            'id', 'title', 'priority', 'start_date', 'end_date', 'audience_type',
            'is_published', 'send_email', 'created_by_name', 'attachments_count',
            'is_acknowledged', 'is_viewed', 'acknowledgment_rate', 'total_recipients',
            'created_at', 'updated_at'
        ]

    def get_created_by_name(self, obj):
        return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip() or obj.created_by.username

    def get_attachments_count(self, obj):
        return obj.attachments.count()

    def get_is_acknowledged(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.acknowledged_by.filter(id=request.user.id).exists()
        return False

    def get_is_viewed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.viewed_by.filter(id=request.user.id).exists()
        return False


class BroadcastDetailSerializer(serializers.ModelSerializer):
    """Broadcast detail serializer"""
    created_by = UserSerializer(read_only=True)
    attachments = MediaSerializer(many=True, read_only=True)
    attachment_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    target_groups = GroupSerializer(many=True, read_only=True)
    target_group_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    target_users = UserSerializer(many=True, read_only=True)
    target_user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    acknowledgment_rate = serializers.ReadOnlyField()
    total_recipients = serializers.ReadOnlyField()
    is_acknowledged = serializers.SerializerMethodField()
    is_viewed = serializers.SerializerMethodField()
    
    class Meta:
        model = Broadcast
        fields = [
            'id', 'title', 'description', 'priority', 'start_date', 'end_date',
            'audience_type', 'attachments', 'attachment_ids', 'target_groups',
            'target_group_ids', 'target_users', 'target_user_ids', 'send_email',
            'is_published', 'created_by', 'acknowledgment_rate', 'total_recipients',
            'is_acknowledged', 'is_viewed', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def get_is_acknowledged(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.acknowledged_by.filter(id=request.user.id).exists()
        return False

    def get_is_viewed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.viewed_by.filter(id=request.user.id).exists()
        return False

    def validate(self, data):
        """Validate broadcast data"""
        if data['start_date'] >= data['end_date']:
            raise serializers.ValidationError("End date must be after start date")
        
        audience_type = data.get('audience_type')
        if audience_type == 'groups' and not data.get('target_group_ids'):
            raise serializers.ValidationError("Target groups are required when audience type is 'groups'")
        
        if audience_type == 'users' and not data.get('target_user_ids'):
            raise serializers.ValidationError("Target users are required when audience type is 'users'")
        
        return data

    def create(self, validated_data):
        attachment_ids = validated_data.pop('attachment_ids', [])
        target_group_ids = validated_data.pop('target_group_ids', [])
        target_user_ids = validated_data.pop('target_user_ids', [])
        
        validated_data['created_by'] = self.context['request'].user
        broadcast = Broadcast.objects.create(**validated_data)
        
        if attachment_ids:
            broadcast.attachments.set(attachment_ids)
        if target_group_ids:
            broadcast.target_groups.set(target_group_ids)
        if target_user_ids:
            broadcast.target_users.set(target_user_ids)
        
        return broadcast

    def update(self, instance, validated_data):
        attachment_ids = validated_data.pop('attachment_ids', None)
        target_group_ids = validated_data.pop('target_group_ids', None)
        target_user_ids = validated_data.pop('target_user_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if attachment_ids is not None:
            instance.attachments.set(attachment_ids)
        if target_group_ids is not None:
            instance.target_groups.set(target_group_ids)
        if target_user_ids is not None:
            instance.target_users.set(target_user_ids)
        
        return instance


class EventListSerializer(serializers.ModelSerializer):
    """Event list serializer (minimal fields)"""
    created_by_name = serializers.SerializerMethodField()
    user_rsvp_status = serializers.SerializerMethodField()
    total_rsvp = serializers.ReadOnlyField()
    is_upcoming = serializers.ReadOnlyField()
    
    class Meta:
        model = Event
        fields = [
            'id', 'title', 'date', 'time', 'venue', 'event_type', 'is_important',
            'created_by_name', 'user_rsvp_status', 'total_rsvp', 'is_upcoming',
            'created_at'
        ]

    def get_created_by_name(self, obj):
        return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip() or obj.created_by.username

    def get_user_rsvp_status(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.get_user_rsvp_status(request.user)
        return None


class EventDetailSerializer(serializers.ModelSerializer):
    """Event detail serializer"""
    created_by = UserSerializer(read_only=True)
    media = MediaSerializer(many=True, read_only=True)
    media_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    visible_to_groups = GroupSerializer(many=True, read_only=True)
    visible_to_group_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    visible_to_users = UserSerializer(many=True, read_only=True)
    visible_to_user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    user_rsvp_status = serializers.SerializerMethodField()
    total_rsvp_yes = serializers.ReadOnlyField()
    total_rsvp_no = serializers.ReadOnlyField()
    total_rsvp_maybe = serializers.ReadOnlyField()
    total_rsvp = serializers.ReadOnlyField()
    is_upcoming = serializers.ReadOnlyField()
    
    class Meta:
        model = Event
        fields = [
            'id', 'title', 'description', 'date', 'time', 'venue', 'event_type',
            'media', 'media_ids', 'theme', 'is_important', 'is_public',
            'visible_to_groups', 'visible_to_group_ids', 'visible_to_users',
            'visible_to_user_ids', 'created_by', 'user_rsvp_status',
            'total_rsvp_yes', 'total_rsvp_no', 'total_rsvp_maybe', 'total_rsvp',
            'is_upcoming', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def get_user_rsvp_status(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.get_user_rsvp_status(request.user)
        return None

    def validate(self, data):
        """Validate event data"""
        from datetime import datetime
        event_datetime = datetime.combine(data['date'], data['time'])
        if event_datetime <= timezone.now():
            raise serializers.ValidationError("Event date and time must be in the future")
        
        return data

    def create(self, validated_data):
        media_ids = validated_data.pop('media_ids', [])
        visible_to_group_ids = validated_data.pop('visible_to_group_ids', [])
        visible_to_user_ids = validated_data.pop('visible_to_user_ids', [])
        
        validated_data['created_by'] = self.context['request'].user
        event = Event.objects.create(**validated_data)
        
        if media_ids:
            event.media.set(media_ids)
        if visible_to_group_ids:
            event.visible_to_groups.set(visible_to_group_ids)
        if visible_to_user_ids:
            event.visible_to_users.set(visible_to_user_ids)
        
        return event

    def update(self, instance, validated_data):
        media_ids = validated_data.pop('media_ids', None)
        visible_to_group_ids = validated_data.pop('visible_to_group_ids', None)
        visible_to_user_ids = validated_data.pop('visible_to_user_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if media_ids is not None:
            instance.media.set(media_ids)
        if visible_to_group_ids is not None:
            instance.visible_to_groups.set(visible_to_group_ids)
        if visible_to_user_ids is not None:
            instance.visible_to_users.set(visible_to_user_ids)
        
        return instance


class RSVPSerializer(serializers.Serializer):
    """RSVP action serializer"""
    status = serializers.ChoiceField(choices=['yes', 'no', 'maybe'])


class BroadcastAcknowledgeSerializer(serializers.Serializer):
    """Broadcast acknowledge serializer"""
    acknowledged = serializers.BooleanField()


class MediaUploadSerializer(serializers.ModelSerializer):
    """Media upload serializer"""
    class Meta:
        model = Media
        fields = ['file']

    def create(self, validated_data):
        validated_data['uploaded_by'] = self.context['request'].user
        return super().create(validated_data)


class BroadcastAnalyticsSerializer(serializers.Serializer):
    """Broadcast analytics serializer"""
    total_recipients = serializers.IntegerField()
    total_views = serializers.IntegerField()
    total_acknowledgments = serializers.IntegerField()
    acknowledgment_rate = serializers.FloatField()
    view_rate = serializers.FloatField()
    daily_views = serializers.ListField()
    daily_acknowledgments = serializers.ListField()


class EventAnalyticsSerializer(serializers.Serializer):
    """Event analytics serializer"""
    total_rsvp_yes = serializers.IntegerField()
    total_rsvp_no = serializers.IntegerField()
    total_rsvp_maybe = serializers.IntegerField()
    total_rsvp = serializers.IntegerField()
    rsvp_rate = serializers.FloatField()
    daily_rsvp = serializers.ListField()