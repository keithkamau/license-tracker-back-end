from rest_framework import permissions


class IsLicenseOwnerOrAdmin(permissions.BasePermission):
    """Permission to allow access to license owners, HR, or admin."""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Admin and HR can access any license
        if request.user.is_admin or request.user.is_hr:
            return True
        
        # Agents can only access their own license
        return obj.agent == request.user


class CanUploadLicense(permissions.BasePermission):
    """Permission to allow only agents to upload licenses."""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_agent


class CanVerifyLicense(permissions.BasePermission):
    """Permission to allow only admin and HR to verify licenses."""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_admin or request.user.is_hr
        )