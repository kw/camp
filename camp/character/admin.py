from django.contrib import admin

from . import models


@admin.register(models.Character)
class CharacterAdmin(admin.ModelAdmin):
    pass


class UndoStackEntryAdmin(admin.TabularInline):
    model = models.UndoStackEntry
    extra = 0


@admin.register(models.Sheet)
class SheetAdmin(admin.ModelAdmin):
    list_filter = ("character", "ruleset", "primary")
    inlines = [UndoStackEntryAdmin]
