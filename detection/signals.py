from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import ProfileInformation

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        ProfileInformation.objects.create(user=instance)
    else:
        ProfileInformation.objects.get_or_create(user=instance)
        instance.profile.save()