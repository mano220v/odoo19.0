# Store preparation and reference analysis

## Reference addon reviewed

`../ow_premium_login/__manifest__.py` and `../ow_premium_login/static/description/index.html` were reviewed in the supplied Odoo 19 addons folder. Publication status was provided by the user; no independent store listing verification was performed.

The reference manifest uses an Odoo 19 version, Odoo Wings author and Apps author-page URL, `vsmanoj144@gmail.com` support, `OPL-1`, a commercial price, a `web` dependency, explicit XML data and frontend/backend asset bundles. Its `images` array references its marketing banner, icon and screenshots. `installable` is true and `application` is false.

The reference description is a standalone HTML document with `oe_container` / `oe_row` wrappers, inline styling, a hero, badges, feature blocks, screenshots, setup instructions and technical details. This is the local convention used for the new addon.

## New addon decisions

- Technical name: `ow_premium_backend`; current version: `19.0.1.2.0`.
- Odoo Wings branding and support details retained.
- OPL-1 license with LICENSE and COPYRIGHT files.
- Proposed price: USD 29.00. The commercial price needs the publisher's review.
- `Themes/Backend` category; `application=True` because Appearance Studio is a top-level app.
- `web` dependency only. Backend assets contain the service, Owl UI, templates and SCSS.
- No business models, Python dependency, security access CSV or business-record migrations are needed.
- The menu is restricted to internal users through `base.group_user`.
- The description uses local image files and inline styling, with no scripts or CDN.
- Store artwork and panel previews are explicitly labeled illustrations. Actual installation screenshots should be captured before submitting if required by the store review.

## Delivery verification

Passed: Python manifest parsing, existence of all manifest data/assets/images, XML parsing, JavaScript syntax, preference normalization/fallback checks, local description image references and standalone libsass compilation. These checks do not establish successful Odoo installation or browser rendering. Live installation was skipped at the user's request; no existing database was changed. See the 1.2 notes below for isolated browser validation.

Before submission, install the addon on Odoo 19 and complete the acceptance checks in README.md, inspect the browser console, confirm the price/support details, and review the rendered Apps description. Submit the addon through your usual Apps publishing workflow. The module has not been uploaded or published by this task.

## Premium appearance update

The 1.1 release adds 12 paired-color palettes, five presets, surface/navigation/backdrop controls, text sizing, striped rows, focus glow and configurable CSS animations. The same per-user storage key is retained with normalization for all new options. The store description and original illustrative artwork have been refreshed. No Odoo installation was performed for the 1.1 release.

## Appearance Studio 1.2

Adds custom gradient colors with white-text contrast correction, eight named themes, validated settings transfer, 20-step appearance undo, three field finishes, table/card accent choices, form width, font stacks, depth/glow sliders and optional button sheen. Controls are grouped into Design, Layout, Effects and Library. New preference defaults preserve older saved options. The reusable `tools/verify_theme.mjs` checks core behavior without a database. A local Chromium harness renders the actual Owl studio with mocked Odoo services; it does not establish full Odoo integration compatibility.

The 1.2 isolated Chromium checks passed: Owl mounting with no page errors, Design/Layout/Effects/Library interactions, profile creation, export/import (including invalid input), custom colors, presets, undo, interactive preview inputs, reduced-motion behavior, dark mode and no horizontal page overflow at 390px. Store captures `studio_preview.png` and `studio_dark.png` are labeled isolated previews.
