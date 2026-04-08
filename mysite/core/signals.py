from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Profile

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        # Creates an empty profile; you'll fill user_id later
        Profile.objects.create(user=instance, user_id=f"TEMP-{instance.id}")