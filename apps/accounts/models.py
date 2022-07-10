from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.contrib.postgres.fields import ArrayField, JSONField
from django.core.mail import send_mail
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.managers import UserManager
from apps.accounts.utils import generate_raw_password

# Possible Keyboard Choices
DEFAULT_KEYBOARD_SIZE = 49
KEYBOARD_CHOICES = ((25, _("25")), (32, _("32")), (37, _("37")), (49, _("49")), (61, _("61")), (88, _("88")))

DEFAULT_VOLUME = "mf"
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
        "volume": DEFAULT_VOLUME,
        "mute": False,
        "auto_advance": False,
        "auto_advance_delay": 4,
        "auto_repeat": False,
        "auto_repeat_delay": 6,
    }


class User(AbstractBaseUser, PermissionsMixin):
    # # FIXME RAW PASSWORD !!!!!!!!
    # raw_password = models.CharField(max_length=32, default=generate_raw_password,
    #                                 help_text="** Temporary field **.\n"
    #                                           "The user's password and this field are only the same for frontend users.")

    # E-mail
    email = models.EmailField(_("Email"), unique=True)
    # Given name
    first_name = models.CharField(_("First Name"), max_length=32, unique=False, default="", blank=True)
    # Surname
    last_name = models.CharField(_("Last Name"), max_length=32, unique=False, default="", blank=True)

    # FIXME remove this field after 0008 migration is applied
    _supervisors = ArrayField(base_field=models.IntegerField(), default=list, verbose_name="Supervisors", blank=True)

    SUPERVISOR_STATUS_ACCEPTED = "Accepted"
    SUPERVISOR_STATUS_DECLINED = "Declined"
    SUPERVISOR_STATUS_SUBSCRIPTION_WAIT = "Pending"
    SUPERVISOR_STATUS_INVITATION_WAIT = "Pending Invitation"
    _supervisors_dict = JSONField(default=dict, verbose_name="Supervisors", blank=True)

    # FIXME remove these fields after 0011 migration is applied
    auto_advance = models.BooleanField(default=False)
    auto_repeat = models.BooleanField(default=False)
    auto_advance_delay = models.PositiveIntegerField(default=4)
    auto_repeat_delay = models.PositiveIntegerField(default=6)

    # FIXME remove this field after 0008 migration is applied
    keyboard_size = models.IntegerField(choices=KEYBOARD_CHOICES, default=DEFAULT_KEYBOARD_SIZE)

    preferences = JSONField(default=get_preferences_default, verbose_name="Preferences", blank=True)

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
            "Designates whether this user should be treated as active. " "Unselect this instead of deleting accounts."
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

    def get_full_name(self):
        name_is_set = self.first_name and self.last_name
        return f"{self.first_name} {self.last_name}" if name_is_set else "NOT SET"

    def email_user(self, subject, message, from_email=None, **kwargs):
        send_mail(subject, message, from_email, [self.email], **kwargs)

    def send_forgotten_password(self):
        self.email_user(
            subject="Password Reminder for AnalyticPiano",
            message=f"Your AnalyticPiano password is: {self.raw_password}",
        )

    # def send_password(self):
    #     self.email_user(
    #         subject="Welcome to AnalyticPiano",
    #         message=f"Your AnalyticPiano password is: {self.raw_password}",
    #     )

    # TODO remove this in the future
    @classmethod
    def get_guest_user(cls):
        return cls.objects.filter(email="guest@analyticpiano.herokuapp.com").first()

    @property
    def supervisors(self):
        return User.objects.filter(id__in=self._supervisors_dict.keys())

    @property
    def subscribers(self):
        return User.objects.filter(_supervisors_dict__has_key=str(self.id))

    def subscribe_to(self, supervisor, status=SUPERVISOR_STATUS_SUBSCRIPTION_WAIT):
        if str(supervisor.id) in self._supervisors_dict:
            return
        self._supervisors_dict[str(supervisor.id)] = status
        self.save()

    def unsubscribe_from(self, supervisor):
        if not str(supervisor.id) in self._supervisors_dict:
            return
        del self._supervisors_dict[str(supervisor.id)]
        self.save()

    @staticmethod
    def accept_subscription(supervisor, subscriber):
        if str(supervisor.id) not in subscriber._supervisors_dict:
            return
        subscriber._supervisors_dict[str(supervisor.id)] = User.SUPERVISOR_STATUS_ACCEPTED
        subscriber.save()

    @staticmethod
    def decline_subscription(supervisor, subscriber):
        if str(supervisor.id) not in subscriber._supervisors_dict:
            return
        subscriber._supervisors_dict[str(supervisor.id)] = User.SUPERVISOR_STATUS_DECLINED
        subscriber.save()

    def is_supervisor_to(self, subscriber):
        return (
            self == subscriber
            or str(self.id) in subscriber._supervisors_dict
            and subscriber._supervisors_dict[str(self.id)] == User.SUPERVISOR_STATUS_ACCEPTED
        )

    def is_subscribed_to(self, supervisor):
        return (
            self == supervisor
            or str(supervisor.id) in self._supervisors_dict
            and self._supervisors_dict[str(supervisor.id)] == User.SUPERVISOR_STATUS_ACCEPTED
        )


class Group(models.Model):
    name = models.CharField(
        "Name",
        max_length=128,
        validators=[
            RegexValidator(
                regex="^[a-zA-Z0-9-_]+$",
                message="Use letters, numbers, underscores, or hyphens",
            )
        ],
    )
    # members = models.ManyToManyField(to=User, blank=True, verbose_name='Members')
    _members = ArrayField(base_field=models.IntegerField(), default=list, verbose_name="Members", blank=True)
    manager = models.ForeignKey(
        to=User, related_name="managed_groups", on_delete=models.PROTECT, verbose_name="Manager"
    )

    created = models.DateTimeField("Created", auto_now_add=True)
    updated = models.DateTimeField("Updated", auto_now=True)

    class Meta:
        verbose_name = "Group"
        verbose_name_plural = "Groups"

    def __str__(self):
        return self.name

    def add_members(self, new_members):
        for member_id in new_members:
            if member_id in self._members:
                continue
            self._members.append(member_id)
        self.save()

    def remove_member(self, member_id):
        if member_id not in self._members:
            return
        self._members.pop(self._members.index(member_id))
        self.save()

    @property
    def members(self):
        return User.objects.filter(id__in=self._members)
