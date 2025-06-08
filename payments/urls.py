from django.urls import path
from . import views

urlpatterns = [
    path("register/", views.register),
    path("login/", views.login),
    path("activate/<uidb64>/<token>/", views.activate, name="activate"),
    path("stripe/create-checkout/", views.create_checkout),
    path("stripe/webhook/", views.stripe_webhook),
    path("auth/check-subscription/", views.check_subscription),
    path("agent/gateway/", views.agent_gateway),
]
