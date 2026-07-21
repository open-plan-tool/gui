from django.db import migrations


def forwards(apps, schema_editor):
    """Re-copy conversion_factor_to_electricity/heat from the base Asset fields.

    0031 parsed efficiency/efficiency_multiple down to a float, silently
    dropping non-constant timeseries values. Now that both fields are
    TextField (0032, 0033) they can hold the same scalar-or-timeseries text
    representation as their Asset source fields, so a straight copy is enough
    and preserves timeseries that the original migration lost.
    """
    CHP = apps.get_model("projects", "CHP")
    for chp in CHP.objects.all():
        CHP.objects.filter(pk=chp.pk).update(
            conversion_factor_to_electricity=chp.efficiency,
            conversion_factor_to_heat=chp.efficiency_multiple,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0033_alter_chp_conversion_factor_to_heat"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
