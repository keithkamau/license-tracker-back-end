from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.throttling import UserRateThrottle
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction

from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
    LoginSerializer
)
from .permissions import IsAdminOrHR, IsOwnerOrAdmin

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom JWT token view with additional user data."""
    
    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.check_password(password):
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_active:
            return Response(
                {'error': 'Account is deactivated'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data
        })


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for user management.
    Admins and HR can view all users, agents can only view their own profile.
    """
    queryset = User.objects.all()
    throttle_classes = [UserRateThrottle]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated(), IsAdminOrHR()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsOwnerOrAdmin()]
        elif self.action == 'list':
            return [permissions.IsAuthenticated(), IsAdminOrHR()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        user = self.request.user
        cache_key = f'user_list_{user.role}_{user.id}'
        
        # Try to get from cache
        cached_queryset = cache.get(cache_key)
        if cached_queryset:
            return cached_queryset
        
        # Admins and HR can see all users
        if user.is_admin or user.is_hr:
            queryset = User.objects.all()
        else:
            # Agents can only see themselves
            queryset = User.objects.filter(id=user.id)
        
        # Cache for 5 minutes
        cache.set(cache_key, queryset, 300)
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply filters
        role = request.query_params.get('role', None)
        is_active = request.query_params.get('is_active', None)
        search = request.query_params.get('search', None)
        
        if role:
            queryset = queryset.filter(role=role)
        if is_active is not None:
            is_active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active)
        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(employee_id__icontains=search)
            )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            user = serializer.save()
            # Invalidate cache
            cache.delete_pattern('user_list_*')
        
        return Response(
            UserSerializer(user).data,
            status=status.HTTP_201_CREATED
        )
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        # Add license info if available
        data = serializer.data
        try:
            license = instance.license
            data['license_status'] = license.status
            data['license_expiry'] = license.expiry_date
        except:
            data['license_status'] = None
            data['license_expiry'] = None
        
        return Response(data)
    
    @action(detail=False, methods=['GET'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        """Return the current user's profile."""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['PUT'], permission_classes=[permissions.IsAuthenticated])
    def change_password(self, request):
        """Change user password."""
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        
        # Check old password
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'old_password': 'Wrong password.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Set new password
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        # Invalidate all tokens (optional: implement token blacklist)
        
        return Response({'message': 'Password changed successfully'})
    
    @action(detail=True, methods=['PUT'], permission_classes=[IsAdminOrHR])
    def toggle_status(self, request, pk=None):
        """Toggle user active status."""
        user = self.get_object()
        user.is_active = not user.is_active
        user.save()
        
        # Invalidate cache
        cache.delete_pattern('user_list_*')
        
        return Response({
            'message': f'User {"activated" if user.is_active else "deactivated"} successfully',
            'is_active': user.is_active
        })