"""
API views for the accounts app.

Provides endpoints for user registration, login, logout, profile management,
address management, admin user CRUD, user suspension/activation, user notes,
and the admin audit log.
"""
from rest_framework import generics, status, permissions
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from django.conf import settings
from django.contrib.auth import authenticate
from django.db import transaction
from django.shortcuts import render
from django.views import View


class LoginRateThrottle(AnonRateThrottle):
    """Throttle for the login endpoint — uses the 'login' scope (5/min)."""
    scope = 'login'


class RegisterRateThrottle(AnonRateThrottle):
    """Throttle for the register endpoint — uses the 'register' scope (10/hr)."""
    scope = 'register'

from .models import AdminAuditLog, User, Address, UserNote
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer, UserUpdateSerializer,
    AdminUserSerializer, AdminUserCreateSerializer, AddressSerializer,
    UserNoteSerializer, PasswordChangeSerializer, AdminAuditLogSerializer,
    PharmacistActivationSetPasswordSerializer, ProfessionalRegistrationSerializer,
    PublicLabPartnerListSerializer,
)
from .permissions import IsAdminUser
from .utils import (
    get_valid_pharmacist_activation,
    issue_pharmacist_activation_token,
    log_admin_action,
    send_pharmacist_activation_email,
)
from apps.lab.models import LabPartner


class RegisterView(generics.CreateAPIView):
    """Public endpoint to self-register a new user account.

    Returns the new user profile alongside fresh JWT access and refresh tokens.
    """
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def create(self, request, *args, **kwargs):
        """Register the user and return JWT tokens alongside the user profile."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


class ProfessionalRegistrationView(APIView):
    """Public endpoint for doctor, pediatrician, lab partner, and lab tech applications."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterRateThrottle]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        serializer = ProfessionalRegistrationSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        application = serializer.save()
        return Response(serializer.build_response(application), status=status.HTTP_201_CREATED)


class PublicLabPartnerListView(generics.ListAPIView):
    """Public endpoint exposing verified lab partners for lab-tech registration."""

    permission_classes = [permissions.AllowAny]
    serializer_class = PublicLabPartnerListSerializer
    search_fields = ['name', 'location', 'accreditation']
    ordering = ['name']

    def get_queryset(self):
        return LabPartner.objects.filter(status=LabPartner.STATUS_VERIFIED).order_by('name')


class LoginView(APIView):
    """Public endpoint to authenticate with email/password and receive JWT tokens."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        """Validate credentials and return JWT tokens on success.

        Returns HTTP 401 for invalid credentials and HTTP 403 for suspended accounts.
        """
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data['email'],
            password=serializer.validated_data['password']
        )
        if not user:
            return Response({'detail': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)
        if user.status == User.STATUS_SUSPENDED:
            return Response({'detail': 'Account suspended. Contact support.'}, status=status.HTTP_403_FORBIDDEN)
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        })


class LogoutView(APIView):
    """Blacklist the provided refresh token to invalidate the user session."""

    def post(self, request):
        """Blacklist the refresh token; errors are silently ignored."""
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            pass
        return Response({'detail': 'Logged out successfully.'}, status=status.HTTP_200_OK)


class MeView(generics.RetrieveUpdateAPIView):
    """Retrieve or update the authenticated user's own profile."""

    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Return the currently authenticated user as the object."""
        return self.request.user

    def get_serializer_class(self):
        """Use UserUpdateSerializer for write operations, UserSerializer for reads."""
        if self.request.method in ['PUT', 'PATCH']:
            return UserUpdateSerializer
        return UserSerializer


class PasswordChangeView(APIView):
    """Allow an authenticated user to change their own password."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Validate old password, then set the new password."""
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response({'old_password': 'Wrong password.'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'detail': 'Password updated successfully.'})


