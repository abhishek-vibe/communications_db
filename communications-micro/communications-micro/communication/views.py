from rest_framework import viewsets, status, filters
from rest_framework.decorators import action,api_view
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, F
from django.utils import timezone
from datetime import datetime, timedelta
from django.conf import settings

from .models import Broadcast, Event, Media, Group, BroadcastView, EventRSVPLog
from .serializers import (
    BroadcastListSerializer, BroadcastDetailSerializer, BroadcastAcknowledgeSerializer,
    EventListSerializer, EventDetailSerializer, RSVPSerializer,
    MediaSerializer, MediaUploadSerializer, GroupSerializer,
    BroadcastAnalyticsSerializer, EventAnalyticsSerializer
)
from .permissions import (
    IsBroadcastOwnerOrAdmin, IsEventOwnerOrAdmin, IsGroupOwnerOrAdmin,
    CanRSVPToEvent, CanAcknowledgeBroadcast, IsMediaOwnerOrAdmin, IsAdminOrReadOnly
)
from .filters import BroadcastFilter, EventFilter


@api_view(['POST'])
def auto_onboard(request):
    auth_token = request.headers.get("Authorization")
    
    if auth_token != f"Token {settings.INTERNAL_REGISTER_DB_TOKEN}":
        return Response({"detail": "Invalid token"}, status=403)

    data = request.data
    tenant_username = data.get('tenant_username')
    tenant_admin_password = data.get('tenant_admin_password')

    if not tenant_username or not tenant_admin_password:
        return Response({"detail": "Missing tenant credentials"}, status=400)

    # Add onboarding logic here...
    return Response({"detail": f"Tenant {tenant_username} onboarded successfully"}, status=201)


class BroadcastViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing broadcasts
    """
    queryset = Broadcast.objects.filter(is_active=True)
    permission_classes = [IsBroadcastOwnerOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = BroadcastFilter
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'start_date', 'priority']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return BroadcastListSerializer
        return BroadcastDetailSerializer

    def get_queryset(self):
        """Filter broadcasts based on user permissions"""
        user = self.request.user
        if user.is_staff:
            return self.queryset
        
        # Filter based on audience targeting
        return self.queryset.filter(
            Q(audience_type='all') |
            Q(audience_type='groups', target_groups__members=user) |
            Q(audience_type='users', target_users=user) |
            Q(created_by=user)
        ).distinct()

    @action(detail=True, methods=['post'], permission_classes=[CanAcknowledgeBroadcast])
    def acknowledge(self, request, pk=None):
        """Acknowledge a broadcast"""
        broadcast = self.get_object()
        serializer = BroadcastAcknowledgeSerializer(data=request.data)
        
        if serializer.is_valid():
            acknowledged = serializer.validated_data['acknowledged']
            
            if acknowledged:
                broadcast.acknowledged_by.add(request.user)
            else:
                broadcast.acknowledged_by.remove(request.user)
            
            return Response({
                'message': f'Broadcast {"acknowledged" if acknowledged else "unacknowledged"} successfully',
                'acknowledged': acknowledged
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def mark_viewed(self, request, pk=None):
        """Mark broadcast as viewed"""
        broadcast = self.get_object()
        
        # Add user to viewed_by if not already viewed
        if not broadcast.viewed_by.filter(id=request.user.id).exists():
            broadcast.viewed_by.add(request.user)
            
            # Create view log
            BroadcastView.objects.get_or_create(
                broadcast=broadcast,
                user=request.user,
                defaults={'ip_address': self.get_client_ip(request)}
            )
        
        return Response({'message': 'Broadcast marked as viewed'})

    @action(detail=True, methods=['get'], permission_classes=[IsAdminOrReadOnly])
    def analytics(self, request, pk=None):
        """Get broadcast analytics"""
        broadcast = self.get_object()
        
        # Calculate daily views and acknowledgments for last 30 days
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        daily_views = []
        daily_acknowledgments = []
        
        current_date = start_date
        while current_date <= end_date:
            views_count = BroadcastView.objects.filter(
                broadcast=broadcast,
                viewed_at__date=current_date
            ).count()
            
            # For acknowledgments, we need to check if they were done on this date
            # Since we don't track acknowledgment date, we'll use a simpler approach
            daily_views.append({
                'date': current_date.isoformat(),
                'count': views_count
            })
            
            current_date += timedelta(days=1)

        analytics_data = {
            'total_recipients': broadcast.total_recipients,
            'total_views': broadcast.viewed_by.count(),
            'total_acknowledgments': broadcast.acknowledged_by.count(),
            'acknowledgment_rate': broadcast.acknowledgment_rate,
            'view_rate': (broadcast.viewed_by.count() / broadcast.total_recipients * 100) if broadcast.total_recipients > 0 else 0,
            'daily_views': daily_views,
            'daily_acknowledgments': []  # Simplified for now
        }
        
        serializer = BroadcastAnalyticsSerializer(analytics_data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def my_broadcasts(self, request):
        """Get current user's created broadcasts"""
        queryset = self.get_queryset().filter(created_by=request.user)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class EventViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing events
    """
    queryset = Event.objects.filter(is_active=True)
    permission_classes = [IsEventOwnerOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = EventFilter
    search_fields = ['title', 'description', 'venue']
    ordering_fields = ['created_at', 'date', 'time']
    ordering = ['date', 'time']

    def get_serializer_class(self):
        if self.action == 'list':
            return EventListSerializer
        return EventDetailSerializer

    def get_queryset(self):
        """Filter events based on user permissions"""
        user = self.request.user
        if user.is_staff:
            return self.queryset
        
        # Filter based on visibility settings
        return self.queryset.filter(
            Q(is_public=True) |
            Q(visible_to_users=user) |
            Q(visible_to_groups__members=user) |
            Q(created_by=user)
        ).distinct()

    @action(detail=True, methods=['post'], permission_classes=[CanRSVPToEvent])
    def rsvp(self, request, pk=None):
        """RSVP to an event"""
        event = self.get_object()
        serializer = RSVPSerializer(data=request.data)
        
        if serializer.is_valid():
            new_status = serializer.validated_data['status']
            old_status = event.get_user_rsvp_status(request.user)
            
            # Remove user from all RSVP lists first
            event.rsvp_yes.remove(request.user)
            event.rsvp_no.remove(request.user)
            event.rsvp_maybe.remove(request.user)
            
            # Add user to appropriate RSVP list
            if new_status == 'yes':
                event.rsvp_yes.add(request.user)
            elif new_status == 'no':
                event.rsvp_no.add(request.user)
            elif new_status == 'maybe':
                event.rsvp_maybe.add(request.user)
            
            # Log RSVP change
            EventRSVPLog.objects.create(
                event=event,
                user=request.user,
                old_status=old_status,
                new_status=new_status
            )
            
            return Response({
                'message': f'RSVP updated to {new_status}',
                'status': new_status,
                'total_rsvp_yes': event.total_rsvp_yes,
                'total_rsvp_no': event.total_rsvp_no,
                'total_rsvp_maybe': event.total_rsvp_maybe
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], permission_classes=[IsAdminOrReadOnly])
    def rsvp_list(self, request, pk=None):
        """Get RSVP list for an event (admin/owner only)"""
        event = self.get_object()
        
        from .serializers import UserSerializer
        
        rsvp_data = {
            'yes': UserSerializer(event.rsvp_yes.all(), many=True).data,
            'no': UserSerializer(event.rsvp_no.all(), many=True).data,
            'maybe': UserSerializer(event.rsvp_maybe.all(), many=True).data,
        }
        
        return Response(rsvp_data)

    @action(detail=True, methods=['get'], permission_classes=[IsAdminOrReadOnly])
    def analytics(self, request, pk=None):
        """Get event analytics"""
        event = self.get_object()
        
        # Calculate daily RSVP changes for last 30 days
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        daily_rsvp = []
        current_date = start_date
        while current_date <= end_date:
            rsvp_count = EventRSVPLog.objects.filter(
                event=event,
                changed_at__date=current_date
            ).count()
            
            daily_rsvp.append({
                'date': current_date.isoformat(),
                'count': rsvp_count
            })
            
            current_date += timedelta(days=1)

        total_visible_users = self.get_total_visible_users(event)
        
        analytics_data = {
            'total_rsvp_yes': event.total_rsvp_yes,
            'total_rsvp_no': event.total_rsvp_no,
            'total_rsvp_maybe': event.total_rsvp_maybe,
            'total_rsvp': event.total_rsvp,
            'rsvp_rate': (event.total_rsvp / total_visible_users * 100) if total_visible_users > 0 else 0,
            'daily_rsvp': daily_rsvp
        }
        
        serializer = EventAnalyticsSerializer(analytics_data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def my_events(self, request):
        """Get current user's created events"""
        queryset = self.get_queryset().filter(created_by=request.user)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming events"""
        queryset = self.get_queryset().filter(date__gte=timezone.now().date())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_total_visible_users(self, event):
        """Calculate total number of users who can see this event"""
        from django.contrib.auth.models import User
        
        if event.is_public:
            return User.objects.filter(is_active=True).count()
        
        visible_users = set()
        
        # Add directly visible users
        for user in event.visible_to_users.all():
            visible_users.add(user.id)
        
        # Add users from visible groups
        for group in event.visible_to_groups.all():
            for user in group.members.all():
                visible_users.add(user.id)
        
        return len(visible_users)


class MediaViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing media uploads
    """
    queryset = Media.objects.all()
    serializer_class = MediaSerializer
    permission_classes = [IsMediaOwnerOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['file_type']
    search_fields = ['file_name']
    ordering_fields = ['uploaded_at']
    ordering = ['-uploaded_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return MediaUploadSerializer
        return MediaSerializer

    def get_queryset(self):
        """Filter media based on user permissions"""
        user = self.request.user
        if user.is_staff:
            return self.queryset
        return self.queryset.filter(uploaded_by=user)

    @action(detail=False, methods=['get'])
    def my_uploads(self, request):
        """Get current user's uploaded media"""
        queryset = self.queryset.filter(uploaded_by=request.user)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class GroupViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing groups
    """
    queryset = Group.objects.filter(is_active=True)
    serializer_class = GroupSerializer
    permission_classes = [IsGroupOwnerOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['group_type', 'department']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'name']
    ordering = ['name']

    def get_queryset(self):
        """Filter groups based on user permissions"""
        user = self.request.user
        if user.is_staff:
            return self.queryset
        
        # Return public groups, groups user is a member of, or groups user owns
        return self.queryset.filter(
            Q(group_type='public') |
            Q(members=user) |
            Q(owners=user) |
            Q(created_by=user)
        ).distinct()

    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        """Join a public group"""
        group = self.get_object()
        
        if group.group_type != 'public':
            return Response(
                {'error': 'Cannot join private groups'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        group.members.add(request.user)
        return Response({'message': 'Successfully joined group'})

    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        """Leave a group"""
        group = self.get_object()
        group.members.remove(request.user)
        return Response({'message': 'Successfully left group'})

    @action(detail=False, methods=['get'])
    def my_groups(self, request):
        """Get groups user is a member of"""
        queryset = self.queryset.filter(members=request.user)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)