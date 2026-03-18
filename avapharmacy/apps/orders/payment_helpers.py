from django.conf import settings


def get_paybill_number():
    return str(getattr(settings, 'MPESA_PAYBILL_NUMBER', '') or '').strip()


def get_paybill_account_label():
    value = str(getattr(settings, 'MPESA_PAYBILL_ACCOUNT_LABEL', '') or '').strip()
    return value or 'Account Number'


def get_paybill_instructions():
    value = str(getattr(settings, 'MPESA_PAYBILL_INSTRUCTIONS', '') or '').strip()
    return value or 'Pay using the M-Pesa Paybill details below. We confirm the payment automatically once Safaricom sends the callback.'


def build_paybill_account_reference(order_or_order_number):
    order_number = getattr(order_or_order_number, 'order_number', order_or_order_number)
    prefix = str(getattr(settings, 'MPESA_PAYBILL_ACCOUNT_PREFIX', '') or '').strip()
    order_number = str(order_number or '').strip()
    if not order_number:
        return prefix
    return f'{prefix}{order_number}'


def strip_paybill_account_prefix(reference):
    value = str(reference or '').strip()
    prefix = str(getattr(settings, 'MPESA_PAYBILL_ACCOUNT_PREFIX', '') or '').strip()
    if prefix and value.startswith(prefix):
        return value[len(prefix):].strip()
    return value


def resolve_order_number_from_paybill_reference(reference):
    value = strip_paybill_account_prefix(reference)
    return value.strip()
