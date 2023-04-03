from django.conf import settings


def pytest_configure():
    # Don't use WhiteNoise in tests.
    settings.MIDDLEWARE.remove("whitenoise.middleware.WhiteNoiseMiddleware")
