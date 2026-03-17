from contact.models import ContactMessage
from pgs.models import Booking, PgListing, SavedPg, VisitRequest


def booking_counts(request):
    """Inject pending and confirmed booking counts for the authenticated user."""
    pending = 0
    confirmed = 0
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        pending = Booking.objects.filter(tenant=user, status__in=['pending', 'pending_payment_review']).count()
        confirmed = Booking.objects.filter(tenant=user, status='confirmed').count()
    dashboard_metrics = {
        'total_listings': PgListing.objects.filter(owner__is_owner=True).count(),
        'available_listings': PgListing.objects.filter(owner__is_owner=True, is_available=True).count(),
        'pending_bookings': Booking.objects.filter(status__in=['pending', 'pending_payment_review']).count(),
        'confirmed_bookings': Booking.objects.filter(status='confirmed').count(),
        'unread_contact_messages': ContactMessage.objects.filter(is_read=False).count(),
        'saved_pg_count': SavedPg.objects.filter(user=user).count() if user and user.is_authenticated else 0,
        'visit_request_count': VisitRequest.objects.filter(user=user, status__in=['visit_requested', 'visit_confirmed']).count() if user and user.is_authenticated else 0,
    }
    return {
        'pending_bookings_count': pending,
        'confirmed_bookings_count': confirmed,
        'dashboard_metrics': dashboard_metrics,
    }
