from rest_framework import permissions


class IsAdminOrHR(permissions.BasePermission):
    """Permission to allow only Admins and HR."""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_admin or request.user.is_hr
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    """Permission to allow only object owners or admins."""
    
    def has_object_permission(self, request, view, obj):
        # Admin can do anything
        if request.user.is_admin:
            return True
        
        # HR can modify agents but not other admins
        if request.user.is_hr:
            return not obj.is_admin
        
        # Users can only modify themselves
        return obj == request.user


class IsAdmin(permissions.BasePermission):
    """Permission to allow only Admins."""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin


class IsAgentOwner(permissions.BasePermission):
    """Permission to allow agents to only access their own license data."""
    
    def has_object_permission(self, request, view, obj):
        # Admin and HR can access all
        if request.user.is_admin or request.user.is_hr:
            return True
        
        # Agents can only access their own license
        return obj.agent == request.user