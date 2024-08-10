import os.path
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import models
from django.utils.translation import gettext_lazy as _
from PIL import Image

# Create your models here.


class UserProfile(models.Model):
    GENDER_CHOICES = [
        ("Male", _("Male")),
        ("Female", _("Female")),
        ("Other", _("Other")),
    ]
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="Profile", null=True, blank=True
    )
    first_name = models.CharField(max_length=64)
    middle_name = models.CharField(max_length=64, blank=True, null=True)
    last_name = models.CharField(max_length=64)
    gender = models.CharField(max_length=15, default="Male", choices=GENDER_CHOICES)
    email = models.CharField(max_length=64)
    phone = models.CharField(max_length=64, blank=True, null=True)
    office_number = models.CharField(max_length=64, blank=True, null=True)
    skype = models.CharField(max_length=64, blank=True, null=True)
    address = models.CharField(max_length=500, blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    image = models.ImageField(upload_to="upload/profile/", null=True, blank=True)
    thumbnail = models.ImageField(
        upload_to="upload/profile/", editable=False, null=True, blank=True
    )
    date_created = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    date_modified = models.DateTimeField(auto_now=True, blank=True, null=True)
    objects = models.Manager()

    def make_thumbnail(self):
        try:
            image = Image.open(self.image)
            image.thumbnail((200, 150), Image.ANTIALIAS)
            thumb_name, thumb_extension = os.path.splitext(self.image.name)
            thumb_extension = thumb_extension.lower()
            thumb_filename = thumb_name + "_thumb" + thumb_extension
            if thumb_extension in [".jpg", ".jpeg"]:
                FTYPE = "JPEG"
            elif thumb_extension == ".gif":
                FTYPE = "GIF"
            elif thumb_extension == ".png":
                FTYPE = "PNG"
            else:
                return False  # Unrecognized file type
            # Save thumbnail to in-memory file as StringIO
            temp_thumb = BytesIO()
            image.save(temp_thumb, FTYPE)
            temp_thumb.seek(0)
            # set save=False, otherwise it will run in an infinite loop
            self.thumbnail.save(
                thumb_filename, ContentFile(temp_thumb.read()), save=False
            )
            temp_thumb.close()
            return True
        except:
            pass

    def save(self, *args, **kwargs):
        try:
            self.make_thumbnail()
            super(UserProfile, self).save(*args, **kwargs)
        except:
            super(UserProfile, self).save(*args, **kwargs)

    def __str__(self):
        return self.user.username
