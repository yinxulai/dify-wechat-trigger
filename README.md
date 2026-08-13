# WeCom AI Bot Trigger

This Dify trigger receives encrypted URL callbacks (short-connection/Webhook)
from WeCom AI bots and dispatches incoming messages to a workflow. It does not
support the WeCom long-connection mode.

## Configuration

Create one trigger provider credential in the Dify UI. Add one value to each
repeated robot field: `Robot IDs`, `Robot Names`, `AI Bot IDs`, `Callback
Tokens`, and `Encoding AES Keys`. Values are paired by position, so the first
value in every field describes the first robot, the second value describes the
second robot, and so on.

Create a subscription, select one robot, and copy the generated callback URL to
that robot's HTTPS URL callback configuration in WeCom. Choose API mode with
"Set message receiving URL" rather than long-connection mode. This first
version uses manual callback configuration and does not create an outbound
webhook.

The callback validates the signature, decrypts the request, checks `aibotid`,
and exposes the decrypted message as the `message_received` event payload.

## Development

Run the local checks with Python 3.12:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python scripts/version.py check
python -m compileall -q provider events main.py
python -m pytest -q
```

Pull requests and pushes to `main` run the same checks and build a downloadable
`.difypkg` artifact with the official Dify Plugin CLI.

## Release

Run the `Release` workflow manually from GitHub Actions and provide a version in
`MAJOR.MINOR.PATCH` format. The workflow requires a version greater than the
current one, updates `pyproject.toml` and the top-level plugin version in
`manifest.yaml`, runs all checks, packages the plugin, commits the version change
to `main`, creates a matching `vMAJOR.MINOR.PATCH` tag, and publishes a GitHub
Release containing the `.difypkg` file. The `meta.version` field is the manifest
schema version and remains independent from the plugin release version.

Publishing a GitHub Release from an existing `vMAJOR.MINOR.PATCH` tag also
triggers the `Package Published Release` workflow. It verifies that the tag
matches the plugin version, runs the checks, builds the `.difypkg`, and uploads
it to that Release.

The repository must allow GitHub Actions to write contents, and branch rules for
`main` must permit the release workflow's version commit.
