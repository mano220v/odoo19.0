# Premium User Login Security

This Odoo 19 addon adds a premium, responsive login screen with four credential modes:

- Password
- Quick PIN
- Unlock pattern
- Text lock

PIN, pattern, and text-lock values are hashed with Odoo's configured password hashing context. They are never stored as plain text. The selected method is enforced per user; selecting PIN in the browser does not create a PIN for a user who has not been configured with one.

## Setup

1. Add this repository to the Odoo `addons_path`.
2. Update the Apps list and install **Premium User Login Security**.
3. Open a user as an administrator and use the **Premium login method** section on the Security tab.
4. Select a method and set its credential. The login screen pattern is drawn by dragging across the dots. For manual setup, use node numbers in reading order (`0` to `8`), for example `0-1-4-7-8`.
5. Save the user, then hard-refresh the login page. Click Password, PIN, Pattern, or Text lock to switch modes.

The regular Odoo password remains the recovery credential and is still available from the standard Password change flow.