class PharmacistActivationSetPasswordView(APIView):
    """Public endpoint to set pharmacist password via one-time activation token."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def post(self, request):
        serializer = PharmacistActivationSetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({
            'detail': 'Password set successfully. You can now log in.',
            'user': {
                'id': user.id,
                'email': user.email,
                'role': user.role,
            },
            'dashboard_url': getattr(settings, 'FRONTEND_PHARMACIST_DASHBOARD_URL', 'http://localhost:3000/pharmacist/dashboard'),
        })


class PharmacistActivationPageView(View):
    """Server-rendered fallback page for pharmacist password activation."""

    template_name = 'accounts/pharmacist_activate.html'

    def get(self, request, token):
        token_obj = get_valid_pharmacist_activation(token)
        context = {
            'token': token,
            'token_valid': token_obj is not None,
            'dashboard_url': getattr(settings, 'FRONTEND_PHARMACIST_DASHBOARD_URL', 'http://localhost:3000/pharmacist/dashboard'),
            'login_url': getattr(settings, 'FRONTEND_LOGIN_URL', 'http://localhost:3000/login'),
        }
        if token_obj:
            context['email'] = token_obj.user.email
        return render(request, self.template_name, context)

    def post(self, request, token):
        serializer = PharmacistActivationSetPasswordSerializer(data={
            'token': token,
            'new_password': request.POST.get('new_password', ''),
            'new_password_confirm': request.POST.get('new_password_confirm', ''),
        })
        context = {
            'token': token,
            'token_valid': True,
            'dashboard_url': getattr(settings, 'FRONTEND_PHARMACIST_DASHBOARD_URL', 'http://localhost:3000/pharmacist/dashboard'),
            'login_url': getattr(settings, 'FRONTEND_LOGIN_URL', 'http://localhost:3000/login'),
        }
        if serializer.is_valid():
            user = serializer.save()
            context.update({
                'success': True,
                'email': user.email,
            })
            return render(request, self.template_name, context)
        context['errors'] = serializer.errors
        token_obj = get_valid_pharmacist_activation(token)
        context['token_valid'] = token_obj is not None
        if token_obj:
            context['email'] = token_obj.user.email
        return render(request, self.template_name, context)


class AdminUserListCreateView(generics.ListCreateAPIView):
    """Admin endpoint to list all users or create a new user of any role."""

    permission_classes = [IsAdminUser]
    filterset_fields = ['role', 'status']
    search_fields = ['email', 'first_name', 'last_name', 'phone']
    ordering_fields = ['date_joined', 'first_name', 'email']
    ordering = ['-date_joined']

    def get_queryset(self):
        """Return all users with related pharmacist records, addresses, and orders."""
        return User.objects.all().select_related('pharmacist', 'customer_profile').prefetch_related('addresses', 'orders')

    def get_serializer_class(self):
        """Use AdminUserCreateSerializer for POST, AdminUserSerializer for GET."""
        if self.request.method == 'POST':
            return AdminUserCreateSerializer
        return AdminUserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        payload = {'user': AdminUserSerializer(self.created_user).data}
        if getattr(self, 'activation_email_meta', None):
            payload['activation_email'] = self.activation_email_meta
        return Response(payload, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        """Save the new user and write an audit log entry."""
        with transaction.atomic():
            user = serializer.save()
            self.created_user = user
            self.activation_email_meta = getattr(serializer, 'activation_email_meta', None)
            log_admin_action(
                self.request.user,
                action='user_created',
                entity_type='user',
                entity_id=user.id,
                message=f'Created user {user.email}',
                metadata={'role': user.role},
            )


class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin endpoint to retrieve, update, or delete a specific user."""

    permission_classes = [IsAdminUser]
    queryset = User.objects.all().select_related('pharmacist', 'customer_profile').prefetch_related('addresses', 'orders')

    def get_serializer_class(self):
        """Use AdminUserCreateSerializer for PUT/PATCH, AdminUserSerializer for GET."""
        if self.request.method in ['PUT', 'PATCH']:
            return AdminUserCreateSerializer
        return AdminUserSerializer

    def perform_update(self, serializer):
        """Save changes and write an audit log entry."""
        user = serializer.save()
        log_admin_action(
            self.request.user,
            action='user_updated',
            entity_type='user',
            entity_id=user.id,
            message=f'Updated user {user.email}',
            metadata={'role': user.role, 'status': user.status},
        )


