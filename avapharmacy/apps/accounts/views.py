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
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import render
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.views import View


class LoginRateThrottle(AnonRateThrottle):
    """Throttle for the login endpoint — uses the 'login' scope (5/min)."""
    scope = 'login'


class RegisterRateThrottle(AnonRateThrottle):
    """Throttle for the register endpoint — uses the 'register' scope (10/hr)."""
    scope = 'register'


class ForgotPasswordRateThrottle(AnonRateThrottle):
    """Throttle for password reset requests."""
    scope = 'forgot_password'

from .bot_protection import enforce_public_bot_controls, log_bot_event
from .models import Address, AdminAuditLog, BotRiskEvent, PaymentMethod, User, UserNote
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer, UserUpdateSerializer,
    AdminUserSerializer, AdminUserCreateSerializer, AddressSerializer,
    PaymentMethodSerializer, UserNoteSerializer, PasswordChangeSerializer, AdminAuditLogSerializer,
    PharmacistActivationSetPasswordSerializer, ProfessionalRegistrationSerializer,
    PublicLabPartnerListSerializer,
)
from .permissions import IsAdminOrPPBInspector, IsAdminUser
from .tokens import blacklist_user_refresh_tokens
from .utils import (
    ACTIVATION_ELIGIBLE_ROLES,
    consume_customer_verification,
    dashboard_url_for_role,
    get_valid_customer_verification,
    get_valid_pharmacist_activation,
    issue_customer_verification_token,
    issue_pharmacist_activation_token,
    log_admin_action,
    role_label,
    send_pharmacist_activation_email,
    send_customer_activation_success_email,
    send_customer_verification_email,
    send_professional_application_received_email,
    send_customer_welcome_email,
    send_password_reset_email,
)
from apps.lab.models import LabPartner
from apps.notifications.utils import create_notification


class ActiveUserTokenRefreshSerializer(TokenRefreshSerializer):
    """Refresh serializer that refuses deleted or inactive accounts."""

    def validate(self, attrs):
        refresh = self.token_class(attrs['refresh'])
        user_id = refresh.get('user_id')
        user = User.objects.filter(pk=user_id).first()
        if user is None or not user.is_active or user.status != User.STATUS_ACTIVE:
            raise InvalidToken('User account is inactive or no longer exists.')
        return super().validate(attrs)


