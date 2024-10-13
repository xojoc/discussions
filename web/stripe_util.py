# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import logging

import stripe
import stripe.error
from celery import shared_task
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from web import models

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
    except stripe.StripeError:
        logger.exception("stripe create_customer")
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
        _ = stripe.Customer.modify(
            user.stripe_customer_id,
            email=user.email,
            metadata={
                "username": user.username,
                "complete_name": user.complete_name,
                "user_pk": user.pk,
            },
        )
    except stripe.error.StripeError:
        logger.exception("stripe update_customer")
        return


@receiver(post_save, sender=models.CustomUser)
def process_customuser(sender, instance, created, **kwargs):
    _ = sender
    if created or not instance.stripe_customer_id:
        create_customer.delay(instance.pk)
    else:
        update_customer.delay(instance.pk)
