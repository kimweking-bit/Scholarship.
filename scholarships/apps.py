import sys

from django import VERSION as DJANGO_VERSION
from django.apps import AppConfig


def _patch_django_template_context_copy() -> None:
    """
    Work around Django's BaseContext.__copy__ bug on Python 3.14.

    Django versions before 5.2.8 use copy(super()) here, which started failing
    once ``super`` objects became copyable on Python 3.14.
    """
    if sys.version_info < (3, 14):
        return
    if DJANGO_VERSION >= (5, 2, 8):
        return

    from django.template.context import BaseContext

    if getattr(BaseContext.__copy__, "__module__", "") == __name__:
        return

    def _base_context_copy(self):
        duplicate = object.__new__(self.__class__)
        duplicate.__dict__ = self.__dict__.copy()
        duplicate.dicts = self.dicts[:]
        return duplicate

    BaseContext.__copy__ = _base_context_copy


class ScholarshipsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "scholarships"

    def ready(self) -> None:
        _patch_django_template_context_copy()
