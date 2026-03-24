from django import forms
from .models import Payment, Booking


class RazorpayPaymentForm(forms.ModelForm):
    """
    Form for handling Razorpay payments
    This form is mainly for backend processing, frontend uses Razorpay SDK
    """
    class Meta:
        model = Payment
        fields = ('razorpay_payment_id', 'razorpay_signature')
        widgets = {
            'razorpay_payment_id': forms.HiddenInput(),
            'razorpay_signature': forms.HiddenInput(),
        }


class PaymentVerificationForm(forms.Form):
    """
    Form to verify payment signatures from Razorpay webhook
    """
    razorpay_order_id = forms.CharField(max_length=100)
    razorpay_payment_id = forms.CharField(max_length=100)
    razorpay_signature = forms.CharField(max_length=255)
