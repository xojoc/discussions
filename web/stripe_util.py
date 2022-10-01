import stripe
from web import models
from django.conf import settings
import logging
from celery import shared_task
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@shared_task(
    ignore_result=True,
)
def create_customer(user_pk):
    user = models.CustomUser.objects.get(pk=user_pk)
    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        response = stripe.Customer.create(
            description=f"Created from discu.eu ({user.pk})",
            email=user.email,
            metadata={
                "username": user.username,
                "complete_name": user.complete_name,
                "user_pk": user.pk,
            },
            idempotency_key=f"{user_pk}",
        )
    except Exception as e:
        logger.error(f"stripe create_customer: {e}")
        return

    user.stripe_customer_id = response.stripe_id
    user.save()


@shared_task(
    ignore_result=True,
)
def update_customer(user_pk):
    user = models.CustomUser.objects.get(pk=user_pk)
    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        stripe.Customer.modify(
            user.stripe_customer_id,
            email=user.email,
            metadata={
                "username": user.username,
                "complete_name": user.complete_name,
                "user_pk": user.pk,
            },
        )
    except Exception as e:
        logger.error(f"stripe update_customer: {e}")
        return


@receiver(post_save, sender=models.CustomUser)
def process_customuser(sender, instance, created, **kwargs):
    if created or not instance.stripe_customer_id:
        create_customer.delay(instance.pk)
    else:
        update_customer.delay(instance.pk)
