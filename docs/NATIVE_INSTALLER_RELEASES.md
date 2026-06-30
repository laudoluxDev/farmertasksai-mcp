# Native Installer Releases

## What Already Exists

This repository already contains native installer build machinery, but native
installers should not be advertised to customers until they are production
signed and pass OS trust checks.

- `install.py` is the terminal installer and source-mode fallback.
- `install_gui.py` is the GUI installer.
- `.github/workflows/build-release.yml` builds PyInstaller server binaries and
  GUI installers for many TasksAI verticals when a `v*` tag is pushed.
- The GitHub release process uploads the built installers as release assets.

## Current FarmerTasksAI Asset Status

FarmerTasksAI does not currently advertise native installer assets. The
customer-facing path is the GitHub manifest plus `npx @tasksai/install`.

Do not add native fallback URLs to `agent-install.json` until FarmerTasksAI has
published, signed, and verified release assets for macOS and Windows.

## Rules For Future Verticals

Do not add native fallback URLs to a vertical manifest until the release assets
exist and have been verified.

For a new vertical:

1. Add the vertical to the build matrix or create that vertical's release flow.
2. Publish a release with real Windows and macOS installer assets.
3. Verify the asset names through GitHub Releases.
4. For macOS, verify Developer ID signing, notarization, and stapling before
   adding the matching URL to `agent-install.json`.
5. For Windows, verify Authenticode signing and SmartScreen/customer launch
   behavior before adding the matching URL to `agent-install.json`.
6. Add the matching URLs to `agent-install.json`.
7. Update the vertical README to tell AI assistants whether native fallback is
   available.

Until the relevant verification is complete, the manifest should advertise only
the `npx` path for that platform.

## Security Notes

The native installer may be downloaded or launched by an AI assistant, but the
user must approve OS prompts such as Windows SmartScreen, UAC, or macOS
security dialogs.

The installer must not be described as sending the user's task content to
FarmerTasksAI servers. FarmerTasksAI servers handle authentication, credits,
catalog/search metadata, and licensed skill delivery. The user's AI assistant
or LLM performs the task work according to that provider's privacy terms.