class AdminUserSuspendView(APIView):
    """Admin endpoint to suspend (deactivate) a user account."""

    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        """Set user status to suspended and is_active to False."""
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        user.status = User.STATUS_SUSPENDED
        user.is_active = False
        user.save()
        log_admin_action(
            request.user,
            action='user_suspended',
            entity_type='user',
            entity_id=user.id,
            message=f'Suspended user {user.email}',
        )
        return Response({'detail': 'User suspended.'})


class AdminUserActivateView(APIView):
    """Admin endpoint to re-activate a previously suspended user account."""

    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        """Set user status to active and is_active to True."""
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        user.status = User.STATUS_ACTIVE
        user.is_active = True
        user.save()
        log_admin_action(
            request.user,
            action='user_activated',
            entity_type='user',
            entity_id=user.id,
            message=f'Activated user {user.email}',
        )
        return Response({'detail': 'User activated.'})


class AdminPharmacistActivationResendView(APIView):
    """Admin endpoint to resend pharmacist activation email."""

    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        if user.role != User.PHARMACIST:
            return Response({'detail': 'Activation resend is only available for pharmacists.'}, status=status.HTTP_400_BAD_REQUEST)
        if user.status == User.STATUS_SUSPENDED:
            return Response({'detail': 'Cannot resend activation for a suspended account.'}, status=status.HTTP_400_BAD_REQUEST)
        if user.is_active and user.has_usable_password():
            return Response({'detail': 'This pharmacist account is already activated.'}, status=status.HTTP_400_BAD_REQUEST)

        token, raw_token = issue_pharmacist_activation_token(user, created_by=request.user)
        send_pharmacist_activation_email(
            user=user,
            raw_token=raw_token,
            request=request,
            invited_by=request.user,
        )
        log_admin_action(
            request.user,
            action='pharmacist_activation_resent',
            entity_type='user',
            entity_id=user.id,
            message=f'Resent pharmacist activation email to {user.email}',
            metadata={'expires_at': token.expires_at.isoformat()},
        )
        return Response({
            'detail': 'Activation email resent successfully.',
            'activation_email': {
                'sent_to': user.email,
                'expires_at': token.expires_at,
            },
        })


class AddressListCreateView(generics.ListCreateAPIView):
    """List or create delivery addresses for the authenticated user."""

    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return only addresses belonging to the current user."""
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Unset any existing default address if the new one is marked as default."""
        if serializer.validated_data.get('is_default'):
            Address.objects.filter(user=self.request.user).update(is_default=False)
        serializer.save(user=self.request.user)


class AddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific address for the authenticated user."""

    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Scope queryset to the current user's addresses."""
        return Address.objects.filter(user=self.request.user)

    def perform_update(self, serializer):
        """Unset other default addresses when this one is set as default."""
        if serializer.validated_data.get('is_default'):
            Address.objects.filter(user=self.request.user).exclude(pk=self.get_object().pk).update(is_default=False)
        serializer.save()


class UserNoteListCreateView(generics.ListCreateAPIView):
    """Admin endpoint to list or add internal notes for a specific user."""

    serializer_class = UserNoteSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        """Return all notes for the user identified by URL kwarg ``pk``."""
        return UserNote.objects.filter(user_id=self.kwargs['pk'])

    def perform_create(self, serializer):
        """Associate the note with the target user and the current admin as author."""
        serializer.save(user_id=self.kwargs['pk'], created_by=self.request.user)


class AdminAuditLogListView(generics.ListAPIView):
    """Admin read-only endpoint to browse the full admin audit log."""

    permission_classes = [IsAdminUser]
    serializer_class = AdminAuditLogSerializer
    filterset_fields = ['action', 'entity_type']
    search_fields = ['message', 'entity_id', 'actor__email']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    queryset = AdminAuditLog.objects.all().select_related('actor')
