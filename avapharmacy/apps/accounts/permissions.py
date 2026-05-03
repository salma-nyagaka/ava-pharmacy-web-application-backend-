"""
Custom DRF permission classes for role-based access control.

All permission classes check that the requesting user is authenticated and
carries the required role before granting access.
"""
from rest_framework.permissions import BasePermission
from .models import User

# Roles that represent internal pharmacy staff (non-customer facing)
INTERNAL_STAFF_ROLES = {
    User.ADMIN,
    User.PHARMACIST,
    User.LAB_TECHNICIAN,
    User.INVENTORY_STAFF,
}


class IsAdminUser(BasePermission):
    """Allow access only to users with the 'admin' role."""

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role == User.ADMIN
        )


class IsAdminOrSelf(BasePermission):
    """Allow object-level access to admins or the user themselves."""

    def has_object_permission(self, request, view, obj):
        return request.user.role == User.ADMIN or obj == request.user


class IsPharmacist(BasePermission):
    """Allow access only to users with the 'pharmacist' role."""

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role == User.PHARMACIST
            and request.user.is_active
            and request.user.status == User.STATUS_ACTIVE
        )


class IsPrescriptionReviewPharmacist(IsPharmacist):
    """Allow only active pharmacists granted prescription review permission."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        profile = getattr(request.user, 'pharmacist', None)
        return bool(
            profile
            and profile.has_permission(profile.PERMISSION_PRESCRIPTION_REVIEW)
        )


class IsPharmacistOrAdmin(BasePermission):
    """Allow access to pharmacists and admins."""

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role in [User.PHARMACIST, User.ADMIN]
            and request.user.is_active
            and request.user.status == User.STATUS_ACTIVE
        )


class IsDoctor(BasePermission):
    """Allow access to users with the 'doctor' or 'pediatrician' role."""

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role in [User.DOCTOR, User.PEDIATRICIAN]
        )


class IsDoctorOrAdmin(BasePermission):
    """Allow access to doctors, pediatricians, and admins."""

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role in [User.DOCTOR, User.PEDIATRICIAN, User.ADMIN]
        )


class IsLabTechOrAdmin(BasePermission):
    """Allow access to lab technicians and admins."""

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role in [User.LAB_TECHNICIAN, User.ADMIN]
        )


class IsLabPartner(BasePermission):
    """Allow access only to verified lab partner accounts."""

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role == User.LAB_PARTNER
        )


class IsLabPartnerOrAdmin(BasePermission):
    """Allow access to lab partners and admins."""

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role in [User.LAB_PARTNER, User.ADMIN]
        )


class IsStaffUser(BasePermission):
    """Allow access to any internal staff role (admin, pharmacist, lab tech, inventory)."""

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role in INTERNAL_STAFF_ROLES
        )


class IsAdminOrInventoryStaff(BasePermission):
    """Allow access to admins and inventory staff."""

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role in [User.ADMIN, User.INVENTORY_STAFF]
        )
