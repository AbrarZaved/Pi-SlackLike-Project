from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from firebase_admin import auth
from .firebase import get_firebase_app
from .models import User, Role, Permission
from .serializers import (
    AdminLoginSerializer,
    SendOTPSerializer,
    VerifyOTPSerializer,
    LoginResponseSerializer,
    UserSerializer,
    RoleSerializer
)
from .permissions import (
    HasPermission, 
    IsAdmin, 
    PermissionConstants,
    get_user_permissions
)
from .tasks import send_welcome_email, send_otp_email


# ====================
# User ViewSet
# ====================

class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing users.
    
    Provides CRUD operations for users with proper permission checks.
    """
    queryset = User.objects.all().select_related('role')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    
    @extend_schema(
        description="Get all users in the system",
        parameters=[
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search users by email, name, or phone number',
                required=False
            )
        ],
        tags=['Users']
    )
    def list(self, request):
        """List all users."""
        users = self.get_queryset()
        
        # Search filter
        search_query = request.query_params.get('search', None)
        if search_query:
            from django.db.models import Q
            users = users.filter(
                Q(email__icontains=search_query) |
                Q(name__icontains=search_query) |
                Q(phone_number__icontains=search_query)
            )
        
        data = [
            {
                'id': user.id,
                'email': user.email,
                'name': user.name,
                'role': user.role_name,
                'status': user.status,
                'phone_number': user.phone_number,
            }
            for user in users
        ]
        return Response({'count': len(data), 'results': data})
    
    @extend_schema(
        description="Create a new user",
        tags=['Users']
    )
    def create(self, request, *args, **kwargs):
        """Create a new user."""
        return super().create(request, *args, **kwargs)
    
    @extend_schema(
        description="Get user details by ID",
        tags=['Users']
    )
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a specific user."""
        return super().retrieve(request, *args, **kwargs)
    
    @extend_schema(
        description="Update user (full update)",
        tags=['Users']
    )
    def update(self, request, *args, **kwargs):
        """Update a user (PUT)."""
        return super().update(request, *args, **kwargs)
    
    @extend_schema(
        description="Partially update user",
        tags=['Users']
    )
    def partial_update(self, request, *args, **kwargs):
        """Partially update a user (PATCH)."""
        return super().partial_update(request, *args, **kwargs)
    
    @extend_schema(
        description="Delete a user",
        tags=['Users']
    )
    def destroy(self, request, *args, **kwargs):
        """Delete a user."""
        return super().destroy(request, *args, **kwargs)


# ====================
# Role ViewSet
# ====================

class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing roles and permissions.
    
    Read-only access to roles and their permissions.
    """
    queryset = Role.objects.all().prefetch_related('permissions')
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        description="Get all available roles",
        tags=['Roles']
    )
    def list(self, request):
        """List all roles."""
        roles = self.get_queryset()
        data = [
            {
                'id': role.id,
                'name': role.name,
                'slug': role.slug,
                'description': role.description,
                'permission_count': role.permissions.count(),
            }
            for role in roles
        ]
        return Response(data)
    
    @extend_schema(
        description="Get role details with all permissions",
        tags=['Roles']
    )
    def retrieve(self, request, pk=None):
        """Get role details with permissions."""
        try:
            role = self.get_queryset().get(pk=pk)
            permissions = role.permissions.all()
            
            data = {
                'id': role.id,
                'name': role.name,
                'slug': role.slug,
                'description': role.description,
                'permissions': [
                    {
                        'codename': perm.codename,
                        'name': perm.name,
                        'category': perm.get_category_display(),
                    }
                    for perm in permissions
                ]
            }
            return Response(data)
        except Role.DoesNotExist:
            return Response(
                {'error': 'Role not found'},
                status=status.HTTP_404_NOT_FOUND
            )


# ====================
# API Views
# ====================

class MyPermissionsView(APIView):
    """
    Get current user's permissions.
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        description="Get current user's permissions",
        tags=['Permissions']
    )
    def get(self, request):
        """Get current user's permissions."""
        user = request.user
        permissions = get_user_permissions(user)
        
        return Response({
            'user': user.email,
            'role': user.role_name,
            'permissions': permissions,
            'permission_count': len(permissions),
        })



# ====================
# OTP Authentication APIs
# ====================

