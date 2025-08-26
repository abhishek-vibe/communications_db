from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Broadcast, Event, Media, Group, BroadcastView, EventRSVPLog


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'group_type', 'department', 'members_count', 'created_by', 'created_at']
    list_filter = ['group_type', 'department', 'created_at']
    search_fields = ['name', 'description', 'department']
    readonly_fields = ['created_at', 'updated_at', 'members_count']
    filter_horizontal = ['members', 'owners']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'group_type', 'department')
        }),
        ('Members', {
            'fields': ('members', 'owners')
        }),
        ('Meta', {
            'fields': ('created_by', 'is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def members_count(self, obj):
        return obj.members.count()
    members_count.short_description = 'Members'

    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'file_type', 'file_size_display', 'uploaded_by', 'uploaded_at']
    list_filter = ['file_type', 'uploaded_at']
    search_fields = ['file_name']
    readonly_fields = ['file_name', 'file_type', 'file_size', 'uploaded_at', 'file_preview']

    def file_size_display(self, obj):
        """Display file size in human readable format"""
        size = obj.file_size
        for unit in ['bytes', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    file_size_display.short_description = 'File Size'

    def file_preview(self, obj):
        """Display file preview if it's an image"""
        if obj.file_type == 'image' and obj.file:
            return format_html(
                '<img src="{}" width="200" height="auto" style="border-radius: 5px;"/>',
                obj.file.url
            )
        return "No preview available"
    file_preview.short_description = 'Preview'


class BroadcastViewInline(admin.TabularInline):
    model = BroadcastView
    extra = 0
    readonly_fields = ['user', 'viewed_at', 'ip_address']


@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'priority', 'audience_type', 'start_date', 'end_date',
        'is_published', 'acknowledgment_rate_display', 'created_by', 'created_at'
    ]
    list_filter = [
        'priority', 'audience_type', 'is_published', 'send_email', 'created_at', 'start_date'
    ]
    search_fields = ['title', 'description']
    readonly_fields = [
        'created_at', 'updated_at', 'acknowledgment_rate', 'total_recipients',
        'acknowledgment_count', 'view_count'
    ]
    filter_horizontal = ['attachments', 'target_groups', 'target_users', 'acknowledged_by', 'viewed_by']
    date_hierarchy = 'created_at'
    inlines = [BroadcastViewInline]
    
    fieldsets = (
        ('Content', {
            'fields': ('title', 'description', 'priority', 'attachments')
        }),
        ('Scheduling', {
            'fields': ('start_date', 'end_date', 'is_published')
        }),
        ('Targeting', {
            'fields': ('audience_type', 'target_groups', 'target_users', 'send_email')
        }),
        ('Tracking', {
            'fields': ('acknowledged_by', 'viewed_by'),
            'classes': ('collapse',)
        }),
        ('Analytics', {
            'fields': ('acknowledgment_rate', 'total_recipients', 'acknowledgment_count', 'view_count'),
            'classes': ('collapse',)
        }),
        ('Meta', {
            'fields': ('created_by', 'is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def acknowledgment_rate_display(self, obj):
        rate = obj.acknowledgment_rate
        color = 'green' if rate >= 80 else 'orange' if rate >= 50 else 'red'
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color, rate
        )
    acknowledgment_rate_display.short_description = 'Ack Rate'

    def acknowledgment_count(self, obj):
        return obj.acknowledged_by.count()
    acknowledgment_count.short_description = 'Acknowledgments'

    def view_count(self, obj):
        return obj.viewed_by.count()
    view_count.short_description = 'Views'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class EventRSVPLogInline(admin.TabularInline):
    model = EventRSVPLog
    extra = 0
    readonly_fields = ['user', 'old_status', 'new_status', 'changed_at']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'date', 'time', 'venue', 'event_type', 'is_important',
        'rsvp_summary', 'created_by', 'created_at'
    ]
    list_filter = [
        'event_type', 'is_important', 'date', 'created_at', 'is_public'
    ]
    search_fields = ['title', 'description', 'venue']
    readonly_fields = [
        'created_at', 'updated_at', 'total_rsvp_yes', 'total_rsvp_no',
        'total_rsvp_maybe', 'total_rsvp', 'is_upcoming'
    ]
    filter_horizontal = [
        'media', 'visible_to_groups', 'visible_to_users',
        'rsvp_yes', 'rsvp_no', 'rsvp_maybe'
    ]
    date_hierarchy = 'date'
    inlines = [EventRSVPLogInline]
    
    fieldsets = (
        ('Event Details', {
            'fields': ('title', 'description', 'date', 'time', 'venue', 'event_type')
        }),
        ('Media & Customization', {
            'fields': ('media', 'theme', 'is_important')
        }),
        ('Visibility', {
            'fields': ('is_public', 'visible_to_groups', 'visible_to_users')
        }),
        ('RSVP Tracking', {
            'fields': ('rsvp_yes', 'rsvp_no', 'rsvp_maybe'),
            'classes': ('collapse',)
        }),
        ('Analytics', {
            'fields': ('total_rsvp_yes', 'total_rsvp_no', 'total_rsvp_maybe', 'total_rsvp', 'is_upcoming'),
            'classes': ('collapse',)
        }),
        ('Meta', {
            'fields': ('created_by', 'is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def rsvp_summary(self, obj):
        yes = obj.total_rsvp_yes
        no = obj.total_rsvp_no
        maybe = obj.total_rsvp_maybe
        return format_html(
            '<span style="color: green;">{}Y</span> / '
            '<span style="color: red;">{}N</span> / '
            '<span style="color: orange;">{}M</span>',
            yes, no, maybe
        )
    rsvp_summary.short_description = 'RSVP (Y/N/M)'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(BroadcastView)
class BroadcastViewAdmin(admin.ModelAdmin):
    list_display = ['broadcast', 'user', 'viewed_at', 'ip_address']
    list_filter = ['viewed_at']
    search_fields = ['broadcast__title', 'user__username', 'user__email']
    readonly_fields = ['broadcast', 'user', 'viewed_at', 'ip_address']

    def has_add_permission(self, request):
        return False  # Prevent manual creation

    def has_change_permission(self, request, obj=None):
        return False  # Prevent editing


@admin.register(EventRSVPLog)
class EventRSVPLogAdmin(admin.ModelAdmin):
    list_display = ['event', 'user', 'old_status', 'new_status', 'changed_at']
    list_filter = ['old_status', 'new_status', 'changed_at']
    search_fields = ['event__title', 'user__username', 'user__email']
    readonly_fields = ['event', 'user', 'old_status', 'new_status', 'changed_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.site_header = "Vibe Connect - Communications Module"
admin.site.site_title = "Communications Admin"
admin.site.index_title = "Communications Management"