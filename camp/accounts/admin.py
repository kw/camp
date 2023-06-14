from django.contrib import admin

from . import models

# admin.site.register(Membership)


@admin.register(models.Membership)
class MembershipAdmin(admin.ModelAdmin):
    pass
