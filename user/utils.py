import six
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.tokens import PasswordResetTokenGenerator


def user_authenticate(self, username=None, password=None):
    kwargs = {"email": username}
    try:
        user = authenticate(username=username, password=password)
        if user is not None:
            return user
        else:
            user = User.objects.get(**kwargs)
            if user.check_password(password):
                return user
            else:
                return None
    except User.DoesNotExist:
        return None


class TokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return (
            six.text_type(user.pk)
            + six.text_type(timestamp)
            + six.text_type(user.is_active)
        )


account_activation_token = TokenGenerator()
