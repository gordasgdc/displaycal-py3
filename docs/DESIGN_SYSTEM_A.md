# Visual system «Foaia de probă» (proof sheet)

The application, the PDF guides and the public pages share one look: a colour
proof checked in a D50 viewing booth. Paper, ink, process-colour control strips,
crop and registration marks, mono "slug" lines. Code: `DisplayCAL/ui/design_a.py`
(tokens, fonts, application style sheet, small widgets); web/PDF:
`docs/_site_src/`.

## Rules that never change

- **Measurement is untouched.** No colour, size, position, timing, display path
  or calculation of the patch window changes with the design. No decoration,
  animation, transparency or overlay is ever drawn over or beside a patch while
  measuring.
- **Text is never made smaller to fit.** At Large / Very large the layout
  re-flows or scrolls. The brand header has a fixed height; the room goes to
  the content.
- **No colour without a job.** Ink carries actions and structure; process
  colours (C M Y K R G B) are data and the control strip; status text uses the
  dedicated `ok / warn / bad` colours (AA on paper).

## Tokens

| Token | Light | Dark |
|---|---|---|
| booth (surround) | `#b3b5b8` | `#26272a` |
| sheet (paper) | `#f6f6f4` | `#1b1c1f` |
| inset (fields) | `#fdfdfc` | `#111214` |
| ink / rule | `#16171a` | `#eceef2` |
| ink 2 (secondary text) | `#4a4c52` | `#a9adb6` |
| ok / warn / bad (text) | `#0b7a45` / `#8a5b00` / `#b3121f` | `#4cc38a` / `#f0b44c` / `#ff6b6b` |
| focus ring | `#2e3192` | `#8fa6ff` |
| primary button | black patch | light patch |

Process colours: C `#00a3e0`, M `#d4147a`, Y `#ffd400`, K `#16171a`,
R `#e8312f`, G `#00a651`, B `#2e3192`. The control strip
(`design_a.STRIP`) is the same 32 patches in the app, the PDFs and the site.

## Type

- **Archivo** (variable): headings 800, body 400, buttons 700.
- **B612 Mono**: slug lines and field names — upper-case, letter-spaced 105 %,
  never below 11 px / 7.8 pt.
- Both fonts are SIL OFL 1.1, bundled unmodified in `DisplayCAL/theme/fonts/`
  (see `NOTICE.txt`).

## Components (app)

- **Header** (`HeaderBanner`): slug line (name · version · build · GPLv3),
  symbol + wordmark underlined C-M-Y-K, tagline, control strip.
- **Steps** (`guide_panel._Rail`): five cells between two rules; the current
  step is a black (dark: light) patch, finished steps carry a tick in a
  registration circle; when names do not fit, every cell shrinks to its number.
- **Page head**: large numeral + title + 2 px ink rule. **Section head**: mono
  slug over a hairline. **Field name**: mono slug.
- **Buttons**: square; secondary = outline, primary = patch; focus = 2 px blue.
- **Figures** (`FigureFrame`, placement player): a print on its own paper with
  a 1 px rule and two registration targets; identical in light and dark.
- Probe drawings are generic (no maker's design, logo or model).

## Screens covered

Guided flow: 1 monitor and instrument · 2 goal · 3 preparation and probe
placement · 4 measurement plan and start · 5 installation and verification.
Then: advanced tabs (display and instrument, calibration, profiling, 3D LUT,
verification), progress / cancel / recovery / errors, results and profile
install, diagnostic / support / update, and the auxiliary tools.
