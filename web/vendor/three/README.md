# three.js (vendored)

`three.module.js` and `three.core.js` copied unchanged from the npm package `three`
**0.186.1** (https://threejs.org), MIT licence (`LICENSE`, from the same package). Checked
byte-for-byte against `npm pack three@0.186.1`.

Used only by the 3D note highway (`web/highway3d.js`, Partitura → "Pista 3D"), which imports
them on first use — so the rest of the UI never loads them, and the app works offline and
inside the standalone `.exe` (the PyInstaller spec walks `web/`). Served by
`GET /vendor/three/{name}`, which answers these two file names and nothing else.

To update: replace both files from the same `npm pack three@<version>` and the LICENSE with it.
