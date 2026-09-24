# Premium Backend Theme — Odoo 19

A backend appearance addon from Odoo Wings. Installation activates premium styling for internal users, using Odoo's standard web components and Owl. There is no React build step, CDN, external font, or extra Python dependency.

## Install

1. Extract `ow_premium_backend.zip` into an addons directory. The directory must contain `ow_premium_backend/__manifest__.py`.
2. Include that addons directory in your Odoo 19 `addons_path`, then restart Odoo.
3. Enable developer mode, update the Apps list, search for **Premium Backend Theme**, and install.
4. Refresh the browser. Open **Appearance Studio** from the app menu, or use the paintbrush button in the navbar.

For an existing installation, update using Apps or `odoo-bin -d YOUR_DATABASE -u ow_premium_backend --stop-after-init`, then restart and refresh.

## Included

- Form sheet surfaces, groups, notebook tabs, labels, status bars, smart buttons, required and invalid inputs.
- Char, text, selection, numeric and many2one input styling; boolean accents; many2many tag spacing.
- List views (called tree views in older Odoo versions): headers, rows, selections, grouped rows and totals.
- One2many and many2many list borders, headers and spacing, including editable native tables.
- Kanban cards, group headers and quick-create containers. Native drag-and-drop behavior is retained.
- Search bars, search facets, buttons, menus and dialogs.
- Twelve gradient palettes: Indigo, Ocean, Emerald, Plum, Rose, Slate, Royal, Teal, Amber, Ruby, Sapphire and Bronze.
- Five coordinated signature presets: Aurora, Midnight, Lagoon, Sunset and Atelier. Presets change palette, mode, surface, navigation and backdrop while preserving your density and other personal options.
- Glass, elevated and clean surface finishes; gradient, midnight and surface-colored navigation.
- Aurora, mesh and plain backdrops; standard and large text sizes.
- Optional striped list rows, glowing field focus and card hover lift.
- A navbar light/dark toggle next to the paintbrush; this explicitly selects light or dark mode. Select System again in the studio to follow your device.
- Light, dark and system appearance; comfortable and compact density; rounded and square corners.
- Optional view fades, dialog entrances, card hover lift and button press feedback, with subtle/expressive timing. Animation effects respect reduced motion, and hover lifts only run on devices with a fine pointer.
- Custom primary/secondary gradient colors, with automatic darkening for readable white button text.
- Personal theme library with up to eight named themes; settings export/import between browsers.
- Undo for up to 20 appearance changes in the current page session.
- Soft, outlined or underline field finishes; tinted table headers; top, side or neutral card borders.
- Standard or wide form canvas and system, humanist or geometric font stacks using installed fonts.
- Adjustable surface shadow depth and focus glow intensity.
- Optional primary-button light sweep and form accent ribbon.
- Keyboard focus outlines and reduced-motion support.
- Responsive Appearance Studio with clearly labeled illustrative form, list and kanban previews.

## Preference storage

Preferences apply immediately and are stored in browser local storage, namespaced by database and user. They are shared between tabs of the same browser. They do not synchronize to another device or browser. Restricted storage falls back to session behavior. Defaults: enabled, light, Indigo, comfortable, rounded, glass surfaces, gradient navigation, Aurora backdrop, standard text, subtle animations, hover lift and field glow enabled, striped rows disabled. Existing stored preferences remain compatible and gain defaults for new options.

Switch off **Premium styling** to return to the standard appearance for your browser user. **Reset defaults** restores the addon defaults. Uninstalling removes the assets and menu; reload open browser tabs afterward. Old preference keys may remain locally and can be removed through browser site storage.

## Use the new studio

The studio has four categories: **Design**, **Layout**, **Effects**, and **Library**. Every option applies immediately.

In Design, turn on **Custom gradient** to select two colors. Very bright colors are deepened for white text contrast; the picked values are retained in your preferences. Choosing a built-in palette or preset turns off custom colors.

In Library, name your current appearance and select **Save theme**. Select a saved theme to apply it. You can remove individual library entries. **Reset defaults** resets the active appearance but retains your library. **Undo change** restores a previous appearance, including a reset or import; it does not undo deletion of a saved theme. Undo history clears on page reload or an appearance update from another tab.

Select **Export current settings**, copy the settings text and paste it into the same field in another browser, then select **Import and apply**. Only the active appearance is exported, not your saved library, user ID or business data. Exports use a versioned JSON format, are limited to 20,000 characters and only allow supported settings. Unknown fields are discarded. Invalid documents leave the current appearance untouched.

Font choices use local font stacks; exact typefaces vary by operating system. Surface depth affects glass/elevated surfaces; the clean finish deliberately has no surface shadows. Motion off and device reduced-motion preferences disable the optional animated effects.

## Scope and compatibility

Targets Odoo 19 standard backend form, list and kanban components. Dependency: `web`. The code does not depend on Enterprise modules, but Enterprise-specific screens have not been tested. Custom widgets, custom view markup, embedded editors and other backend themes may need additional CSS. Avoid installing overlapping backend themes without testing their combined effects.

The addon does not restyle website/portal pages, POS, PDF reports, graph/pivot/calendar/Gantt-specific renderers, or every third-party widget. Existing semantic status colors and tag colors are retained. It does not replace business views or change business data or access rights.

## Version 19.0.1.2.0

Update the addon after replacing an older copy, restart Odoo and refresh the browser to load the new assets. Saved options use the same storage key and are normalized with defaults for newly introduced fields.

Glass surfaces use CSS backdrop filtering; unsupported browsers render the surface color without blur. Gradients and color mixing target current browsers. Animations use CSS and do not add a DOM observer, background timer or React dependency.

## Before publishing

The manifest uses Odoo Wings author/support conventions from the existing `ow_premium_login` addon. Proposed price: USD 29.00; license: OPL-1. Review the price and support details before publishing.

The description includes labeled design illustrations and isolated browser captures of the actual Appearance Studio component; neither is a live Odoo installation screenshot. Capture actual screenshots on your Odoo installation and replace them if desired before submitting to the Apps store. This delivery passed manifest/path checks, XML parsing, JavaScript syntax checks, combined SCSS compilation and the dependency-free checks in `tools/verify_theme.mjs`. That script covers preference migration, import validation, color contrast, saved themes, undo, persistence and storage failures. Run it with `node tools/verify_theme.mjs` from this addon directory. A local Chromium harness passed checks for the actual Owl studio: layout controls, profiles, export/import, undo, custom colors, presets, interactive sample inputs, dark mode, reduced motion and 390px mobile overflow. The harness used mocked Odoo services and minimal base styling; native business views were not mounted. Full installation and native business-view verification are still required; no live database was changed.

Recommended acceptance checks: install on a staging database; open Contacts in list/form/kanban; open an editable one2many table such as Sales order lines if Sales is installed; edit required fields and trigger validation; open relational dropdowns and dialogs; test dark/system appearance, each palette, compact density, mobile widths, keyboard navigation, reload persistence and theme disable/reset. Check the browser console for asset or Owl errors.

## Support

Odoo Wings — vsmanoj144@gmail.com
