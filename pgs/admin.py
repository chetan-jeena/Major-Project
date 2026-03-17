from django.contrib import admin

from .models import Booking, PGImage, PgListing, SavedPg, VisitRequest


@admin.register(PgListing)
class PgListingAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "owner",
        "city",
        "state",
        "price_per_month",
        "is_available",
        "available_from",
    )
    list_filter = ("city", "state", "sharing_type", "type_of_pg", "is_available")
    search_fields = ("title", "city", "state", "address", "owner__email")
    prepopulated_fields = {"slug": ("title",)}

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "owner":
            kwargs["queryset"] = db_field.related_model.objects.filter(is_owner=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(PGImage)
class PGImageAdmin(admin.ModelAdmin):
    list_display = ("pg", "uploaded_at")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "pg", "amount", "status", "booking_date", "payment_reference")
    list_filter = ("status", "booking_date")
    search_fields = ("tenant__username", "tenant__email", "pg__title", "id", "payment_reference")
    readonly_fields = ("booking_date", "qr_code")


@admin.register(SavedPg)
class SavedPgAdmin(admin.ModelAdmin):
    list_display = ("user", "pg", "created_at")
    search_fields = ("user__email", "pg__title")


@admin.register(VisitRequest)
class VisitRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "pg", "preferred_date", "status", "created_at")
    list_filter = ("status", "preferred_date", "created_at")
    search_fields = ("user__email", "pg__title", "notes")
