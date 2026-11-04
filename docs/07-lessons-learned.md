# 07 · Lessons learned

Problems we hit, and what fixed them.

| Problem | Cause | Fix / rule |
|---|---|---|
| Model looked fine, but baked shading was nearly black and needed a very high exposure | Marching-cubes faces were wound inward, so normals pointed into the garment; double-sided materials hid it | Check normals point outward (`face_normals` on the back should have z < 0). Same bug later in the cord/stitch tubes (`tube()`). |
| Draw-cords disappeared into the chest | Surface search kept stepping inward after some points converged | Step by the signed distance in both directions and stop when all points converge (`surface_front_z`) |
| Hollow hem broke into holes | Carving an inner cavity close to a surface with folds | Don't carve thin walls near displaced surfaces; keep the body solid |
| Squat, boxy first version | Proportions guessed instead of measured | Measure the reference on a pixel grid and convert with a known width |
| Print text slightly soft | Source map is 1448 px wide, enlarged to 58 cm | Get vector or high-res art from the designer |
| "Right sleeve" ambiguity | Viewer's right ≠ wearer's right | We use **wearer's right** (`SLEEVE_SIDE = -1`) and say so in the tech pack |
| Sleeve print overlapped the seam stitching | Placed too high | Keep the print centre below the bottom of the armhole seam |
| Artifact refused the `.glb` | Not a served file type | gzip + base64 into `.txt`, unpack in the browser |
| Couldn't put the viewer on Google Drive | Drive doesn't run HTML; model too big for the connector | Host the viewer elsewhere (artifact / GitHub Pages) and link to it from a Drive doc |
| Canva uploads failed with `403` | Cloud environment network policy blocked canva.com | Add `www.canva.com` to Allowed domains |
| Canva draft had an invented map, wrong date, typos | AI layout generation fills images and text itself | Replace every generated image with real files and proofread every page before sharing |
| Headless screenshots timed out | Continuous render loop in software WebGL | Viewer exposes `window.__still()` to stop the loop and return one frame |
| CDN blocked in the build container | Proxy policy | `render.js` serves three.js from `tools/node_modules` instead |
