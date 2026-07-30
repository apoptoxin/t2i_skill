---
name: generate-douyin-cover
description: Turn a Chinese short-video voiceover script into a project-scoped 3:4 Douyin cover, or a complete image-generation prompt bundle when no image tool is available. Use when the user asks to create, redesign, standardize, compare, or generate prompts for a Chinese social-video cover.
---

# Generate Douyin Cover

Turn one Chinese voiceover script into a reusable cover package. Preserve the
project's brand choice, select one of three proven composition families, use
debranded Few-shot references, and validate the final cover before delivery.

Do not connect to or publish on GitHub unless the user separately asks.

## 0. Prepare the runtime

Resolve `<skill-root>` to the absolute directory that contains this `SKILL.md`.
Never assume the current working directory is the Skill directory.

Before the first run on a computer, run:

```bash
python3 "<skill-root>/scripts/doctor.py" \
  --skill-root "<skill-root>"
```

If the doctor reports that Pillow is missing or outside the supported range,
install the bundled requirement and rerun the doctor:

```bash
python3 -m pip install -r "<skill-root>/requirements.txt"
```

All fonts, licenses, references, and Few-shot examples required by the scripts
are bundled under `<skill-root>`. Do not replace them with machine-local paths.

An image-generation tool is optional. Without one, stop after producing the
validated prompt bundle and report `prompt_only`.

## 1. Initialize every project

This Skill is global, but its configuration is project-scoped. Before the first
run in a project, check for `.cover-skill/config.json`.

If it is absent, ask only for:

1. whether to display an account name;
2. the account name when enabled;
3. whether the first run should create one or two variants.

Then run:

```bash
python3 "<skill-root>/scripts/project_state.py" init \
  --project-root <project-root> \
  --brand-mode text \
  --brand-name "<account-name>" \
  --initial-variants 1
```

Use `--brand-mode none --brand-name ""` when no account name is wanted.
Never reuse initialization from another project.

If the user rejects two generated covers in a row, record both rejections.
The state then changes the default to two variants:

```bash
python3 "<skill-root>/scripts/project_state.py" feedback \
  --project-root <project-root> \
  --outcome rejected
```

Two consecutive accepted covers restore the default to one variant.

## 2. Read the script before designing

Extract the single strongest conflict, the visible evidence, and the promised
result. Do not invent numbers, proof, product names, or results.

Choose exactly one layout:

- `process`: messy input becomes an ordered method or workflow;
- `comparison`: old/new, wrong/right, before/after, or two competing choices;
- `evidence`: three sources, tests, reports, or examples point to one result.

Read [references/layouts.md](references/layouts.md) and
[references/style-system.md](references/style-system.md).

Create `cover-variables.json` using the schema in
[references/variable-schema.md](references/variable-schema.md).

Hard limits:

- top label: at most 8 Chinese characters;
- title: at most two lines, each at most 14 visible characters;
- one core conflict only;
- no unbacked number;
- no copied Demo wording;
- rightmost 12% contains no critical information.

## 3. Build the prompt bundle

Use only the Few-shot image matching the selected layout:

- process: `assets/examples/process-demo-debranded.png`;
- comparison: `assets/examples/comparison-demo-debranded.png`;
- evidence: `assets/examples/evidence-demo-debranded.png`.

The other two images may explain the common style family, but must not be
averaged into the composition. Read
[references/few-shot-guide.md](references/few-shot-guide.md).

Run:

```bash
python3 "<skill-root>/scripts/prompt_bundle.py" \
  --source-script <script-file> \
  --variables <variables-json> \
  --output <run-dir> \
  --style-file "<skill-root>/references/style-system.md" \
  --layout-file "<skill-root>/references/layouts.md"
```

This always creates:

- `cover-variables.json`
- `cover-prompt.txt`
- `negative-prompt.txt`
- `layout-spec.md`

## 4. Generate a background when an image tool exists

Use the matching debranded Few-shot image as the image reference. Use the
`background_only` section in `cover-prompt.txt`.

The image model must create composition, material, overlap, rotation, crop,
shadows, and the heavy brush arrow. It must create no readable text.

Do not ask the image model to write final Chinese. Exact Chinese is added by the
renderer so that typography is stable.

When the project state requests two variants, generate two backgrounds with the
same content but meaningfully different crop, rotation, and overlap. Do not
return two near-duplicates.

## 5. Add accurate Chinese

Run:

```bash
python3 "<skill-root>/scripts/render_cover.py" \
  --background <generated-background> \
  --variables <run-dir>/cover-variables.json \
  --output <run-dir>/cover-candidate.png \
  --manifest <run-dir>/cover-candidate.manifest.json
```

The bundled font is Adobe Source Han Sans CN Heavy 1.004R under the SIL Open
Font License. See `assets/fonts/OFL.txt`.

The renderer intentionally overlays only typography and a few torn labels. It
must not redraw the generated collage as a clean card grid.

Image models may move the body collage while preserving the requested style.
When the paper strips and their text anchors do not align, rerender a process
cover with `--body-offset <pixels>`. This moves only the process-body labels;
the headline stays fixed. Choose the offset by visual inspection, then run the
same formal QA. Do not accept a candidate merely because its boxes do not
mathematically overlap.

## 6. Validate before delivery

Run:

```bash
python3 "<skill-root>/scripts/validate_output.py" \
  --project-root <project-root> \
  --run-dir <run-dir> \
  --source-script <script-file>
```

Only a passing formal run may create `cover.png`. A failed candidate remains
`cover-candidate.png` and must not be described as final.

Before delivery, visually inspect:

- title readability at thumbnail size;
- no text overlap or clipping;
- no critical content in the right interaction strip;
- no accidental Demo wording or account name;
- irregular editorial composition, not UI cards or PPT;
- generated background and overlaid text agree semantically.

If no image tool exists, deliver the four-file prompt bundle and explicitly call
it `prompt_only`; never create a placeholder called `cover.png`.
