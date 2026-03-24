"""
Razorpay Payment Integration Views for PG Finder

This module handles:
- Creating payment orders
- Verifying payment signatures
- Processing webhook callbacks
- Managing payment status
"""

import json
import hmac
import hashlib
from decimal import Decimal
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required
import razorpay

from .models import Booking, Payment
from users.models import Notification

# Initialize Razorpay client
razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


@login_required(login_url='user_login')
@require_http_methods(['GET', 'POST'])
def initiate_payment(request, booking_id):
    """
    Initiate Razorpay payment for a booking
    Creates Razorpay order and renders payment page
    """
    booking = get_object_or_404(Booking, id=booking_id, tenant=request.user)

    # Prevent double payments
    if hasattr(booking, 'payment') and booking.payment.payment_status == 'completed':
        messages.warning(request, 'Payment already completed for this booking.')
        return redirect('booking_confirmation', booking_id=booking_id)

    try:
        # Create Razorpay order
        razorpay_order = razorpay_client.order.create(
            {
                'amount': int(booking.amount * 100),  # Amount in paise
                'currency': 'INR',
                'receipt': f'booking_{booking.id}_{timezone.now().timestamp()}',
                'payment_capture': 1  # Auto-capture payment
            }
        )

        # Create or update Payment model
        payment, created = Payment.objects.get_or_create(
            booking=booking,
            defaults={
                'amount': booking.amount,
                'razorpay_order_id': razorpay_order['id'],
                'payment_status': 'initiated',
            }
        )

        if not created and payment.payment_status != 'initiated':
            payment.razorpay_order_id = razorpay_order['id']
            payment.payment_status = 'initiated'
            payment.save()

        context = {
            'booking': booking,
            'payment': payment,
            'razorpay_key_id': settings.RAZORPAY_KEY_ID,
            'razorpay_order_id': razorpay_order['id'],
            'amount': int(booking.amount * 100),  # In paise
            'user_email': request.user.email,
            'user_phone': request.user.phone,
            'user_name': f"{request.user.first_name} {request.user.last_name}",
        }

        return render(request, 'pgs/payment/razorpay_payment.html', context)

    except Exception as e:
        messages.error(request, f'Payment initiation failed: {str(e)}')
        return redirect('booking_confirmation', booking_id=booking_id)


@csrf_exempt
@require_http_methods(['POST'])
def verify_payment(request, booking_id):
    """
    Verify Razorpay payment signature after successful payment
    This is called from frontend after payment success
    """
    try:
        data = json.loads(request.body)
        booking = get_object_or_404(Booking, id=booking_id)
        payment = get_object_or_404(Payment, booking=booking)

        # Verify signature
        signature = data.get('razorpay_signature')
        payment_id = data.get('razorpay_payment_id')
        order_id = data.get('razorpay_order_id')

        if not verify_razorpay_signature(order_id, payment_id, signature):
            return JsonResponse({
                'status': 'error',
                'message': 'Payment verification failed',
            }, status=400)

        # Update payment record
        payment.razorpay_payment_id = payment_id
        payment.razorpay_signature = signature
        payment.payment_status = 'completed'
        payment.completed_at = timezone.now()
        payment.save()

        # Update booking status
        booking.status = 'confirmed'
        booking.payment_id = payment_id
        booking.save()

        # Create notification for user
        Notification.objects.create(
            user=booking.tenant,
            notification_type='payment_success',
            title='Payment Successful',
            message=f'Your payment of ₹{booking.amount} for {booking.pg.title} has been received.',
            booking_id=booking_id,
            pg_id=booking.pg_id
        )

        # Create notification for owner
        Notification.objects.create(
            user=booking.pg.owner,
            notification_type='booking_confirmed',
            title=f'New Booking - {booking.tenant.first_name}',
            message=f'{booking.tenant.first_name} has booked {booking.pg.title} from {booking.check_in_date}.',
            booking_id=booking_id,
            pg_id=booking.pg_id,
            user_from=booking.tenant
        )

        return JsonResponse({
            'status': 'success',
            'message': 'Payment verified successfully',
            'booking_id': booking_id,
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e),
        }, status=400)


@csrf_exempt
@require_http_methods(['POST'])
def razorpay_webhook(request):
    """
    Handle Razorpay webhook for payment events
    Processes payment.authorized, payment.failed, etc.
    """
    try:
        webhook_data = json.loads(request.body)
        event = webhook_data.get('event')
        payload = webhook_data.get('payload', {})

        # Verify webhook signature
        signature = request.META.get('HTTP_X_RAZORPAY_SIGNATURE', '')
        if not verify_webhook_signature(request.body, signature):
            return JsonResponse({'status': 'error'}, status=401)

        # Handle different payment events
        if event == 'payment.authorized':
            handle_payment_authorized(payload)
        elif event == 'payment.failed':
            handle_payment_failed(payload)
        elif event == 'order.paid':
            handle_order_paid(payload)

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


