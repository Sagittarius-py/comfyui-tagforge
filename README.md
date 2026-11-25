# TagForge for ComfyUI

Tag translation, tag autocomplete and an artist list for **Anima** and **Illustrious** prompts.
No extra Python packages: it uses only what ComfyUI already ships.

## Install
1. Put this folder in `ComfyUI/custom_nodes/`.
2. Build the tag database (Danbooru public API + e621 daily export; a few minutes, ~20 MB with `--min-count 100`).
   Run it with ComfyUI's Python:
   ```
   python scripts/build_db.py --min-count 100
   ```
   Options: `--only danbooru|e621` refreshes one source; `--min-count N` skips tags with fewer posts.
   The build writes to a temporary file and swaps it in at the end, so a failed run keeps the old database.
3. Restart ComfyUI.

Without the database the nodes still work, but only syntax formatting and blocking are applied.

## Nodes
### Tag Translator (TagForge)
`text` → `text`, `report`

- **model**: output syntax.
  - `anima`: artists as `@name`, spaces instead of underscores (except `score_N`).
  - `illustrious`: artists as plain names.
- **tags_to**: output vocabulary, `danbooru` or `e621`. Translation uses tag aliases, identical names and a small manual table (`data/mapping_e621_danbooru.csv`), e.g. `anthro` ↔ `furry`, `male` ↔ `1boy`.
- **source**: input vocabulary. `auto` detects it per tag.
- Parentheses inside tag names are escaped (`pokemon \(creature\)`), because ComfyUI reads `(` as weight syntax. Weights like `(tag:1.4)` are kept.
- Plain artist names found in the database get `@` automatically for Anima.
- Sentences (6+ words or ending with a period) pass through unchanged.
- Duplicates are removed, and lines are kept.
- `report` lists unknown tags, translations, tags without an equivalent, artists and notes. Connect it to `Preview Any`.

### Artist Picker (TagForge)
`artists` → `text` formatted for the chosen model.

- **Browse artists…** opens a searchable list of Danbooru artists (100+ posts), sorted by post count, each with a link to the Danbooru profile. Click a row to append the artist.
- **random_count** > 0 picks random artists from the 2000 most popular ones whose tag existed before the model's training data ended:
  - Anima: September 2025, per its model card.
  - Illustrious: end of 2023 (trained on Danbooru2023; the card gives no exact date).

## Autocomplete
Works in every text field in ComfyUI.

- Suggestions appear after 2 characters. Use ↑/↓, Enter or Tab to insert, Esc to close.
- Suggestions include aliases; colors mark the category (general, artist, character, copyright, meta).
- When you leave a field, it gets an orange outline for unknown tags or a red one for blocked tags. Hover it to see the list.
- Settings → **TagForge**:
  - turn autocomplete on/off;
  - artist syntax (Anima/Illustrious);
  - suggestion source (Danbooru, e621, both).

## Your own tags
Quality and meta tags the models know but boorus don't (`masterpiece`, `best quality`, `newest`, `year 2024`, `score_9`, `explicit`…) are never reported as unknown.
Add your own (e.g. LoRA trigger words) to `data/custom_tags.txt`, one per line. Changes apply without a restart.

## Content block
Tags and words referring to minors (loli, shota, cub, young, child…, ages under 18) stop the prompt with an error. This cannot be turned off.

## Data sources
- Danbooru: `danbooru.donmai.us` public API (tags with post counts and creation dates, active aliases).
- e621: `static1.e621.net/data/db_export/` (`tags.csv.gz`, `tag_aliases.csv.gz`).

Respect both sites' terms. The script waits between Danbooru requests.

## Tests
```
python tests/test_core.py
```
