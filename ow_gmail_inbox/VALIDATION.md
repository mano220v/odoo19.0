# Validation report

- Passed Python syntax parsing for all addon sources.
- Passed manifest metadata and asset/data/image existence checks.
- Passed XML parsing for views, settings, rules, OAuth result page and Owl templates.
- Passed standalone SCSS compilation and JavaScript syntax checks.
- Passed eight protocol tests: OAuth state identity/database/expiry, PKCE, callback/resource validation, MIME handling, text-only HTML fallback, header injection and file limits, token transport and uncertain-send error handling.
- Passed isolated Chromium tests mounting the actual Owl component with mocked Odoo services: inbox/read, escaped content, mark-read requests, reply addressing, attachment selection, failed-send content retention, successful-send UI reset, pagination, Gmail search, mobile layout and disconnect.
- Reviewed desktop and mobile UI captures. All mail content shown is fictional.
- Packaged ZIP with one top-level `ow_gmail_inbox` directory and without Python bytecode/cache files.

Not performed: installation in an Odoo database, execution of the supplied Odoo access-control test suite, live Google OAuth/refresh/revoke, or real email sending/receiving. Google project credentials and a test installation are required for those checks. No existing database or live Google account was changed.
