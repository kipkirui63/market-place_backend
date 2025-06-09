from django.contrib import admin
from .models import User, Subscription, Tool  

admin.site.register(User)
admin.site.register(Subscription)
admin.site.register(Tool)
