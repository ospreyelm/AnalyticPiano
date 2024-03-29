from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.contrib.postgres.fields import JSONField
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

from apps.accounts.managers import UserManager

DEFAULT_KEYBOARD_SIZE = 49
# Supported keyboard choices
KEYBOARD_CHOICES = (
    (25, _("25")),
    (32, _("32")),
    (37, _("37")),
    (49, _("49")),
    (61, _("61")),
    (88, _("88")),
)

DEFAULT_KEYBOARD_OCTAVES_OFFSET = 0

DEFAULT_VOLUME = "mf"
# Supported volume choices
VOLUME_CHOICES = (
    ("pp", _("pp")),
    ("p", _("p")),
    ("mp", _("mp")),
    ("mf", _("mf")),
    ("f", _("f")),
    ("ff", _("ff")),
)


def get_preferences_default():
    return {
        "keyboard_size": DEFAULT_KEYBOARD_SIZE,
        "keyboard_octaves_offset": DEFAULT_KEYBOARD_OCTAVES_OFFSET,
        "volume": DEFAULT_VOLUME,
        "mute": False,
        "auto_advance": True,
        "auto_repeat": True,
        "auto_advance_delay": 2,
        "auto_repeat_delay": 2,
        "auto_sustain_duration": 20,  # tenths of a second
    }


class User(AbstractBaseUser, PermissionsMixin):
    # E-mail
    email = models.EmailField(_("Email"), unique=True)
    # Given name
    first_name = models.CharField(
        _("First Name"), max_length=32, unique=False, default="", blank=True
    )
    # Surname
    last_name = models.CharField(
        _("Last Name"), max_length=32, unique=False, default="", blank=True
    )

    preferences = JSONField(
        default=get_preferences_default, verbose_name="Preferences", blank=True
    )

    is_staff = models.BooleanField(
        _("Is Admin"),
        default=False,
        help_text=_(
            "TEMPORARY IMPORTANT NOTIFICATION:"
            "Before designating to Admin status, make sure the password IS NOT THE SAME as the raw password."
            "Designates whether the user can log into this admin site."
        ),
    )
    is_active = models.BooleanField(
        _("Is Active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )
    date_joined = models.DateTimeField(_("Date Joined"), default=timezone.now)

    objects = UserManager()

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta(AbstractBaseUser.Meta):
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ("-date_joined",)

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email).lower()

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.email}"

    def __repr__(self):
        return f"{self.first_name} {self.last_name} - {self.email}"

    def get_full_name(self):
        name_is_set = self.first_name and self.last_name
        return f"{self.first_name} {self.last_name}" if name_is_set else "[anonymous]"

    def email_user(self, subject, message, from_email=None, **kwargs):
        send_mail(subject, message, from_email, [self.email], **kwargs)

    # def send_forgotten_password(self):
    #     self.email_user(
    #         subject="Password Reminder for AnalyticPiano",
    #         message=f"Your AnalyticPiano password is: {self.raw_password}",
    #     )

    # def send_password(self):
    #     self.email_user(
    #         subject="Welcome to AnalyticPiano",
    #         message=f"Your AnalyticPiano password is: {self.raw_password}",
    #     )

    # TODO: convert these to One-to-Many fields
    # sets aren't JSON serializable, but if performance proves too poor and a 1-M field isn't practical,
    #   revert these fields back to sets and add lots of getters and setters to convert from array -> set and back

    content_permits = JSONField(
        default=list, verbose_name="Content Permits", blank=True
    )
    # list of users with permission to access the User's content

    performance_permits = JSONField(
        default=list, verbose_name="Performance Permissions", blank=True
    )
    # list of users with permission to access the User's performances

    connections_list = JSONField(
        default=list, verbose_name="Connections List", blank=True
    )

    @property
    def connections(self):
        _listed_connections = User.objects.filter(
            Q(id__in=self.connections_list)
            | Q(id__in=self.content_permits)
            | Q(id__in=self.performance_permits)
            | Q(content_permits__contains=self.id)
            | Q(performance_permits__contains=self.id)
        )
        return _listed_connections

    def toggle_content_permit(self, other_user):  # new
        if self.id == other_user.id:
            return
        second_party = int(other_user.id)
        if second_party in self.content_permits:
            self.content_permits.remove(second_party)
        else:
            self.content_permits.append(second_party)
        self.save()

    def toggle_performance_permit(self, other_user):  # new
        if self.id == other_user.id:
            return
        second_party = int(other_user.id)
        if second_party in self.performance_permits:
            self.performance_permits.remove(second_party)
        else:
            self.performance_permits.append(second_party)
        self.save()

    def pin_connection(self, other_user):  # new
        if self.id == other_user.id:
            return
        second_party = int(other_user.id)
        if second_party not in self.connections_list:
            self.connections_list.append(second_party)
        else:
            self.connections_list.remove(second_party)
            self.connections_list.append(second_party)
        self.save()

    def toggle_connection_pin(self, other_user):  # new
        if self.id == other_user.id:
            return
        second_party = int(other_user.id)
        if second_party in self.connections_list:
            self.connections_list.remove(second_party)
        else:
            self.connections_list.append(second_party)
        self.save()


class Group(models.Model):
    name = models.CharField(
        "Group name",
        max_length=128,
        # unique?
    )
    members = models.ManyToManyField(
        to=User,
        blank=True,
        related_name="participant_groups",
        verbose_name="Members",
        help_text="The users within your group. You can add users after creating the group.",
    )
    # _members = ArrayField(
    #     base_field=models.IntegerField(),
    #     default=list,
    #     verbose_name="Members",
    #     blank=True,
    # )
    manager = models.ForeignKey(
        to=User,
        related_name="managed_groups",
        on_delete=models.PROTECT,
        verbose_name="Manager",
    )

    created = models.DateTimeField("Created", auto_now_add=True)
    updated = models.DateTimeField("Updated", auto_now=True)

    class Meta:
        verbose_name = "Group"
        verbose_name_plural = "Groups"

    def __str__(self):
        return self.name

    def save(self):
        super(Group, self).save()
        return self

    # def add_members(self, new_members):
    #     for member_id in new_members:
    #         if member_id in self._members:
    #             continue
    #         self._members.append(member_id)
    #     self.save()

    # def remove_member(self, member_id):
    #     if member_id not in self._members:
    #         return
    #     self._members.pop(self._members.index(member_id))
    #     self.save()

    # @property
    # def members(self):
    #     return User.objects.filter(id__in=self._members)
