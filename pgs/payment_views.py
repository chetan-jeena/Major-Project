"""
Direct UPI Payment Integration Views for PG Finder

Simplified payment system that uses a direct UPI ID without payment gateway complexity.
Users scan QR code or manually enter UPI ID to make payments.
"""

import qrcode
from io import BytesIO
import base64
import logging
from uuid import uuid4
from django.http import JsonResponse
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods

from .models import Booking, Payment
from users.models import Notification

logger = logging.getLogger(__name__)

# Your UPI ID
YOUR_UPI_ID = "9027448046@axl"


# ============================================================================
# UPI Payment Helper Functions
# ============================================================================

def generate_upi_link(upi_id, amount, name="PG Finder"):
    """
    Generate UPI deep link for payment
    Format: upi://pay?pa=upi_id&pn=name&am=amount
    """
    return f"upi://pay?pa={upi_id}&pn={name}&am={amount}"


def generate_qr_code(data):
    """
    Generate QR code from data and return as base64
    """
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to bytes
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        # Encode to base64
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_base64}"
    except Exception as e:
        logger.error(f"QR code generation error: {str(e)}")
        return None


# ============================================================================
# Payment Views
# ============================================================================

@login_required(login_url='user_login')
@require_http_methods(['GET', 'POST'])
def initiate_payment(request, booking_id):
    """
    Initiate UPI payment for a booking
    Displays QR code and UPI ID for manual payment
    """
    booking = get_object_or_404(Booking, id=booking_id, tenant=request.user)

    # Prevent double payments
    if hasattr(booking, 'payment') and booking.payment.payment_status == 'completed':
        messages.warning(request, 'Payment already completed for this booking.')
        return redirect('booking_confirmation', booking_id=booking_id)

    try:
        # Generate UPI payment link with amount
        amount = float(booking.amount)
        upi_link = generate_upi_link(YOUR_UPI_ID, amount, name=booking.pg.title[:20])

        # Generate QR code
        qr_code_base64 = generate_qr_code(upi_link)

        # Create or update Payment model
        payment, created = Payment.objects.get_or_create(
            booking=booking,
            defaults={
                'amount': booking.amount,
                'payment_status': 'pending',
                'payment_method': 'upi',
                'transaction_id': f"txn_{uuid4().hex[:12]}",
            }
        )

        if not created and payment.payment_status != 'pending':
            payment.payment_status = 'pending'
            payment.transaction_id = f"txn_{uuid4().hex[:12]}"
            payment.save()

        context = {
            'booking': booking,
            'payment': payment,
            'amount': amount,
            'upi_id': YOUR_UPI_ID,
            'qr_code': qr_code_base64,
            'payment_method': 'upi',
            'upi_link': upi_link,
        }

        return render(request, 'pgs/payment/upi_payment.html', context)

    except Exception as e:
        logger.error(f"Payment initiation error: {str(e)}")
        messages.error(request, f'Payment initiation failed: {str(e)}')
        return redirect('booking_confirmation', booking_id=booking_id)


