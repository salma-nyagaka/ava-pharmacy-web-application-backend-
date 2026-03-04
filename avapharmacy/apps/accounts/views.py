from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from django.contrib.auth import authenticate


class LoginRateThrottle(AnonRateThrottle):
    scope = 'login'


class RegisterRateThrottle(AnonRateThrottle):
    scope = 'register'

from .models import AdminAuditLog, User, Address, UserNote
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer, UserUpdateSerializer,
    AdminUserSerializer, AdminUserCreateSerializer, AddressSerializer,
    UserNoteSerializer, PasswordChangeSerializer, AdminAuditLogSerializer
)
from .permissions import IsAdminUser
from .utils import log_admin_action


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def create(self, request, *args, **kwargs):
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


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
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
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            pass
        return Response({'detail': 'Logged out successfully.'}, status=status.HTTP_200_OK)


class MeView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UserUpdateSerializer
        return UserSerializer


class PasswordChangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response({'old_password': 'Wrong password.'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'detail': 'Password updated successfully.'})


class AdminUserListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    filterset_fields = ['role', 'status']
    search_fields = ['email', 'first_name', 'last_name', 'phone']
    ordering_fields = ['date_joined', 'first_name', 'email']
    ordering = ['-date_joined']

    def get_queryset(self):
        return User.objects.all().select_related('pharmacist_profile').prefetch_related('addresses', 'orders')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AdminUserCreateSerializer
        return AdminUserSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        log_admin_action(
            self.request.user,
            action='user_created',
            entity_type='user',
            entity_id=user.id,
            message=f'Created user {user.email}',
            metadata={'role': user.role},
        )


class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    queryset = User.objects.all().select_related('pharmacist_profile').prefetch_related('addresses', 'orders')

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return AdminUserCreateSerializer
        return AdminUserSerializer

    def perform_update(self, serializer):
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
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
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
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
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


class AddressListCreateView(generics.ListCreateAPIView):
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        if serializer.validated_data.get('is_default'):
            Address.objects.filter(user=self.request.user).update(is_default=False)
        serializer.save(user=self.request.user)


class AddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_update(self, serializer):
        if serializer.validated_data.get('is_default'):
            Address.objects.filter(user=self.request.user).exclude(pk=self.get_object().pk).update(is_default=False)
        serializer.save()


class UserNoteListCreateView(generics.ListCreateAPIView):
    serializer_class = UserNoteSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return UserNote.objects.filter(user_id=self.kwargs['pk'])

    def perform_create(self, serializer):
        serializer.save(user_id=self.kwargs['pk'], created_by=self.request.user)


class AdminAuditLogListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminAuditLogSerializer
    filterset_fields = ['action', 'entity_type']
    search_fields = ['message', 'entity_id', 'actor__email']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    queryset = AdminAuditLog.objects.all().select_related('actor')
