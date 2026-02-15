from django.apps import AppConfig


class JobsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "jobs"

    def ready(self) -> None:
        # Import runners so they register with the registry.
        # This keeps the runner plug-in seam simple.
        import runners.alphafold  # noqa: F401
        import runners.bindcraft  # noqa: F401
        import runners.boltz  # noqa: F401
        import runners.chai  # noqa: F401
        import runners.ligandmpnn  # noqa: F401


