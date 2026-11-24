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
admin.site.register(LandingMessage)
