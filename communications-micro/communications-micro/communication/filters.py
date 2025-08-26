import django_filters
from django.db.models import Q
from django.utils import timezone
from .models import Broadcast, Event


class BroadcastFilter(django_filters.FilterSet):
    """Filter class for broadcasts"""
    
    priority = django_filters.ChoiceFilter(choices=Broadcast.PRIORITY_CHOICES)
    audience_type = django_filters.ChoiceFilter(choices=Broadcast.AUDIENCE_CHOICES)
    is_published = django_filters.BooleanFilter()
    is_active = django_filters.BooleanFilter(method='filter_is_active')
    is_acknowledged = django_filters.BooleanFilter(method='filter_acknowledged')
    is_viewed = django_filters.BooleanFilter(method='filter_viewed')
    date_range = django_filters.DateFromToRangeFilter(field_name='start_date')
    created_by = django_filters.NumberFilter(field_name='created_by__id')
    
    class Meta:
        model = Broadcast
        fields = [
            'priority', 'audience_type', 'is_published', 'is_active',
            'is_acknowledged', 'is_viewed', 'date_range', 'created_by'
        ]

    def filter_is_active(self, queryset, name, value):
        """Filter for currently active/visible broadcasts"""
        now = timezone.now()
        if value:
            return queryset.filter(
                start_date__lte=now,
                end_date__gte=now,
                is_published=True,
                is_active=True
            )
        else:
            return queryset.exclude(
                start_date__lte=now,
                end_date__gte=now,
                is_published=True,
                is_active=True
            )

    def filter_acknowledged(self, queryset, name, value):
        """Filter broadcasts by acknowledgment status for current user"""
        user = self.request.user
        if not user.is_authenticated:
            return queryset.none()
        
        if value:
            return queryset.filter(acknowledged_by=user)
        else:
            return queryset.exclude(acknowledged_by=user)

    def filter_viewed(self, queryset, name, value):
        """Filter broadcasts by view status for current user"""
        user = self.request.user
        if not user.is_authenticated:
            return queryset.none()
        
        if value:
            return queryset.filter(viewed_by=user)
        else:
            return queryset.exclude(viewed_by=user)


class EventFilter(django_filters.FilterSet):
    """Filter class for events"""
    
    event_type = django_filters.ChoiceFilter(choices=Event.EVENT_TYPES)
    is_important = django_filters.BooleanFilter()
    is_upcoming = django_filters.BooleanFilter(method='filter_upcoming')
    date_range = django_filters.DateFromToRangeFilter(field_name='date')
    rsvp_status = django_filters.ChoiceFilter(
        choices=Event.RSVP_STATUS,
        method='filter_rsvp_status'
    )
    created_by = django_filters.NumberFilter(field_name='created_by__id')
    venue = django_filters.CharFilter(lookup_expr='icontains')
    
    class Meta:
        model = Event
        fields = [
            'event_type', 'is_important', 'is_upcoming', 'date_range',
            'rsvp_status', 'created_by', 'venue'
        ]

    def filter_upcoming(self, queryset, name, value):
        """Filter for upcoming events"""
        now = timezone.now()
        if value:
            return queryset.filter(date__gte=now.date())
        else:
            return queryset.filter(date__lt=now.date())

    def filter_rsvp_status(self, queryset, name, value):
        """Filter events by user's RSVP status"""
        user = self.request.user
        if not user.is_authenticated:
            return queryset.none()
        
        if value == 'yes':
            return queryset.filter(rsvp_yes=user)
        elif value == 'no':
            return queryset.filter(rsvp_no=user)
        elif value == 'maybe':
            return queryset.filter(rsvp_maybe=user)
        
        return queryset