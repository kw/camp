from django.contrib import admin

from . import models

# Register your models here.


class RegistrationInline(admin.TabularInline):
    model = models.EventRegistration


@admin.register(models.Event)
class EventAdmin(admin.ModelAdmin):
    date_hierarchy = "created_date"
    inlines = [RegistrationInline]


@admin.register(models.EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    date_hierarchy = "registered_date"