@login_required(login_url='user_login')
@require_http_methods(['POST'])
def verify_payment(request, booking_id):
    """
    Manual payment verification
    User provides transaction ID from their bank
    """
    try:
        booking = get_object_or_404(Booking, id=booking_id, tenant=request.user)
        payment = get_object_or_404(Payment, booking=booking)

        # Get transaction ID from form
        transaction_id = request.POST.get('transaction_id', '').strip()

        if not transaction_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Please provide a transaction ID',
            }, status=400)

        # Update payment with transaction ID
        payment.transaction_id = transaction_id
        payment.payment_status = 'pending_verification'
        payment.save()

        # Update booking status to pending review
        booking.status = 'pending_payment_review'
        booking.payment_id = transaction_id
        booking.save()

        # Create notification for owner to verify
        Notification.objects.create(
            user=booking.pg.owner,
            notification_type='payment_pending_review',
            title=f'Payment Verification Required - {booking.tenant.first_name}',
            message=f'{booking.tenant.first_name} has submitted payment (Transaction ID: {transaction_id}) for {booking.pg.title}. Please verify the payment.',
            booking_id=booking_id,
            pg_id=booking.pg_id,
            user_from=booking.tenant
        )

        # Create notification for tenant
        Notification.objects.create(
            user=booking.tenant,
            notification_type='payment_submitted',
            title='Payment Submitted for Verification',
            message=f'Your payment for {booking.pg.title} has been submitted. The owner will verify it shortly.',
            booking_id=booking_id,
            pg_id=booking.pg_id
        )

        return JsonResponse({
            'status': 'success',
            'message': 'Payment submitted for verification',
            'booking_id': booking_id,
        })

    except Booking.DoesNotExist:
        logger.error(f"Booking not found: {booking_id}")
        return JsonResponse({
            'status': 'error',
            'message': 'Booking not found',
        }, status=404)
    except Payment.DoesNotExist:
        logger.error(f"Payment not found for booking: {booking_id}")
        return JsonResponse({
            'status': 'error',
            'message': 'Payment record not found',
        }, status=404)
    except Exception as e:
        logger.error(f"Payment verification error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e),
        }, status=400)


@login_required(login_url='user_login')
@require_http_methods(['POST'])
def confirm_payment(request, booking_id):
    """
    Owner confirms/approves payment (after manual verification)
    """
    booking = get_object_or_404(Booking, id=booking_id)

    # Only owner can confirm payment
    if request.user != booking.pg.owner:
        messages.error(request, 'Only the owner can confirm payments.')
        return redirect('home')

    try:
        payment = booking.payment

        if payment.payment_status != 'pending_verification':
            messages.error(request, 'Payment is not pending verification.')
            return redirect('booking_confirmation', booking_id=booking_id)

        # Mark payment as completed
        payment.payment_status = 'completed'
        payment.completed_at = timezone.now()
        payment.save()

        # Update booking status
        booking.status = 'confirmed'
        booking.payment_confirmed_date = timezone.now()
        booking.save()

        # Notify tenant
        Notification.objects.create(
            user=booking.tenant,
            notification_type='payment_success',
            title='Payment Confirmed',
            message=f'Your payment for {booking.pg.title} has been confirmed by the owner.',
            booking_id=booking_id,
            pg_id=booking.pg_id
        )

        # Notify owner
        Notification.objects.create(
            user=booking.pg.owner,
            notification_type='booking_confirmed',
            title=f'New Booking - {booking.tenant.first_name}',
            message=f'{booking.tenant.first_name} has booked {booking.pg.title} from {booking.check_in_date}.',
            booking_id=booking_id,
            pg_id=booking.pg_id,
            user_from=booking.tenant
        )

        messages.success(request, 'Payment confirmed successfully.')
        return redirect('booking_confirmation', booking_id=booking_id)

    except Payment.DoesNotExist:
        messages.error(request, 'Payment record not found.')
        return redirect('booking_confirmation', booking_id=booking_id)
    except Exception as e:
        logger.error(f"Payment confirmation error: {str(e)}")
        messages.error(request, f'Error: {str(e)}')
        return redirect('booking_confirmation', booking_id=booking_id)


@login_required(login_url='user_login')
@require_http_methods(['POST'])
def cancel_payment(request, booking_id):
    """
    Cancel a booking and payment
    """
    booking = get_object_or_404(Booking, id=booking_id, tenant=request.user)

    try:
        if hasattr(booking, 'payment'):
            booking.payment.payment_status = 'cancelled'
            booking.payment.save()

        booking.status = 'cancelled'
        booking.updated_at = timezone.now()
        booking.save()

        messages.success(request, 'Booking cancelled successfully.')
        return redirect('my_bookings_list')

    except Exception as e:
        logger.error(f"Booking cancellation error: {str(e)}")
        messages.error(request, f'Error: {str(e)}')
        return redirect('booking_confirmation', booking_id=booking_id)

