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


class RegistrationInline(admin.TabularInline):
    model = models.EventRegistration


class ReportInline(admin.TabularInline):
    model = models.EventReport


@admin.register(models.Event)
class EventAdmin(admin.ModelAdmin):
    date_hierarchy = "created_date"
    inlines = [ReportInline, RegistrationInline]


@admin.register(models.EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    date_hierarchy = "registered_date"


@admin.register(models.EventReport)
class EventReportAdmin(admin.ModelAdmin):
    pass


@admin.register(models.PlayerCampaignData)
class PlayerCampaignAdmin(admin.ModelAdmin):
    pass


@admin.register(models.Award)
class AwardAdmin(admin.ModelAdmin):
    pass
