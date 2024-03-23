import gzip
import io
import pprint

import httpx
import puremagic
from django.conf import settings
from django.utils import timezone

from camp.engine import loader

from .models import Ruleset

_GITHUB_API_VERSION = "2022-11-28"
_USER_AGENT = "User-Agent"
_DEFAULT_USER_AGENT = "kw/camp"

_AUTH_HEADER = "Authorization"
_GITHUB_HEADER = "X-GitHub-Api-Version"

_ACCEPT = "Accept"
_GITHUB_JSON = "application/vnd.github.raw+json"
_OCTET_STREAM = "application/octet-stream"

_GITHUB_API_BASE = "https://api.github.com/"


def fetch_ruleset(ruleset: Ruleset):
    if not ruleset.remote_url:
        return

    ruleset.remote_last_attempt = timezone.now()

    headers = {
        _USER_AGENT: getattr(settings, "RULESET_USER_AGENT", _DEFAULT_USER_AGENT),
        _ACCEPT: _OCTET_STREAM,
    }
    if ruleset.remote_token:
        headers[_AUTH_HEADER] = f"Bearer {ruleset.remote_token}"

    if ruleset.remote_url.startswith(_GITHUB_API_BASE):
        headers[_GITHUB_HEADER] = _GITHUB_API_VERSION
        headers[_ACCEPT] = _GITHUB_JSON

    response = httpx.get(ruleset.remote_url, headers=headers, follow_redirects=True)
    if not response.is_success:
        ruleset.remote_error = f"HTTP {response.status_code}: {response.reason_phrase}\n\n{response.content}"
        ruleset.remote_ok = False
        return

    data = response.content
    try:
        types = {m.extension for m in puremagic.magic_string(data)}
    except Exception:
        types = set()

    stream = io.BytesIO(data)
    if ".gz" in types:
        stream = gzip.open(stream, mode="rt")

    json_data = stream.read()
    try:
        parsed = loader.deserialize_ruleset(json_data)
    except Exception as exc:
        # Data doesn't parse.
        ruleset.remote_error = str(exc)
        ruleset.remote_ok = False
        return

    # Data parses, but isn't valid somehow.

    if parsed.bad_defs:
        ruleset.remote_error = pprint.pformat(parsed.bad_defs)
        ruleset.remote_ok = False
        return

    # Data ok, but not changed.
    if json_data == ruleset.remote_data:
        return

    # Success! Store the data.
    ruleset.remote_data = json_data
    ruleset.remote_last_updated = ruleset.remote_last_attempt
    ruleset.remote_error = ""
    ruleset.remote_ok = True
