from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    phone = models.CharField(max_length=20, null=True, blank=True)
    role = models.CharField(max_length=20, default='user')
    is_active = models.BooleanField(default=False)

# models.py
class Tool(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price_id = models.CharField(max_length=200) 
    is_active = models.BooleanField(default=True)


class Subscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE)
    status = models.CharField(max_length=50)
    email = models.EmailField()
