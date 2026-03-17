from django.db import models
from users.models import MyUser as Users


class PgListing(models.Model):
    TYPE_CHOICES = [
        ("boys", "Boys"),
        ("girls", "Girls"),
        ("coed", "Coed"),
        ("family", "Family"),
    ]
    SHARING_CHOICES = [
        ("single", "Single"),
        ("double", "Double"),
        ("triple", "Triple"),
        ("quad", "Quad"),
    ]
    FURNISHING_CHOICES = [
        ("fully_furnished", "Fully Furnished"),
        ("semi_furnished", "Semi Furnished"),
        ("unfurnished", "Unfurnished"),
    ]

    owner = models.ForeignKey(Users, on_delete=models.CASCADE, related_name="pg_listings")
    title = models.CharField(max_length=100)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField()
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pin_code = models.CharField(max_length=10)
    price_per_month = models.DecimalField(max_digits=10, decimal_places=2)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    available_from = models.DateField()
    is_available = models.BooleanField(default=True)
    type_of_pg = models.CharField(max_length=20, blank=True, null=True, choices=TYPE_CHOICES)
    amenities = models.TextField(help_text="Comma-separated list of amenities", blank=True, null=True)
    preferred_tenants = models.CharField(
        max_length=255,
        blank=True,
        help_text="Comma-separated preferred tenant types",
    )
    furnishing_status = models.CharField(
        max_length=30,
        choices=FURNISHING_CHOICES,
        default="fully_furnished",
    )
    food_available = models.BooleanField(default=False)
    parking_available = models.BooleanField(default=False)
    wifi_available = models.BooleanField(default=False)
    rules_or_restrictions = models.TextField(blank=True)
    sharing_type = models.CharField(max_length=20, choices=SHARING_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def amenities_list(self):
        return [item.strip() for item in (self.amenities or "").split(",") if item.strip()]

    def preferred_tenants_list(self):
        return [item.strip() for item in (self.preferred_tenants or "").split(",") if item.strip()]


class PGImage(models.Model):
    pg = models.ForeignKey(PgListing, on_delete=models.CASCADE, related_name="images")
    pg_image = models.ImageField(upload_to="pg_images/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.pg.title}"


class SavedPg(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name="saved_pgs")
    pg = models.ForeignKey(PgListing, on_delete=models.CASCADE, related_name="saved_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "pg")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} saved {self.pg.title}"


class VisitRequest(models.Model):
    STATUS_CHOICES = [
        ("visit_requested", "Visit Requested"),
        ("visit_confirmed", "Visit Confirmed"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name="visit_requests")
    pg = models.ForeignKey(PgListing, on_delete=models.CASCADE, related_name="visit_requests")
    preferred_date = models.DateField()
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="visit_requested")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Visit request by {self.user.username} for {self.pg.title}"


class Booking(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending Payment"),
        ("pending_payment_review", "Pending Payment Review"),
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    ]

    tenant = models.ForeignKey(Users, on_delete=models.CASCADE, related_name="bookings")
    pg = models.ForeignKey(PgListing, on_delete=models.CASCADE, related_name="bookings")
    booking_date = models.DateTimeField(auto_now_add=True)
    check_in_date = models.DateField()
    check_out_date = models.DateField(blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="pending")
    qr_code = models.ImageField(upload_to="qr_codes/", blank=True, null=True)
    phonepe_upi = models.CharField(max_length=100, blank=True, null=True)
    payment_id = models.CharField(max_length=100, blank=True, null=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    payment_screenshot = models.ImageField(upload_to="payment_screenshots/", blank=True, null=True)
    payment_confirmed_date = models.DateTimeField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        Users,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="reviewed_bookings",
    )
    review_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-booking_date"]

    def __str__(self):
        return f"Booking by {self.tenant.username} for {self.pg.title}"
