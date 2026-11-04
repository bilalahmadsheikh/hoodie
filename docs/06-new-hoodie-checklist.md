# 06 · Making a new hoodie from this repo

1. **Branch or copy the repo.** Keep this hoodie's files as a reference.

2. **Collect references** in `artwork/`: product photo(s) for shape and colour, mock-ups
   for print placement, the print artwork itself (highest resolution you can get,
   ideally vector or PNG with transparency), and any fonts (check the licence allows
   commercial use).

3. **Shape** (only if the fit differs). Measure the reference photo on a grid, convert
   pixels to metres with a known width, and update the torso/sleeve/hood/pocket numbers
   ([02-3d-model.md](02-3d-model.md)). Iterate with `QUICK=1 python build_hoodie.py`
   and quick renders.

4. **Colour.** Set `FABRIC_HEX` and friends, render, measure the median RGB against the
   reference, adjust until it matches within a few units.

5. **Prints.** Point `PRINT_SRC` / `FRONT_LINES` / `SLEEVE_TEXT` at the new artwork and
   text, set sizes and positions ([03-prints.md](03-prints.md)). Remember: `SLEEVE_SIDE = -1`
   is the **wearer's right**. Remove a print by dropping its `parts[...]` line in `main()`.

6. **Full build and check.** Run `tools/build_all.sh`, then look at every image in
   `renders/` next to the mock-ups.

7. **Rename** outputs if you want (`oatmeal_hoodie_realistic.glb` appears in
   `build_hoodie.py`, `viewer/index.html`, `tools/build_all.sh`,
   `tools/pack_viewer_for_artifact.py`).

8. **Update the tech pack** text in `production/tech_pack.html` (sizes, colours,
   placements come from the build output and `production/print_sizes.json`).

9. **Share.** Publish `dist/artifact/` as an artifact ([04](04-viewer-and-sharing.md)),
   build the Canva tech pack ([05](05-production-and-canva.md)), check every page, and send
   the maker the link + print files.

10. **Update `README.md` and `docs/README.md`** with the new hoodie's summary.
