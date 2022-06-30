from django.contrib import admin

from . import models


class GameRoleInline(admin.TabularInline):
    model = models.GameRole


class ChapterRoleInline(admin.TabularInline):
    model = models.ChapterRole


@admin.register(models.Game)
class GameAdmin(admin.ModelAdmin):
    inlines = [GameRoleInline]


@admin.register(models.Chapter)
class ChapterAdmin(admin.ModelAdmin):
    inlines = [ChapterRoleInline]
