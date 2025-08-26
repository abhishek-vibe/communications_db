from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.utils import timezone
import os

def upload_to_media(instance, filename):
    """Upload media files to organized folders"""
    return f'communications/media/{timezone.now().year}/{timezone.now().month}/{filename}'

def upload_to_attachments(instance, filename):
    """Upload attachment files to organized folders"""
    return f'communications/attachments/{timezone.now().year}/{timezone.now().month}/{filename}'


class Group(models.Model):
    """Group model for organizing users"""
    GROUP_TYPES = [
        ('public', 'Public'),
        ('private', 'Private'),
    ]
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    group_type = models.CharField(max_length=10, choices=GROUP_TYPES, default='public')
    department = models.CharField(max_length=255, blank=True, null=True)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='user_groups', blank=True)
    owners = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='owned_groups', blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_groups')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'communication_groups'


class Media(models.Model):
    """Media model for file uploads"""
    MEDIA_TYPES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('pdf', 'PDF'),
        ('document', 'Document'),
    ]
    
    file = models.FileField(
        upload_to=upload_to_media,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'mp4', 'avi', 'mov', 'pdf', 'doc', 'docx', 'txt'])]
    )
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20, choices=MEDIA_TYPES)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.file:
            self.file_name = os.path.basename(self.file.name)
            self.file_size = self.file.size
            
            # Determine file type based on extension
            ext = os.path.splitext(self.file_name)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.gif']:
                self.file_type = 'image'
            elif ext in ['.mp4', '.avi', '.mov']:
                self.file_type = 'video'
            elif ext == '.pdf':
                self.file_type = 'pdf'
            else:
                self.file_type = 'document'
        
        super().save(*args, **kwargs)

    def __str__(self):
        return self.file_name

    class Meta:
        db_table = 'communication_media'


class Broadcast(models.Model):
    """Broadcast model for company-wide announcements"""
    PRIORITY_CHOICES = [
        ('important', 'Important'),
        ('normal', 'Normal'),
    ]
    
    AUDIENCE_CHOICES = [
        ('all', 'All'),
        ('groups', 'Groups'),
        ('users', 'Users'),
    ]
    
    title = models.CharField(max_length=255)
    description = models.TextField()  # Rich text from frontend
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    audience_type = models.CharField(max_length=10, choices=AUDIENCE_CHOICES, default='all')
    
    # Relationships
    attachments = models.ManyToManyField(Media, blank=True, related_name='broadcast_attachments')
    target_groups = models.ManyToManyField(Group, blank=True, related_name='targeted_broadcasts')
    target_users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='targeted_broadcasts')
    acknowledged_by = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='acknowledged_broadcasts')
    viewed_by = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='viewed_broadcasts')
    
    # Settings
    send_email = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Meta
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_broadcasts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    @property
    def is_visible(self):
        """Check if broadcast is currently visible"""
        now = timezone.now()
        return self.start_date <= now <= self.end_date and self.is_published and self.is_active

    @property
    def total_recipients(self):
        """Calculate total number of recipients"""
        User = get_user_model()
        if self.audience_type == 'all':
            return User.objects.filter(is_active=True).count()
        elif self.audience_type == 'groups':
            return User.objects.filter(user_groups__in=self.target_groups.all()).distinct().count()
        else:
            return self.target_users.count()

    @property
    def acknowledgment_rate(self):
        """Calculate acknowledgment percentage"""
        total = self.total_recipients
        if total == 0:
            return 0
        return (self.acknowledged_by.count() / total) * 100

    class Meta:
        db_table = 'communication_broadcasts'
        ordering = ['-created_at']


class Event(models.Model):
    """Event model for internal/external events"""
    EVENT_TYPES = [
        ('internal', 'Internal'),
        ('external', 'External'),
    ]
    
    RSVP_STATUS = [
        ('yes', 'Yes'),
        ('no', 'No'),
        ('maybe', 'Maybe'),
    ]
    
    title = models.CharField(max_length=255)
    description = models.TextField()
    date = models.DateField()
    time = models.TimeField()
    venue = models.CharField(max_length=255)
    event_type = models.CharField(max_length=10, choices=EVENT_TYPES, default='internal')
    
    # Media and customization
    media = models.ManyToManyField(Media, blank=True, related_name='event_media')
    theme = models.JSONField(blank=True, null=True, help_text="Visual customization settings")
    
    # Settings
    is_important = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # RSVP tracking
    rsvp_yes = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='events_rsvp_yes')
    rsvp_no = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='events_rsvp_no')
    rsvp_maybe = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='events_rsvp_maybe')
    
    # Visibility
    visible_to_groups = models.ManyToManyField(Group, blank=True, related_name='visible_events')
    visible_to_users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='visible_events')
    is_public = models.BooleanField(default=False, help_text="If true, visible to all users")
    
    # Meta
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_events')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.date}"

    @property
    def total_rsvp_yes(self):
        return self.rsvp_yes.count()

    @property
    def total_rsvp_no(self):
        return self.rsvp_no.count()

    @property
    def total_rsvp_maybe(self):
        return self.rsvp_maybe.count()

    @property
    def total_rsvp(self):
        return self.total_rsvp_yes + self.total_rsvp_no + self.total_rsvp_maybe

    @property
    def is_upcoming(self):
        """Check if event is upcoming"""
        from datetime import datetime
        event_datetime = datetime.combine(self.date, self.time)
        return event_datetime > timezone.now()

    def get_user_rsvp_status(self, user):
        """Get RSVP status for a specific user"""
        if self.rsvp_yes.filter(id=user.id).exists():
            return 'yes'
        elif self.rsvp_no.filter(id=user.id).exists():
            return 'no'
        elif self.rsvp_maybe.filter(id=user.id).exists():
            return 'maybe'
        return None

    def user_can_view(self, user):
        """Check if user can view this event"""
        if self.is_public:
            return True
        if self.created_by == user:
            return True
        if self.visible_to_users.filter(id=user.id).exists():
            return True
        if self.visible_to_groups.filter(members=user).exists():
            return True
        return False

    class Meta:
        db_table = 'communication_events'
        ordering = ['date', 'time']


class BroadcastView(models.Model):
    """Track broadcast views"""
    broadcast = models.ForeignKey(Broadcast, on_delete=models.CASCADE, related_name='view_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    class Meta:
        db_table = 'communication_broadcast_views'
        unique_together = ['broadcast', 'user']


class EventRSVPLog(models.Model):
    """Track RSVP changes"""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='rsvp_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    old_status = models.CharField(max_length=10, choices=Event.RSVP_STATUS, blank=True, null=True)
    new_status = models.CharField(max_length=10, choices=Event.RSVP_STATUS)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'communication_event_rsvp_logs'