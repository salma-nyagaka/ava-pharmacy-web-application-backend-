import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Pharmacist, User


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email='admin-suspend@example.com',
        password='AdminPass123!',
        first_name='Admin',
        last_name='User',
        role=User.ADMIN,
        phone='+254700009001',
    )


@pytest.fixture
def active_pharmacist(db):
    user = User.objects.create_user(
        email='suspend-pharmacist@example.com',
        password='PharmacistPass123!',
        first_name='Suspend',
        last_name='Pharmacist',
        role=User.PHARMACIST,
        phone='+254700009002',
    )
    Pharmacist.objects.create(
        user=user,
        permissions=[Pharmacist.PERMISSION_PRESCRIPTION_REVIEW],
    )
    return user


@pytest.mark.django_db
def test_admin_suspending_pharmacist_blocks_login(admin_user, active_pharmacist):
    client = APIClient()
    client.force_authenticate(admin_user)

    suspend_response = client.post(reverse('admin-user-suspend', args=[active_pharmacist.id]))
    assert suspend_response.status_code == 200

    active_pharmacist.refresh_from_db()
    assert active_pharmacist.status == User.STATUS_SUSPENDED
    assert active_pharmacist.is_active is False

    login_client = APIClient()
    login_response = login_client.post(
        reverse('login'),
        {'email': active_pharmacist.email, 'password': 'PharmacistPass123!'},
        format='json',
    )
    assert login_response.status_code in {401, 403}


@pytest.mark.django_db
def test_admin_suspending_pharmacist_blocks_existing_access_token(admin_user, active_pharmacist):
    existing_access_token = str(RefreshToken.for_user(active_pharmacist).access_token)

    admin_client = APIClient()
    admin_client.force_authenticate(admin_user)
    suspend_response = admin_client.post(reverse('admin-user-suspend', args=[active_pharmacist.id]))
    assert suspend_response.status_code == 200

    pharmacist_client = APIClient()
    pharmacist_client.credentials(HTTP_AUTHORIZATION=f'Bearer {existing_access_token}')
    me_response = pharmacist_client.get(reverse('me'))

    assert me_response.status_code == 401
    assert me_response.data['error']['message'] == 'Account suspended. Contact support.'
