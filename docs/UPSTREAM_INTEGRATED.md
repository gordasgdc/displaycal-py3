# Upstream contributions integrated selectively

DisplayCAL-CG follows https://github.com/eoyilmaz/displaycal-py3 (a community
continuation of DisplayCAL by Florian Höch). Open upstream pull requests are
reviewed and, when useful and safe, applied as separate commits that keep the
original author. They are contributions to a GPL-3.0-or-later project and stay
under that licence. Nothing here rewrites upstream history; if upstream merges
the same change, the patches are identical and drop out on the next sync.

| Upstream PR | Author | Change | Applied |
|---|---|---|---|
| [#973](https://github.com/eoyilmaz/displaycal-py3/pull/973) | Åsmund Hjulstad | `open(path, encoding="utf8")` in `ccmx.py` (fixes colorimeter-correction import on newer Python) | yes |
| [#977](https://github.com/eoyilmaz/displaycal-py3/pull/977) | Xare123 | Retry ICC reads after transient profile-loader failures (Windows) | yes |
| [#982](https://github.com/eoyilmaz/displaycal-py3/pull/982) | mkiera | Scripting host `KeyError` when a client disconnects mid-response | yes |
| [#988](https://github.com/eoyilmaz/displaycal-py3/pull/988) | nick | madTPG class references and fragmented TCP replies (code and tests; the first commit of the PR, which only replaces test fixtures, conflicts with the current tree and was not applied) | partly |
| [#974](https://github.com/eoyilmaz/displaycal-py3/pull/974) | Åsmund Hjulstad | colord installation on Wayland | no (Linux only; not shipped) |

Reviewed 2026-10-19 against `upstream/develop` at `06317b85`.
