Pipeline entry points are grouped into 4 buckets:

- `pipelines/ocr_text`
  - OCR extraction from video frames
- `pipelines/yolo`
  - screen/host/welcome_screen dataset prep, label conversion, train, predict
- `pipelines/llm`
  - instrument extraction, classification, visualization
- `pipelines/transcript`
  - transcript generation and cleanup

Shared library code now lives under:

- `src/llm`
- `src/transcript`

Data/output folders stay where they are:

- `ocr/`
- `yolo/`
- `transcripts/`
- `outputs/`
