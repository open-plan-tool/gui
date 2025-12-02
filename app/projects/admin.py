from django.contrib import admin

# Register your models here.
from .models import *

admin.site.register(Project)
admin.site.register(EconomicData)
admin.site.register(Comment)
admin.site.register(Scenario)
admin.site.register(Asset)
admin.site.register(Bus)
admin.site.register(ConnectionLink)


class AssetTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "visibility", "name", "asset_type")
    list_filter = ("visibility", "asset_type")


admin.site.register(AssetTemplate, AssetTemplateAdmin)
