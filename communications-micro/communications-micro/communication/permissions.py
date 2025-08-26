from rest_framework.permissions import BasePermission
from django.contrib.auth.models import User


class IsAdminOrReadOnly(BasePermission):
    """
    Custom permission to only allow admins to edit objects.
    """
    def has_permission(self, request, view):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return request.user.is_authenticated
        return request.user.is_staff

    def has_object_permission(self, request, view, obj):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        return request.user.is_staff


class IsBroadcastOwnerOrAdmin(BasePermission):
    """
    Custom permission to allow broadcast owners or admins to edit broadcasts.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Read permissions for any authenticated user if they can see the broadcast
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return self.can_view_broadcast(request.user, obj)
        
        # Write permissions only for admins or broadcast owner
        return request.user.is_staff or obj.created_by == request.user

    def can_view_broadcast(self, user, broadcast):
        """Check if user can view this broadcast"""
        if not broadcast.is_visible:
            return False
        
        if broadcast.audience_type == 'all':
            return True
        elif broadcast.audience_type == 'groups':
            return broadcast.target_groups.filter(members=user).exists()
        elif broadcast.audience_type == 'users':
            return broadcast.target_users.filter(id=user.id).exists()
        
        return False


class IsEventOwnerOrAdmin(BasePermission):
    """
    Custom permission to allow event owners or admins to edit events.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Read permissions for users who can view the event
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return obj.user_can_view(request.user)
        
        # Write permissions only for admins or event owner
        return request.user.is_staff or obj.created_by == request.user


class IsGroupOwnerOrAdmin(BasePermission):
    """
    Custom permission to allow group owners or admins to edit groups.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Read permissions for group members
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return (obj.group_type == 'public' or 
                   obj.members.filter(id=request.user.id).exists() or
                   obj.owners.filter(id=request.user.id).exists() or
                   request.user.is_staff)
        
        # Write permissions for group owners or admins
        return (obj.owners.filter(id=request.user.id).exists() or 
               request.user.is_staff)


class CanRSVPToEvent(BasePermission):
    """
    Custom permission to check if user can RSVP to an event.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return obj.user_can_view(request.user) and obj.is_upcoming


class CanAcknowledgeBroadcast(BasePermission):
    """
    Custom permission to check if user can acknowledge a broadcast.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # User can acknowledge if they can view the broadcast and it's currently visible
        if not obj.is_visible:
            return False
            
        if obj.audience_type == 'all':
            return True
        elif obj.audience_type == 'groups':
            return obj.target_groups.filter(members=request.user).exists()
        elif obj.audience_type == 'users':
            return obj.target_users.filter(id=request.user.id).exists()
        
        return False


class IsMediaOwnerOrAdmin(BasePermission):
    """
    Custom permission for media files.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        return request.user.is_staff or obj.uploaded_by == request.user