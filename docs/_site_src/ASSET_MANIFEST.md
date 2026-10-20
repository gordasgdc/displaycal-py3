# Public pages — asset manifest

Source of the pages: `docs/_site_src/` (`strings.py` texts, `build_site.py` pages, `build_readme.py` READMEs).
The technical guide is generated from `docs/guides/` (the same sources as the PDF guides).

| Asset | Where it is used | Origin | Licence / terms | Status |
|---|---|---|---|---|
| Icon "B" (glossy symbol) | logo, favicon, hero badge | Procedural redraw (Python/Pillow/NumPy, scripts kept outside the repo) of the symbol of the original DisplayCAL (rounded triangle, RGB spheres, beam): geometry fitted to the silhouette of the original splash artwork, finish "B — controlled glossy" | Derived from the original DisplayCAL artwork (GPLv3 project); the original authors' credit is kept | **Candidate, not approved by the owner** |
| Screenshots labelled REAL | landing page, READMEs | Captured from the final release candidate (macOS: Apple Silicon, app extracted from the notarized .pkg and run with an isolated profile; Windows 11 VM, installer from CI), window-only captures; no file names, paths, serials or desktop visible. The real diagnostic-dialog capture shows a local path and is NOT used publicly | GPLv3 (screenshots of GPLv3 software) | Final candidate |
| Screenshots labelled DEMO | landing page, READMEs | `scripts/capture_review.py` offscreen render with simulated monitor/instrument; each image carries a band saying so | GPLv3 | Demonstration only; never presented as a measurement |
| Positioning animation | landing page | Inline SVG + CSS, schematic, drawn for this project; not a product photo | GPLv3 | Pause control, static step list, `prefers-reduced-motion` respected |
| Flow demonstration | landing page | The five demo screenshots above, stepped by a small script | GPLv3 | Play/pause, previous/next, "show all steps" static alternative, reduced motion starts paused |
| GitHub Invertocat (black, white) | star link on the page and in the READMEs | Official GitHub logo archive; see `docs/BRAND_ASSETS.md` for URL, hashes and terms | https://brand.github.com/foundations/logo — used unaltered, small, next to a text label, not as the project logo | Permitted use |
| Instrument makers' logos | — | **Not used** (no published brand terms allowing it were found; names appear as text only) | — | — |
| Typography | all pages | System font stack, no web fonts, no external requests | — | — |

No image-generation tool was available when these pages were prepared, so no generated imagery is used and no approved
material was replaced by procedural drawings. Hero art from a dedicated image tool could be proposed in parallel by the
owner's other tools; it would be added here with its source and terms before use.
