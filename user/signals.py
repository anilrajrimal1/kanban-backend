from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_encode

from .utils import account_activation_token


@receiver(post_save, sender=User)
def send_activation_email(sender, instance, created, **kwargs):
    if created:
        current_site = settings.BACKEND_URL
        email_subject = "User Activation Email"
        template = "new_user_email_template.html"

        email_data = {
            "user_title": instance.username.title(),
            "user": instance,
            "domain": current_site,
            "uid": urlsafe_base64_encode(force_bytes(instance.pk)),
            "token": account_activation_token.make_token(instance),
        }

        mail_to = str(instance.email)
        html_message = render_to_string(template, email_data)
        email_message = strip_tags(html_message)

        email_res = send_mail(
            email_subject,
            email_message,
            settings.EMAIL_HOST_USER,
            [
                instance.email,
            ],
            html_message=html_message,
            fail_silently=False,
        )
        email_response = (
            ", Confirm your email address.".format(mail_to)
            if email_res
            else "Email verification could not be done."
        )

        return email_response
