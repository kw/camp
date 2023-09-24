from django.contrib import admin

from . import models


class GameRoleInline(admin.TabularInline):
    model = models.GameRole


class ChapterRoleInline(admin.TabularInline):
    model = models.ChapterRole


class RulesetInline(admin.TabularInline):
    model = models.Ruleset


@admin.register(models.Game)
class GameAdmin(admin.ModelAdmin):
    inlines = [GameRoleInline, RulesetInline]


@admin.register(models.Chapter)
class ChapterAdmin(admin.ModelAdmin):
    inlines = [ChapterRoleInline]


@admin.register(models.Campaign)
class CampaignAdmin(admin.ModelAdmin):
    pass
