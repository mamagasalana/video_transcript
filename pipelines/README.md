Pipeline entry points are grouped into 4 buckets:

- `pipelines/ocr_text`
  - OCR extraction from video frames
- `pipelines/yolo`
  - `step1_generate_yolo_dataset.py`
  - `step2_make_label_subset.py`
  - manual step 3 in Label Studio
  - `step4_label_studio_to_yolo.py`
  - `step5_train_yolo_screen.py`
  - `step6_predict_yolo_screen.py`
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
