from django.contrib import admin

from . import models


@admin.register(models.Character)
class CharacterAdmin(admin.ModelAdmin):
    pass


@admin.register(models.Sheet)
class SheetAdmin(admin.ModelAdmin):
    list_filter = ("character", "ruleset", "primary")
