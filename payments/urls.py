from django.urls import path
from . import views
from .views import cancel_subscription, my_subscriptions

urlpatterns = [
    path("register/", views.register),
    path("login/", views.login),
    path("activate/<uidb64>/<token>/", views.activate, name="activate"),
    path("stripe/create-checkout/", views.create_checkout),
    path("stripe/webhook/", views.stripe_webhook),
    path("auth/check-subscription/", views.check_subscription),
    path("agent/gateway/", views.agent_gateway),
    path("activate/<uidb64>/<token>/", views.activate, name="activate"),
    path("tools/", views.list_tools),
    path('cancel-subscription/', cancel_subscription, name='cancel-subscription'),
    path('my-subscriptions/', my_subscriptions, name='my-subscriptions'),

]
