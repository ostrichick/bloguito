# Header polish follow-up — 2026-09-27

## Scope

- Shared GeneratePress header only.
- Keep the WordPress blogname/SEO metadata unchanged.
- Render the visible title as two stable lines: `생활정보 24 |` and `정부 지원금, 절세, 복지 생활 백과`.
- Remove `사이트 소개` from the primary navigation only. The footer `/about/` link remains.

## Implementation

- `wordpress/mu-plugins/bloguito-front-end-polish.php`
  - `generate_site_title_output` wraps the brand and descriptor in separate spans.
  - Header CSS renders the title link as a vertical flex layout.
  - `wp_nav_menu_objects` filters the About item only when `theme_location=primary`.
- `wordpress/tests/front-end-polish-test.php` covers title markup, primary-menu filtering, footer-menu preservation, and header CSS registration.

## Validation

- Production PHP syntax check passed.
- `front-end-polish-test.php` passed in the production WordPress PHP container.
- Production MU plugin SHA256: `577e09e1c2b9686a77f007e7e8967d88d9ab319856627813f3d9120002165ac2`.
- WP Super Cache page cache was cleared with the plugin function after deployment; ordinary homepage HTML then showed the new title markup.
- Ordinary homepage verification: `사이트 소개` count in the primary menu = 0, total visible occurrence = 1 (footer).
- Desktop 1280×900 and mobile 390×844 screenshots confirmed the header title renders on two lines without the prior awkward wrap.
- QA screenshots are local temporary evidence under `tmp/header-polish-desktop.png` and `tmp/header-polish-mobile.png` and are not committed.
