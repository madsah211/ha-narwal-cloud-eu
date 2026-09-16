# How to obtain Narwal app tokens

> Treat access and refresh tokens like your account password. Use only your own
> account and devices. Delete captures, proxy certificates, and clipboard
> history when finished.

The recommended setup is **Sign in with a Narwal account** in the integration.
Use this advanced guide only for an existing token-based installation or a
region where direct account login is not supported.

## Safer test environment

Use a fresh Android emulator or disposable test device with no personal data.
Install the official Narwal Freo app only in that environment. When extraction
is complete, delete the emulator and its proxy certificate rather than
weakening the security of your everyday phone.

The app may use TLS certificate pinning. Install a debugging CA or perform any
necessary SSL unpinning only inside the disposable environment and only against
your own account and device.

## Procedure

1. Run a local HTTPS debugging proxy such as HTTP Toolkit or mitmproxy.
2. Connect the disposable Android environment and install the proxy CA.
3. Install the official Narwal Freo app and sign in to your own account.
4. Fully close and reopen the app to trigger a token refresh.
5. Find the request to
   `/user-authentication-server/v1/token/refresh`.
6. In the JSON response's `result` object, copy:
   - `token` as the **Narwal access token**;
   - `refreshToken` as the **Narwal refresh token**.
7. In Home Assistant, add Narwal Cloud EU and choose
   **Enter app tokens manually**.
8. Stop the proxy and securely delete captured responses, exported files,
   certificates, and clipboard history.

Never post these values in a GitHub issue or chat. The integration setup form is
the only appropriate place to enter them.
