# 04 · 3D viewer and sharing it by link

## The viewer

`viewer/index.html` is a single page: three.js 0.170 from the jsDelivr CDN,
GLTFLoader, orbit controls, studio lighting (key/fill/front/rim/back lights + room
environment), neutral tone mapping, and a soft ground shadow.

- **Camera presets:** `VIEWS` (front, 3/4, side, back, back print, front print, sleeve,
  pocket). Each has a nav button; `?view=back` opens on that view.
- **Model location:** it tries `?model=…`, then `oatmeal_hoodie_realistic.glb` next to
  the page, then `../model/oatmeal_hoodie_realistic.glb`, then a gzip+base64 `.txt`.
- **Exposure:** `renderer.toneMappingExposure` (0.58). Re-check colour if you change it.
- Transparent print decals don't cast shadows (otherwise their rectangle would).

To run it locally, serve the repo root over http (the model won't load from `file://`),
then open `http://localhost:8000/viewer/`:

```bash
python -m http.server 8000
```

## Sharing a link (what we used)

We published the viewer as a **Claude artifact**:
https://claude.ai/artifact/3hkLLwRwZE3gaSFJWwWvRm. The owner sets who can open it
(Share → anyone with the link).

The artifact host has rules a normal web server doesn't, so the page is packaged first:

```bash
python tools/pack_viewer_for_artifact.py
```

This writes `dist/artifact/gik_hoodie_viewer.html` + `hoodie_model.glb.gz.b64.txt`:
- `.glb` is not a served file type, so the model is gzipped and base64-encoded into a
  `.txt` (13.5 MB, under the ~16 MB per-file limit). The viewer unpacks it with the
  browser's `DecompressionStream`.
- The page's `<html>/<head>/<body>` tags are stripped (the host adds its own), and
  safe-area padding is added for phones.

To update the published page, ask Claude to republish `dist/artifact/gik_hoodie_viewer.html`
with the `.txt` file to the same artifact URL.

## Why not Google Drive?

Drive shows an `.html` file's source code instead of running it, and the 3D model is
too big to send through the Drive connector. We put a short Google Doc on Drive that
links to the viewer instead. A GitHub Pages site from this repo would also work as a
public host.
