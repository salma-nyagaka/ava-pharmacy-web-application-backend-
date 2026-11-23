from decimal import Decimal
from django.conf import settings
from django.db import transaction
from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.orders.mpesa import MpesaClient, MpesaAPIError, MpesaConfigurationError, parse_mpesa_callback
from .models import LabRequest, LabPayment



def data(payment):
    return {'id': payment.pk, 'stage': payment.stage, 'amount': str(payment.amount), 'status': payment.status, 'message': payment.last_error}


def confirm(payment):
    LabRequest.objects.select_for_update().get(pk=payment.request_id)
    if payment.status == 'succeeded':
        return
    if LabPayment.objects.filter(request=payment.request, stage=payment.stage, status='succeeded').exclude(pk=payment.pk).exists():
        raise ValidationError('This payment stage has already been settled. Contact support to reconcile this transaction.')
    payment.status = 'succeeded'
    payment.last_error = ''
    payment.save()
    if payment.stage == 'test':
        payment.request.payment_status = 'paid'
        payment.request.save(update_fields=['payment_status', 'updated_at'])


class LabPaymentCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        try:
            booking = LabRequest.objects.select_for_update().get(pk=pk, patient=request.user)
        except LabRequest.DoesNotExist:
            return Response({'detail': 'Request not found.'}, status=404)
        stage = request.data.get('stage')
        if stage not in ('collection', 'test') or booking.status == 'cancelled':
            raise ValidationError('Choose an available payment stage.')
        if stage == 'collection' and booking.channel != 'collection':
            raise ValidationError('This request does not require home collection.')
        if stage == 'test' and not booking.laboratory_id:
            raise ValidationError('The partner must select a laboratory before test payment.')
        if stage == 'test' and booking.channel == 'collection' and not booking.payments.filter(stage='collection', status='succeeded').exists():
            raise ValidationError('Pay the collection fee first.')
        existing = booking.payments.filter(stage=stage, status__in=['pending', 'succeeded']).order_by('-pk').first()
        if existing:
            return Response(data(existing))
        amount = booking.collection_fee_amount if stage == 'collection' else booking.quoted_test_price
        if amount is None or amount <= 0 or amount != amount.to_integral_value():
            raise ValidationError('A positive whole-shilling amount is required for M-Pesa.')
        callback = getattr(settings, 'LAB_MPESA_CALLBACK_URL', '')
        if not callback:
            return Response({'detail': 'Lab M-Pesa callback URL is not configured.'}, status=503)
        payment = LabPayment.objects.create(request=booking, stage=stage, amount=amount)
        try:
            _, result = MpesaClient().initiate_stk_push(payment, request.data.get('phone', booking.patient_phone), str(payment.reference)[:12], f'Lab {stage} fee', callback_url=callback)
        except (MpesaAPIError, MpesaConfigurationError) as error:
            payment.status = 'failed'; payment.last_error = str(error); payment.save()
            return Response({'detail': str(error)}, status=503)
        payment.checkout_request_id = result.get('CheckoutRequestID', '')
        payment.merchant_request_id = result.get('MerchantRequestID', '')
        if not payment.checkout_request_id or not payment.merchant_request_id:
            payment.status = 'failed'; payment.last_error = 'M-Pesa did not return a valid payment reference.'
            payment.save()
            return Response({'detail': payment.last_error}, status=502)
        payment.save()
        return Response(data(payment), status=201)


class LabPaymentSyncView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        try:
            payment = LabPayment.objects.select_for_update().select_related('request').get(pk=pk, request__patient=request.user)
        except LabPayment.DoesNotExist:
            return Response({'detail': 'Payment not found.'}, status=404)
        if payment.status == 'pending' and payment.checkout_request_id:
            try:
                result = MpesaClient().query_stk_status(payment)
            except (MpesaAPIError, MpesaConfigurationError):
                return Response(data(payment), status=202)
            code = str(result.get('ResultCode', ''))
            if code == '0':
                confirm(payment)
            elif code in ('1', '1032', '1037', '2001'):
                payment.status = 'failed'; payment.last_error = 'Payment cancelled.'; payment.save()
        return Response(data(payment))


class LabPaymentCallbackView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @transaction.atomic
    def post(self, request):
        from apps.orders.views import _trusted_mpesa_callback
        if not _trusted_mpesa_callback(request):
            return Response({'detail': 'Invalid callback authentication.'}, status=403)
        callback = parse_mpesa_callback(request.data)
        if not callback['checkout_request_id'] or not callback['merchant_request_id']:
            raise ValidationError('Incomplete payment callback.')
        payment = LabPayment.objects.select_for_update().select_related('request').filter(checkout_request_id=callback['checkout_request_id'], merchant_request_id=callback['merchant_request_id']).first()
        if not payment:
            return Response({'detail': 'Payment not found.'}, status=404)
        if payment.status == 'succeeded':
            return Response({'ResultCode': 0})
        if callback['result_code'] == '0':
            try:
                valid_amount = Decimal(str(callback['metadata'].get('Amount'))) == payment.amount
            except Exception:
                valid_amount = False
            if not valid_amount or not callback['metadata'].get('MpesaReceiptNumber'):
                raise ValidationError('Payment amount or receipt is invalid.')
            payment.receipt = callback['metadata']['MpesaReceiptNumber']
            confirm(payment)
        else:
            payment.status = 'failed'; payment.last_error = callback['result_desc']; payment.save()
        return Response({'ResultCode': 0})