def verify_razorpay_signature(order_id, payment_id, signature):
    """
    Verify Razorpay payment signature
    Returns True if signature is valid, False otherwise
    """
    try:
        data = f'{order_id}|{payment_id}'
        generated_signature = hmac.new(
            key=settings.RAZORPAY_KEY_SECRET.encode(),
            msg=data.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        return generated_signature == signature
    except Exception:
        return False


def verify_webhook_signature(body, signature):
    """
    Verify Razorpay webhook signature
    """
    try:
        generated_signature = hmac.new(
            key=settings.RAZORPAY_KEY_SECRET.encode(),
            msg=body,
            digestmod=hashlib.sha256
        ).hexdigest()
        return generated_signature == signature
    except Exception:
        return False


def handle_payment_authorized(payload):
    """
    Handle payment.authorized event from Razorpay
    """
    payment_data = payload.get('payment', {})
    payment_id = payment_data.get('id')
    order_id = payment_data.get('order_id')

    try:
        payment = Payment.objects.get(razorpay_order_id=order_id)
        payment.razorpay_payment_id = payment_id
        payment.payment_status = 'completed'
        payment.completed_at = timezone.now()
        payment.save()

        # Update booking
        booking = payment.booking
        booking.status = 'confirmed'
        booking.payment_id = payment_id
        booking.save()
    except Payment.DoesNotExist:
        pass


def handle_payment_failed(payload):
    """
    Handle payment.failed event from Razorpay
    """
    payment_data = payload.get('payment', {})
    order_id = payment_data.get('order_id')
    error_description = payment_data.get('error_description', 'Unknown error')

    try:
        payment = Payment.objects.get(razorpay_order_id=order_id)
        payment.payment_status = 'failed'
        payment.error_message = error_description
        payment.save()

        # Create notification
        booking = payment.booking
        Notification.objects.create(
            user=booking.tenant,
            notification_type='payment_failed',
            title='Payment Failed',
            message=f'Your payment for {booking.pg.title} failed. {error_description}',
            booking_id=booking.id,
            pg_id=booking.pg_id
        )
    except Payment.DoesNotExist:
        pass


def handle_order_paid(payload):
    """
    Handle order.paid event from Razorpay
    """
    order_data = payload.get('order', {})
    order_id = order_data.get('id')

    try:
        payment = Payment.objects.get(razorpay_order_id=order_id)
        if payment.payment_status != 'completed':
            payment.payment_status = 'completed'
            payment.completed_at = timezone.now()
            payment.save()
    except Payment.DoesNotExist:
        pass


@login_required(login_url='user_login')
def payment_status(request, booking_id):
    """
    Check payment status for a booking
    """
    booking = get_object_or_404(Booking, id=booking_id, tenant=request.user)

    try:
        payment = booking.payment
        return JsonResponse({
            'status': payment.payment_status,
            'amount': str(payment.amount),
            'booking_status': booking.status,
        })
    except Payment.DoesNotExist:
        return JsonResponse({
            'status': 'not_found',
            'booking_status': booking.status,
        })


@login_required(login_url='user_login')
def refund_payment(request, booking_id):
    """
    Initiate refund for a payment
    Only booking owner can request refund
    """
    booking = get_object_or_404(Booking, id=booking_id, tenant=request.user)

    try:
        payment = booking.payment
        if payment.payment_status != 'completed':
            messages.error(request, 'Only completed payments can be refunded.')
            return redirect('booking_confirmation', booking_id=booking_id)

        # Create refund via Razorpay
        refund = razorpay_client.payment.refund(
            payment.razorpay_payment_id,
            {
                'amount': int(payment.amount * 100),
                'notes': {
                    'booking_id': str(booking_id),
                    'reason': 'User requested refund'
                }
            }
        )

        # Update payment status
        payment.payment_status = 'refunded'
        payment.save()

        # Update booking status
        booking.status = 'cancelled'
        booking.updated_at = timezone.now()
        booking.save()

        messages.success(request, f'Refund initiated. Amount: ₹{payment.amount}')
        return redirect('my_bookings_list')

    except Exception as e:
        messages.error(request, f'Refund failed: {str(e)}')
        return redirect('booking_confirmation', booking_id=booking_id)