class ActiveUserTokenRefreshView(TokenRefreshView):
    serializer_class = ActiveUserTokenRefreshSerializer


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
        enforce_public_bot_controls(
            request,
            BotRiskEvent.EVENT_REGISTER,
            email=serializer.validated_data.get('email', ''),
            phone=serializer.validated_data.get('phone', ''),
        )
        user = serializer.save()
        if user.role == 'customer':
            token, raw_token = issue_customer_verification_token(user)
            send_customer_verification_email(user=user, raw_token=raw_token, request=request)
            return Response({
                'detail': 'Registration successful. Please check your email to verify your account.',
                'verification_email': {
                    'sent_to': user.email,
                    'expires_at': token.expires_at,
                },
                'user': UserSerializer(user).data,
            }, status=status.HTTP_201_CREATED)
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
        enforce_public_bot_controls(
            request,
            BotRiskEvent.EVENT_REGISTER,
            email=serializer.validated_data.get('email', ''),
            phone=serializer.validated_data.get('phone', ''),
        )
        application = serializer.save()
        response_payload = serializer.build_response(application)
        first_name = (getattr(application, 'name', '') or '').split(' ', 1)[0]
        role_label = response_payload['registration_type_display']
        review_url = '/admin/doctors?type=Pediatrician' if response_payload['registration_type'] == 'pediatrician' else '/admin/doctors?type=Doctor'
        try:
            send_professional_application_received_email(
                email=application.email,
                first_name=first_name,
                role_label=role_label,
                reference=getattr(application, 'reference', '') or str(application.pk),
            )
        except Exception:
            pass

        for admin in User.objects.filter(role=User.ADMIN, is_active=True):
            try:
                create_notification(
                    recipient=admin,
                    notification_type='doctor_verified',
                    title=f'New {role_label} application',
                    message=f'{application.name} submitted credentials for review.',
                    data={
                        'url': review_url,
                        'reference': getattr(application, 'reference', '') or str(application.pk),
                        'application_id': application.pk,
                        'professional_type': response_payload['registration_type'],
                    },
                    send_email=False,
                )
            except Exception:
                pass
        return Response(response_payload, status=status.HTTP_201_CREATED)


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
        enforce_public_bot_controls(
            request,
            BotRiskEvent.EVENT_LOGIN,
            email=serializer.validated_data.get('email', ''),
        )
        user = authenticate(
            request,
            username=serializer.validated_data['email'],
            password=serializer.validated_data['password']
        )
        if not user:
            pending_user = User.objects.filter(email__iexact=serializer.validated_data['email']).first()
            if (
                pending_user
                and pending_user.role == User.CUSTOMER
                and pending_user.status == User.STATUS_PENDING_VERIFICATION
                and pending_user.check_password(serializer.validated_data['password'])
            ):
                log_bot_event(
                    request,
                    BotRiskEvent.EVENT_LOGIN,
                    email=serializer.validated_data['email'],
                    risk_score=30,
                    decision=BotRiskEvent.DECISION_VERIFY,
                    reasons=['pending_customer_verification'],
                )
                return Response({'detail': 'Please activate your account via the email we sent you before logging in.'}, status=status.HTTP_403_FORBIDDEN)
            log_bot_event(
                request,
                BotRiskEvent.EVENT_LOGIN,
                email=serializer.validated_data['email'],
                risk_score=40,
                decision=BotRiskEvent.DECISION_BLOCK,
                reasons=['invalid_credentials'],
            )
            return Response({'detail': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)
        if user.status == User.STATUS_SUSPENDED:
            log_bot_event(
                request,
                BotRiskEvent.EVENT_LOGIN,
                user=user,
                risk_score=50,
                decision=BotRiskEvent.DECISION_BLOCK,
                reasons=['suspended_account'],
            )
            return Response({'detail': 'Account suspended. Contact support.'}, status=status.HTTP_403_FORBIDDEN)
        if user.role == User.CUSTOMER and user.status == User.STATUS_PENDING_VERIFICATION:
            log_bot_event(
                request,
                BotRiskEvent.EVENT_LOGIN,
                user=user,
                risk_score=30,
                decision=BotRiskEvent.DECISION_VERIFY,
                reasons=['pending_customer_verification'],
            )
            return Response({'detail': 'Please activate your account via the email we sent you before logging in.'}, status=status.HTTP_403_FORBIDDEN)
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
    """Public endpoint to set staff password via one-time activation token."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def post(self, request):
        serializer = PharmacistActivationSetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        log_admin_action(
            user,
            action='professional_account_verified',
            entity_type='user',
            entity_id=user.id,
            message=f'{user.email} activated their professional account.',
            metadata={'role': user.role},
        )
        return Response({
            'detail': 'Password set successfully. You can now log in.',
            'user': {
                'id': user.id,
                'email': user.email,
                'role': user.role,
            },
            'dashboard_url': dashboard_url_for_role(user.role),
        })


class PharmacistActivationPageView(View):
    """Server-rendered fallback page for staff password activation."""

    template_name = 'accounts/pharmacist_activate.html'

    def get(self, request, token):
        token_obj = get_valid_pharmacist_activation(token)
        account_role = token_obj.user.role if token_obj else None
        context = {
            'token': token,
            'token_valid': token_obj is not None,
            'dashboard_url': dashboard_url_for_role(account_role),
            'login_url': getattr(settings, 'FRONTEND_LOGIN_URL', 'http://localhost:3000/login'),
            'account_role_label': role_label(account_role),
        }
        if token_obj:
            context['email'] = token_obj.user.email
        return render(request, self.template_name, context)

    def post(self, request, token):
        serializer = PharmacistActivationSetPasswordSerializer(data={
            'token': token,
            'new_password': request.POST.get('new_password', ''),
            'new_password_confirm': request.POST.get('new_password_confirm', ''),
            'accepted_terms': request.POST.get('accepted_terms') == 'on',
        })
        context = {
            'token': token,
            'token_valid': True,
            'login_url': getattr(settings, 'FRONTEND_LOGIN_URL', 'http://localhost:3000/login'),
        }
        if serializer.is_valid():
            user = serializer.save()
            context.update({
                'success': True,
                'email': user.email,
                'dashboard_url': dashboard_url_for_role(user.role),
                'account_role_label': role_label(user.role),
            })
            return render(request, self.template_name, context)
        context['errors'] = serializer.errors
        token_obj = get_valid_pharmacist_activation(token)
        context['token_valid'] = token_obj is not None
        context['account_role_label'] = role_label(token_obj.user.role if token_obj else None)
        context['dashboard_url'] = dashboard_url_for_role(token_obj.user.role if token_obj else None)
        if token_obj:
            context['email'] = token_obj.user.email
        return render(request, self.template_name, context)


class ProfessionalActivationSetPasswordView(PharmacistActivationSetPasswordView):
    """Alias endpoint for staff activation."""


class ProfessionalActivationPageView(PharmacistActivationPageView):
    """Alias endpoint for staff activation page."""


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


class AdminCustomerListCreateView(AdminUserListCreateView):
    """Admin customer menu endpoint with customer-only list/create behavior."""

    filterset_fields = ['status']
    ordering_fields = ['date_joined', 'first_name', 'email']

    def get_queryset(self):
        return super().get_queryset().filter(role=User.CUSTOMER)

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data['role'] = User.CUSTOMER
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response({'customer': AdminUserSerializer(self.created_user).data}, status=status.HTTP_201_CREATED, headers=headers)


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
        previous = self.get_object()
        previous_is_active = previous.is_active
        user = serializer.save()
        if previous_is_active and (not user.is_active or user.status != User.STATUS_ACTIVE):
            blacklist_user_refresh_tokens(user)
        log_admin_action(
            self.request.user,
            action='user_updated',
            entity_type='user',
            entity_id=user.id,
            message=f'Updated user {user.email}',
            metadata={'role': user.role, 'status': user.status},
        )

    def perform_destroy(self, instance):
        """Invalidate sessions before permanently deleting an account."""
        user_id = instance.id
        email = instance.email
        blacklist_user_refresh_tokens(instance)
        instance.delete()
        log_admin_action(
            self.request.user,
            action='user_deleted',
            entity_type='user',
            entity_id=user_id,
            message=f'Deleted user {email}',
            )


class AdminCustomerDetailView(AdminUserDetailView):
    """Admin customer detail endpoint that cannot be used for staff records."""

    queryset = User.objects.filter(role=User.CUSTOMER).select_related('customer_profile').prefetch_related('addresses', 'orders')

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        data = request.data.copy()
        data['role'] = User.CUSTOMER
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(AdminUserSerializer(serializer.instance).data)


class AdminCustomerStatsView(APIView):
    """Customer menu summary for ecommerce customer health and value."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.orders.models import Order

        customers = User.objects.filter(role=User.CUSTOMER)
        active_customers = customers.filter(status=User.STATUS_ACTIVE, is_active=True)
        paid_orders = Order.objects.filter(payment_status=Order.PAYMENT_STATUS_PAID, customer__role=User.CUSTOMER)
        customers_with_paid_orders = paid_orders.values('customer_id').distinct().count()
        total_customers = customers.count()

        return Response({
            'total_customers': total_customers,
            'active_customers': active_customers.count(),
            'pending_verification': customers.filter(status=User.STATUS_PENDING_VERIFICATION).count(),
            'suspended_customers': customers.filter(status=User.STATUS_SUSPENDED).count(),
            'customers_with_paid_orders': customers_with_paid_orders,
            'customers_without_orders': max(total_customers - customers_with_paid_orders, 0),
            'total_customer_spend': float(paid_orders.aggregate(total=Sum('total'))['total'] or 0),
            'orders_by_customer_status': [
                {
                    'customer__status': row['customer__status'],
                    'order_count': row['order_count'],
                    'revenue': float(row['revenue'] or 0),
                }
                for row in (
                    Order.objects.filter(customer__role=User.CUSTOMER)
                    .values('customer__status')
                    .annotate(order_count=Count('id'), revenue=Sum('total', filter=Q(payment_status=Order.PAYMENT_STATUS_PAID)))
                    .order_by('customer__status')
                )
            ],
        })


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
        blacklist_user_refresh_tokens(user)
        log_admin_action(
            request.user,
            action='user_suspended',
            entity_type='user',
            entity_id=user.id,
            message=f'Suspended user {user.email}',
        )
        return Response(AdminUserSerializer(user).data)


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
        return Response(AdminUserSerializer(user).data)


class AdminCustomerSuspendView(AdminUserSuspendView):
    """Suspend only customer accounts from the customer menu."""

    def post(self, request, pk):
        if not User.objects.filter(pk=pk, role=User.CUSTOMER).exists():
            return Response({'detail': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)
        return super().post(request, pk)


class AdminCustomerActivateView(AdminUserActivateView):
    """Activate only customer accounts from the customer menu."""

    def post(self, request, pk):
        if not User.objects.filter(pk=pk, role=User.CUSTOMER).exists():
            return Response({'detail': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)
        return super().post(request, pk)


class AdminPharmacistActivationResendView(APIView):
    """Admin endpoint to resend activation email for eligible staff roles."""

    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        if user.role not in ACTIVATION_ELIGIBLE_ROLES:
            return Response({'detail': 'Activation resend is only available for staff accounts.'}, status=status.HTTP_400_BAD_REQUEST)
        if user.status == User.STATUS_SUSPENDED:
            return Response({'detail': 'Cannot resend activation for a suspended account.'}, status=status.HTTP_400_BAD_REQUEST)
        if user.is_active and user.has_usable_password():
            return Response({'detail': 'This account is already activated.'}, status=status.HTTP_400_BAD_REQUEST)

        token, raw_token = issue_pharmacist_activation_token(user, created_by=request.user)
        send_pharmacist_activation_email(
            user=user,
            raw_token=raw_token,
            request=request,
            invited_by=request.user,
        )
        log_admin_action(
            request.user,
            action='staff_activation_resent',
            entity_type='user',
            entity_id=user.id,
            message=f'Resent activation email to {user.email}',
            metadata={'expires_at': token.expires_at.isoformat(), 'role': user.role},
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
        has_existing = Address.objects.filter(user=self.request.user).exists()
        if serializer.validated_data.get('is_default'):
            Address.objects.filter(user=self.request.user).update(is_default=False)
        serializer.save(user=self.request.user, is_default=serializer.validated_data.get('is_default', False) or not has_existing)


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

    def perform_destroy(self, instance):
        was_default = instance.is_default
        user = instance.user
        super().perform_destroy(instance)
        if was_default:
            next_address = Address.objects.filter(user=user).order_by('-created_at').first()
            if next_address:
                next_address.is_default = True
                next_address.save(update_fields=['is_default'])


class PaymentMethodListCreateView(generics.ListCreateAPIView):
    """List or create saved payment methods for the authenticated user."""

    serializer_class = PaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PaymentMethod.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        has_existing = PaymentMethod.objects.filter(user=self.request.user).exists()
        if serializer.validated_data.get('is_default'):
            PaymentMethod.objects.filter(user=self.request.user).update(is_default=False)
        serializer.save(
            user=self.request.user,
            is_default=serializer.validated_data.get('is_default', False) or not has_existing,
        )


class PaymentMethodDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a saved payment method for the authenticated user."""

    serializer_class = PaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PaymentMethod.objects.filter(user=self.request.user)

    def perform_update(self, serializer):
        if serializer.validated_data.get('is_default'):
            PaymentMethod.objects.filter(user=self.request.user).exclude(pk=self.get_object().pk).update(is_default=False)
        serializer.save()

    def perform_destroy(self, instance):
        was_default = instance.is_default
        user = instance.user
        super().perform_destroy(instance)
        if was_default:
            next_method = PaymentMethod.objects.filter(user=user).order_by('-updated_at').first()
            if next_method:
                next_method.is_default = True
                next_method.save(update_fields=['is_default'])


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

    permission_classes = [IsAdminOrPPBInspector]
    serializer_class = AdminAuditLogSerializer
    filterset_fields = ['action', 'entity_type']
    search_fields = ['message', 'entity_id', 'actor__email']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    queryset = AdminAuditLog.objects.all().select_related('actor')


class ForgotPasswordView(APIView):
    """Send a password reset link to the user's email."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [ForgotPasswordRateThrottle]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        if not email:
            return Response(
                {'error': {'code': 'validation_error', 'message': 'Email address is required.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        enforce_public_bot_controls(
            request,
            BotRiskEvent.EVENT_FORGOT_PASSWORD,
            email=email,
        )
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'error': {'code': 'not_found', 'message': 'No account found with that email address.'}},
                status=status.HTTP_404_NOT_FOUND,
            )
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_url = f"{getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:3000')}/reset-password?uid={uid}&token={token}"
        send_password_reset_email(user=user, reset_url=reset_url)
        response_data = {'message': 'A password reset link has been sent to your email.'}
        if settings.DEBUG:
            response_data['reset_url_debug'] = reset_url
  
        return Response(response_data)


class ResetPasswordView(APIView):
    """Set a new password using a uid+token from the reset email."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def post(self, request):
        uid = request.data.get('uid', '')
        token = request.data.get('token', '')
        new_password = request.data.get('new_password', '')

        if not uid or not token or not new_password:
            return Response(
                {'error': {'code': 'validation_error', 'message': 'uid, token and new_password are required.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            user_pk = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_pk)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {'error': {'code': 'invalid_token', 'message': 'Reset link is invalid or has expired.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not default_token_generator.check_token(user, token):
            return Response(
                {'error': {'code': 'invalid_token', 'message': 'Reset link is invalid or has expired.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(new_password) < 8:
            return Response(
                {'error': {'code': 'validation_error', 'message': 'Password must be at least 8 characters.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(new_password)
        user.save()
        return Response({'message': 'Password reset successfully. You can now log in.'})


class VerifyEmailView(APIView):
    """Confirm a customer's email using a one-time verification token."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        raw_token = request.data.get('token') or request.query_params.get('token')
        token = get_valid_customer_verification(raw_token)
        if token is None:
            return Response({'token': 'Verification link is invalid or expired.'}, status=status.HTTP_400_BAD_REQUEST)
        user = token.user
        user.status = User.STATUS_ACTIVE
        user.is_active = True
        user.save(update_fields=['status', 'is_active', 'updated_at'])
        consume_customer_verification(raw_token)
        send_customer_activation_success_email(user=user)
        send_customer_welcome_email(user=user)
        return Response({
            'data': {'email_verified': True, 'user': UserSerializer(user).data},
            'message': 'Email verified successfully. You can now log in.',
        })


class ResendVerificationView(APIView):
    """Resend the email verification link (stub — rate limited)."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def post(self, request):
        email = (request.data.get('email') or '').strip().lower()
        user = User.objects.filter(email__iexact=email, role=User.CUSTOMER).first()
        if user and user.status == User.STATUS_PENDING_VERIFICATION:
            token, raw_token = issue_customer_verification_token(user)
            send_customer_verification_email(user=user, raw_token=raw_token, request=request)
            return Response({
                'message': 'Verification email resent if the address is registered.',
                'verification_email': {'sent_to': user.email, 'expires_at': token.expires_at},
            })
        return Response({'message': 'Verification email resent if the address is registered.'})


class AccountProfileView(generics.RetrieveUpdateAPIView):
    """Retrieve or update the authenticated user's own profile (alias for MeView)."""

    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UserUpdateSerializer
        return UserSerializer


class AccountDeleteView(APIView):
    """Soft-delete the authenticated user's account."""

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        user = request.user
        blacklist_user_refresh_tokens(user)
        user.is_active = False
        user.status = User.STATUS_SUSPENDED
        user.email = f'deleted_{user.pk}_{user.email}'
        user.save(update_fields=['is_active', 'status', 'email', 'updated_at'])
        return Response({'message': 'Account deleted. Personal data will be anonymized within 30 days.'}, status=status.HTTP_200_OK)
