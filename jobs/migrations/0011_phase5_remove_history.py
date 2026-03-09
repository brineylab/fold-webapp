from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0010_phase4_remove_slurm_job_id"),
    ]

    operations = [
        migrations.DeleteModel(
            name="HistoricalJob",
        ),
    ]
