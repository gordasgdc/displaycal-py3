# Monitor lookup — what the two sites offer (checked 2026-10-19)

- **everymac.com** (https://everymac.com/): the page has a GET search form (`/search/search.html?q=`, free text) and the
  *Ultimate Mac Lookup* (`/ultimate-mac-lookup/?identify=<identifier>`). Checked live with `identify=Mac14%2C9`: a list of
  the Macs with that Model Identifier (two configurations of the same 14-inch model). The lookup also accepts serial
  numbers; DisplayCAL-CG builds the URL **only from a well-formed model identifier** and never from a serial number.
- **displayspecifications.com** (https://www.displayspecifications.com/): the search box is an autocomplete script that
  calls an internal endpoint. URLs that look like a search page (`/en/search?q=…`, `/en/search/…`) do not give results, so
  **no search URL is built**: the model is copied to the clipboard and the home page is opened.
- Nothing is fetched by the application; the browser does the visit. No local copy of either site's data is kept.
- ArgyllCMS `ccxxmake` documentation (https://www.argyllcms.com/doc/ccxxmake.html), read 2026-10-19: a **ccmx** is a
  correction matrix for one colorimeter + display combination, made with a reference instrument; a **ccss** is a
  calibration spectral sample of one display, for colorimeters with built-in spectral sensitivity data (e.g. i1d3).
