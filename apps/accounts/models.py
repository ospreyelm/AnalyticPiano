from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.contrib.postgres.fields import ArrayField
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.managers import UserManager
from apps.accounts.utils import generate_raw_password


# Possible Keyboard Choices

KEYBOARD_CHOICES = (
    (25, _("25")),
    (32, _("32")),
    (37, _("37")),
    (49, _("49")),
    (61, _("61")),
    (88, _("88"))
)



class User(AbstractBaseUser, PermissionsMixin):
    # FIXME RAW PASSWORD !!!!!!!!
    raw_password = models.CharField(max_length=32, default=generate_raw_password,
                                    help_text="** Temporary field **.\n"
                                              "The user's password and this field are only the same for frontend users.")

    email = models.EmailField(_('Email'), unique=True)

    first_name = models.CharField(_('First Name'), max_length=32, unique=False, default="", blank=True)
    last_name = models.CharField(_('Last Name'), max_length=32, unique = False, default="", blank=True)

    keyboard_size = models.IntegerField(choices=KEYBOARD_CHOICES, default=49)   


    _supervisors = ArrayField(base_field=models.IntegerField(), default=list,
                              verbose_name='Supervisors', blank=True)
    
    is_staff = models.BooleanField(
        _('Is Admin'),
        default=False,
        help_text=_(
            'TEMPORARY IMPORTANT NOTIFICATION:'
            'Before designating to Admin status, make sure the password IS NOT THE SAME as the raw password.'
            'Designates whether the user can log into this admin site.'
        ),
    )
    is_active = models.BooleanField(
        _('Is Active'),
        default=True,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
    )
    date_joined = models.DateTimeField(_('Date Joined'), default=timezone.now)

    objects = UserManager()

    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta(AbstractBaseUser.Meta):
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ('-date_joined',)

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)

    def get_full_name(self):
        name_is_set = self.first_name and self.last_name
        return f'{self.first_name} {self.last_name}' if name_is_set else 'NOT SET'

    def email_user(self, subject, message, from_email=None, **kwargs):
        send_mail(subject, message, from_email, [self.email], **kwargs)

    def send_forgotten_password(self):
        self.email_user(
            subject='Password Reminder',
            message=f'Your password is: {self.raw_password}',
        )

    def get_keyboard_size(self):
        return self.keyboard_size

    # TODO remove this in the future
    @classmethod
    def get_guest_user(cls):
        return cls.objects.filter(email='guest@harmonylab.com').first()

    @property
    def supervisors(self):
        return User.objects.filter(id__in=self._supervisors)

    @property
    def subscribers(self):
        return User.objects.filter(_supervisors__contains=[self.id])

    def subscribe_to(self, supervisor):
        if supervisor.id in self._supervisors:
            return
        self._supervisors.append(supervisor.id)
        self.save()

    def unsubscribe_from(self, supervisor):
        if supervisor.id not in self._supervisors:
            return
        self._supervisors.remove(supervisor.id)
        self.save()

    def is_supervisor_to(self, subscriber):
        return self.subscribers.filter(id=subscriber.id).exists() or subscriber.id == self.id
