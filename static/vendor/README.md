# Vendored front-end libraries

PTVault serves every script, stylesheet and font from this folder instead of a
CDN. The app works with no internet connection (air-gapped engagements), the
Content-Security-Policy allows no third-party host, and an upstream release can
never change the app without a commit here.

| Library | Version | Files | License |
| --- | --- | --- | --- |
| [Lucide](https://lucide.dev) | 1.59.0 | `lucide-1.59.0/lucide.min.js` | ISC (`LICENSE`) |
| [EasyMDE](https://github.com/Ionaru/easy-markdown-editor) | 2.21.0 | `easymde-2.21.0/easymde.min.{js,css}` | MIT (`LICENSE`) |
| [marked](https://marked.js.org) | 18.1.1 | `marked-18.1.1/marked.umd.js` | MIT (`LICENSE`) |
| [D3](https://d3js.org) | 7.9.0 | `d3-7.9.0/d3.min.js` | ISC (`LICENSE`) |
| [Font Awesome](https://fontawesome.com/v4/) | 4.7.0 | `font-awesome-4.7.0/css/font-awesome.min.css`, `fonts/fontawesome-webfont.{woff2,woff}` | Font: SIL OFL 1.1 · CSS: MIT |
| [Inter](https://rsms.me/inter/) via Fontsource | 5.3.0 | `inter-5.3.0/inter.css`, `files/inter-*-wght-normal.woff2` | SIL OFL 1.1 (`LICENSE`) |

Font Awesome is only here because EasyMDE's editor toolbar renders its buttons
with it; PTVault's own icons are Lucide. `inter.css` is Fontsource's `wght.css`
with the family renamed from `Inter Variable` to `Inter`, so the app's font
stack picks it up unchanged.

## Updating a library

1. Pick a release that has been public for at least two weeks.
2. Download it with npm, which verifies the registry's integrity hash, into an
   empty scratch folder outside the repo:
   `npm pack <package>@<version>` then `tar -xzf <file>.tgz`.
3. Copy the files listed above into a new `<name>-<version>/` folder with the
   package's `LICENSE`, update the paths in `templates/*.html`, delete the old
   folder, and update this table and the checksums below.
4. Run the app and check every tab: a renamed Lucide icon shows up as a blank
   space, and `tests/test_security.py` fails if a template points at a CDN.

## SHA-256

```
f2094bbf6141b359722c4fe454eb6c4b0f0e42cc10cc7af921fc158fceb86539  d3-7.9.0/d3.min.js
6eee36340432776d682e7372ec4a7eb29be4fdb3ffada32c0bfa5e31a5ef34a2  easymde-2.21.0/easymde.min.css
2c06bddfd0c89176db08ccf9d42e2beaa9b4f1a4ff8fb2ec0bf1bed25ce08e05  easymde-2.21.0/easymde.min.js
799aeb25cc0373fdee0e1b1db7ad6c2f6a0e058dfadaa3379689f583213190bd  font-awesome-4.7.0/css/font-awesome.min.css
ba0c59deb5450f5cb41b3f93609ee2d0d995415877ddfa223e8a8a7533474f07  font-awesome-4.7.0/fonts/fontawesome-webfont.woff
2adefcbc041e7d18fcf2d417879dc5a09997aa64d675b7a3c4b6ce33da13f3fe  font-awesome-4.7.0/fonts/fontawesome-webfont.woff2
ca157063339ac4ad418f214f3abfed119b0798ab4d377386ce5c9e5a7a435ebd  inter-5.3.0/files/inter-cyrillic-ext-wght-normal.woff2
71d5ee93cc1e9f1d520a3a8b66456de18c7879d8df09d57fcd2eaff75fef0075  inter-5.3.0/files/inter-cyrillic-wght-normal.woff2
6e9e020a25f9b56d418f2c085b1d3c09725a4da23fe693a5b463064606732190  inter-5.3.0/files/inter-greek-ext-wght-normal.woff2
1be3448e292fbf05ffe176fe1e43f135013d50b1e7d324ad1a558f623d3bb6f6  inter-5.3.0/files/inter-greek-wght-normal.woff2
34b9c504cab7a73e37b746343a449132e56cf7b5481af2cb81dc74dcff25c956  inter-5.3.0/files/inter-latin-ext-wght-normal.woff2
3100e775e8616cd2611beecfa23a4263d7037586789b43f035236a2e6fbd4c62  inter-5.3.0/files/inter-latin-wght-normal.woff2
5c66f9e07e90c6d4ac4922cc68d60de26c17b1858e677fb5e603fce3952b3ff2  inter-5.3.0/files/inter-vietnamese-wght-normal.woff2
737c25ebf22e517553d17c3a0135db9828efca2e5e1b5de3e8bd0a9b2dfc259d  inter-5.3.0/inter.css
89520d7fe5af181b5d32ecee6a41e5c2c01a45540536c322f4970626b7267633  lucide-1.59.0/lucide.min.js
b82b9334406d8bdd16b6236c08de1cb65b2a859873ca9503d9cc0b292ca3c12a  marked-18.1.1/marked.umd.js
```