class SendOTPView(APIView):
    """
    Request OTP for passwordless login/registration.
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        description="""
        Request OTP for passwordless login/registration.
        
        Send a 6-digit OTP to the user's email address. The OTP is valid for 10 minutes.
        If the user doesn't exist, a new account will be created automatically.
        Use this OTP with the /verify-otp/ endpoint to login and receive JWT tokens.
        """,
        request=SendOTPSerializer,
        tags=['Authentication']
    )
    def post(self, request):
        """
        Request OTP for passwordless login/registration.
        
        This endpoint generates a 6-digit OTP and sends it to the user's email.
        If the user doesn't exist, a new account is created automatically.
        The OTP is valid for 10 minutes. Use it with /verify-otp/ to login.
        
        Request Body:
            {
                "email": "user@example.com"
            }
        
        Response:
            {
                "success": true,
                "message": "OTP sent to your email",
                "email": "user@example.com",
                "is_new_user": false
            }
        """
        serializer = SendOTPSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {'error': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        email = serializer.validated_data['email']
        
        try:
            # Get Customer role for new users
            from django.db.models import Q
            try:
                customer_role = Role.objects.get(Q(slug='customer') | Q(name__iexact='customer'))
            except Role.DoesNotExist:
                customer_role = None  # Will be assigned when role is created
            
            # Try to get existing user or create new one
            defaults = {
                'is_active': True,
                'role': customer_role
            }
                
            user, created = User.objects.get_or_create(
                email=email,
                defaults=defaults
            )
            
            # Generate OTP
            otp = user.generate_otp()
            
            # Send OTP via email asynchronously
            send_otp_email.delay(user.id, otp)
            
            return Response({
                'success': True,
                'message': 'OTP sent to your email',
                'email': email,
                'is_new_user': created,
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to send OTP: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VerifyOTPView(APIView):
    """
    Verify OTP and login user (Passwordless Authentication).
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        description="""
        Verify OTP and login user (Passwordless Authentication).
        
        This endpoint verifies the OTP sent to user's email and returns JWT tokens
        for authentication. Use these tokens for subsequent API requests.
        """,
        request=VerifyOTPSerializer,
        responses={200: LoginResponseSerializer},
        tags=['Authentication']
    )
    def post(self, request):
        """
        Verify OTP and login user.
        
        This endpoint verifies the OTP sent to user's email.
        Upon successful verification, returns JWT access and refresh tokens.
        
        Request Body:
            {
                "email": "user@example.com",
                "otp": "123456"
            }
        
        Response:
            {
                "success": true,
                "message": "Login successful",
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "user": {
                    "id": 1,
                    "email": "user@example.com",
                    "role": "Admin",
                    "phone_number": "+1234567890"
                }
            }
        
        Use the access_token in the Authorization header for subsequent requests:
            Authorization: Bearer <access_token>
        """
        serializer = VerifyOTPSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {'error': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        
        try:
            user = User.objects.get(email=email)
            
            # Verify OTP
            is_valid, message = user.verify_otp(otp)
            
            if is_valid:
                # Generate JWT tokens
                refresh = RefreshToken.for_user(user)
                access_token = str(refresh.access_token)
                refresh_token = str(refresh)
                
                return Response({
                    'success': True,
                    'message': 'Login successful',
                    'access_token': access_token,
                    'refresh_token': refresh_token,
                    'user': {
                        'id': user.id,
                        'email': user.email,
                        'role': user.role_name,
                        'phone_number': user.phone_number,
                        'status': user.status,
                    }
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'error': message
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except User.DoesNotExist:
            return Response(
                {'error': 'User with this email does not exist'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to verify OTP: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# Social Auth

class FirebaseAuthView(APIView):
    """
    Authenticate user using Firebase ID token.
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        description="Authenticate user using Firebase ID token and send OTP",
        request=OpenApiTypes.OBJECT,
        tags=['Authentication']
    )
    def post(self, request):
        """Authenticate user using Firebase ID token and send OTP."""
        id_token = request.data.get('id_token')
        
        if not id_token:
            return Response(
                {'error': 'ID token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            firebase_app = get_firebase_app()
            decoded_token = auth.verify_id_token(id_token, app=firebase_app)
            email = decoded_token.get('email')
            
            if not email:
                return Response(
                    {'error': 'Email not found in token'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get Customer role for new users
            from django.db.models import Q
            try:
                customer_role = Role.objects.get(Q(slug='customer') | Q(name__iexact='customer'))
            except Role.DoesNotExist:
                customer_role = None
            
            # Get or create user
            defaults = {
                'is_active': True,
                'role': customer_role
            }
            
            user, created = User.objects.get_or_create(
                email=email,
                defaults=defaults
            )
            
            # Generate OTP
            otp = user.generate_otp()
            
            # Send OTP via email asynchronously
            send_otp_email.delay(user.id, otp)
            
            return Response({
                'success': True,
                'message': 'OTP sent to your email',
                'email': email,
                'is_new_user': created,
            }, status=status.HTTP_200_OK)
            
        except auth.InvalidIdTokenError:
            return Response(
                {'error': 'Invalid ID token'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to send OTP: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# Admin Login

class AdminLoginView(APIView):
    """
    Admin login using email and password.
    """
    permission_classes = [AllowAny]
    serializer_class = AdminLoginSerializer
    @extend_schema(
        description="Admin login using email and password",
        request=AdminLoginSerializer,
        responses={200: LoginResponseSerializer},
        tags=['Authentication']
    )
    def post(self, request):
        """Admin login using email and password."""
        serializer = self.serializer_class(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {'error': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        
        try:
            # Get user by email
            user = User.objects.select_related('role').get(email=email)
            
            # Check if user is active
            if not user.is_active:
                return Response(
                    {'error': 'User account is disabled'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check password
            if not user.check_password(password):
                return Response(
                    {'error': 'Invalid email or password'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Check if user has admin role
            if not user.role or user.role.slug != 'admin':
                return Response(
                    {'error': 'Access denied. Admin privileges required.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)
            
            return Response({
                'success': True,
                'message': 'Login successful',
                'access_token': access_token,
                'refresh_token': refresh_token,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'role': user.role_name,
                    'phone_number': user.phone_number,
                    'status': user.status,
                }
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response(
                {'error': 'Invalid email or password'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            return Response(
                {'error': f'Login failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class HealthCheckView(APIView):
    """
    Health check endpoint - no authentication required.
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        description="Health check endpoint",
        tags=['Health']
    )
    def get(self, request):
        """Health check endpoint."""
        return Response({
            'status': 'healthy',
            'version': '1.0.0',
            'timestamp': str(request.META.get('HTTP_DATE', '')),
        })
