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
| [Host Grotesk](https://github.com/element-type/hostgrotesk) via Fontsource | 5.3.0 | `host-grotesk-5.3.0/host-grotesk.css`, `files/host-grotesk-latin{,-ext}-wght-normal.woff2` | SIL OFL 1.1 (`LICENSE`) |
| [Atkinson Hyperlegible Mono](https://www.brailleinstitute.org/freefont/) via Fontsource | 5.3.0 | `atkinson-hyperlegible-mono-5.3.0/atkinson-hyperlegible-mono.css`, `files/atkinson-hyperlegible-mono-latin{,-ext}-wght-normal.woff2` | SIL OFL 1.1 (`LICENSE`) |

Font Awesome is only here because EasyMDE's editor toolbar renders its buttons
with it; PTVault's own icons are Lucide. Each font's CSS is Fontsource's `wght.css` with the family renamed from
`<Name> Variable` to `<Name>`, so the font tokens in `static/css/tokens.css`
pick them up unchanged. Host Grotesk is the reading face; Atkinson Hyperlegible
Mono is reserved for measured values (IPs, ports, hashes, timestamps).

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
2706b1ee4f452e744ea91f7e4908cbde9c5d35521bf5ffffc71a382a2de89613  atkinson-hyperlegible-mono-5.3.0/files/atkinson-hyperlegible-mono-latin-wght-normal.woff2
3fa1fa7e990377c87018d62f356cc42b8db39fd88cee5724431e9f0d63b7f32f  atkinson-hyperlegible-mono-5.3.0/files/atkinson-hyperlegible-mono-latin-ext-wght-normal.woff2
c53a3771287f883545c195c56521c8f10e3f3d8ab1551b5862d3342089211aab  atkinson-hyperlegible-mono-5.3.0/atkinson-hyperlegible-mono.css
f2094bbf6141b359722c4fe454eb6c4b0f0e42cc10cc7af921fc158fceb86539  d3-7.9.0/d3.min.js
6eee36340432776d682e7372ec4a7eb29be4fdb3ffada32c0bfa5e31a5ef34a2  easymde-2.21.0/easymde.min.css
2c06bddfd0c89176db08ccf9d42e2beaa9b4f1a4ff8fb2ec0bf1bed25ce08e05  easymde-2.21.0/easymde.min.js
799aeb25cc0373fdee0e1b1db7ad6c2f6a0e058dfadaa3379689f583213190bd  font-awesome-4.7.0/css/font-awesome.min.css
ba0c59deb5450f5cb41b3f93609ee2d0d995415877ddfa223e8a8a7533474f07  font-awesome-4.7.0/fonts/fontawesome-webfont.woff
2adefcbc041e7d18fcf2d417879dc5a09997aa64d675b7a3c4b6ce33da13f3fe  font-awesome-4.7.0/fonts/fontawesome-webfont.woff2
194782c85ee857df4373f6c246e4da9c0ba3cccf85756f6d26e1e78de3479495  host-grotesk-5.3.0/files/host-grotesk-latin-ext-wght-normal.woff2
ce9c9db8a488852eb7e4a52f51fd8ce0c93ef61a8d3bfa054b509ec92958dcfe  host-grotesk-5.3.0/files/host-grotesk-latin-wght-normal.woff2
8f94955fbb773c06dbbfc5dc6c634ce3f46db0571ef34b00ea8deac0ff785c39  host-grotesk-5.3.0/host-grotesk.css
89520d7fe5af181b5d32ecee6a41e5c2c01a45540536c322f4970626b7267633  lucide-1.59.0/lucide.min.js
b82b9334406d8bdd16b6236c08de1cb65b2a859873ca9503d9cc0b292ca3c12a  marked-18.1.1/marked.umd.js
```
