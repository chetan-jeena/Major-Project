from django.urls import path

from . import views

urlpatterns = [
    path("", views.pgs, name="pgs"),
    path("about/", views.about, name="about"),
    path("search/", views.search, name="search"),
    path("pgregister/", views.pg_register, name="pg_register"),
    path("saved/", views.saved_pg_list, name="saved_pg_list"),
    path("compare/", views.compare_pgs, name="compare_pgs"),
    path("owner/reviews/", views.owner_booking_reviews, name="owner_booking_reviews"),
    path("book/<slug:pg_slug>/", views.book_pg, name="book_pg"),
    path("visit/<slug:pg_slug>/", views.request_visit, name="request_visit"),
    path("save/<slug:pg_slug>/", views.toggle_saved_pg, name="toggle_saved_pg"),
    path("booking-confirmation/<int:booking_id>/", views.booking_confirmation, name="booking_confirmation"),
    path("confirm-payment/<int:booking_id>/", views.confirm_payment, name="confirm_payment"),
    path("review-booking/<int:booking_id>/", views.review_booking, name="review_booking"),
    path("review-visit/<int:visit_request_id>/", views.review_visit_request, name="review_visit_request"),
    path("my-bookings/", views.my_bookings_list, name="my_bookings_list"),
    path("cancel-booking/<int:booking_id>/", views.cancel_booking, name="cancel_booking"),
    path("<slug:pg_slug>/", views.pg_detail, name="pg_detail"),
]
