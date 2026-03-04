from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, PharmacistProfile, Address, UserNote


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone', 'password', 'password_confirm', 'role')

    def validate_role(self, value):
        allowed = [User.CUSTOMER, User.DOCTOR, User.PEDIATRICIAN, User.PHARMACIST, User.LAB_TECHNICIAN]
        if value not in allowed:
            raise serializers.ValidationError('Invalid role for self-registration.')
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password_confirm'):
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        if user.role == User.PHARMACIST:
            PharmacistProfile.objects.create(user=user)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    total_orders = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = (
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'role', 'status', 'address', 'total_orders',
            'date_joined', 'updated_at'
        )
        read_only_fields = ('id', 'date_joined', 'updated_at')


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'phone', 'address')


class AdminUserSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    total_orders = serializers.ReadOnlyField()
    pharmacist_permissions = serializers.SerializerMethodField()
    last_order_date = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'role', 'status', 'address', 'total_orders',
            'last_order_date', 'date_joined', 'pharmacist_permissions'
        )

    def get_pharmacist_permissions(self, obj):
        if hasattr(obj, 'pharmacist_profile'):
            return obj.pharmacist_profile.permissions
        return []

    def get_last_order_date(self, obj):
        last = obj.orders.order_by('-created_at').first()
        return last.created_at if last else None


class AdminUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    pharmacist_permissions = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone', 'role', 'address', 'password', 'pharmacist_permissions')

    def create(self, validated_data):
        permissions = validated_data.pop('pharmacist_permissions', [])
        user = User.objects.create_user(**validated_data)
        if user.role == User.PHARMACIST:
            PharmacistProfile.objects.create(user=user, permissions=permissions)
        return user


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ('id', 'label', 'street', 'city', 'county', 'is_default', 'created_at')
        read_only_fields = ('id', 'created_at')


class UserNoteSerializer(serializers.ModelSerializer):
    created_by_name = serializers.ReadOnlyField(source='created_by.full_name')

    class Meta:
        model = UserNote
        fields = ('id', 'content', 'created_by', 'created_by_name', 'created_at')
        read_only_fields = ('id', 'created_by', 'created_at')


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password': 'Passwords do not match.'})
        return attrs
