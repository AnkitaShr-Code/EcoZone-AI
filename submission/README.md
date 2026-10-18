# Submission artifacts

Sources and outputs behind the competition deliverables. Everything here was built from the live app and `evals/REPORT.md`; no number is written by hand. Only the text and code sources are committed. The finished files (the filled PPTX, the PDF, the video, the explainer audio) and large intermediates (screen takes, screenshots, short loops, previews) are not, because they are submitted separately and would only add weight and go stale.

## `deck/`: pitch deck

- The PDF (18 pages, 16:9, links clickable) is printed with Chrome from the slide files in `project/` by `pdf.mjs`; the demo video link (Google Drive) is on page 16.
- The filled PPTX is built by `build_pptx.py` from the official template (`Submission Template _ AI Builder Cup.pptx` in the repo root). The template's slides, header images and bars are kept and its note slide is removed. Snapshots and performance run over extra pages. Slide bodies, charts and screenshots are pictures (fonts baked in); slide 1's team fields and slide 16's links are real text. It was built and checked programmatically (`check_pptx.py`: every shape inside the slide, no empty placeholders) but not rendered in PowerPoint here, so open it once before exporting to PDF.
- `project/`: the deck as slide files (HTML/CSS, Google Fonts: Space Grotesk, Inter, JetBrains Mono). They reference real screenshots and two short loops from the live app (`assets/`, not committed; retake them with `video/record.mjs`).
- `build_pptx.py` / `check_pptx.py`: build and verify the PPTX from the template. `heat_ranks.py` / `heat_ranks.json`: the heat-check scatter data (ranks only; reproduces the eval's rho and p). `render.mjs`: renders slide files to PNG with Playwright and system Chrome.

## `video/`: demo video pipeline

- `script.md` / `script.json`: shot list, narration templates and overlays; `narration.md` and `narration-segments.json` are the narration filled from one recorded take; `values.json` holds the numbers read from the app during that take.
- `record.mjs`: drives the live app with Playwright and system Chrome (needs `npm install`; no browser download) and records frames, markers and values.
- `tools/`, `graphics/`, `lib/`, `build.sh`: assemble frames, fill the narration from the take's values, render HTML/CSS overlays and cut the video to the narration audio (`./build.sh --voice-dir audio/ --out out/final.mp4`; ffmpeg required).
- Honesty rules the narration follows are in `script.md`: numbers come from the screen or `evals/REPORT.md`; the Gemini vs greedy outcome is stated as the take showed it; the heat check is described as weak and not significant.

## `docs/explainer/`

`explainer-script-v2.md` (about 10 minutes) and `explainer-script-v2-short.md` (about 2.5 minutes): a spoken walk-through of what was built, the decisions and when. The audio versions are not committed.
