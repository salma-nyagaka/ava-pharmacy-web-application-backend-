from rest_framework.permissions import BasePermission
from .models import User


class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role == User.ADMIN
        )


class IsAdminOrSelf(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user.role == User.ADMIN or obj == request.user


class IsPharmacist(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role == User.PHARMACIST
        )


class IsPharmacistOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role in [User.PHARMACIST, User.ADMIN]
        )


class IsDoctor(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role in [User.DOCTOR, User.PEDIATRICIAN]
        )


class IsDoctorOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role in [User.DOCTOR, User.PEDIATRICIAN, User.ADMIN]
        )


class IsLabTechOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role in [User.LAB_TECHNICIAN, User.ADMIN]
        )
