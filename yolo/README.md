YOLO screen detector starter files.

Folder layout:

- `yolo/images/train`
- `yolo/images/val`
- `yolo/labels/train`
- `yolo/labels/val`
- `yolo/images/batches/batch_001`
- `yolo/labels/batches/batch_001`
- `yolo/dataset_train_label.yaml`

Use:

1. run `pipelines/yolo/step1_generate_yolo_dataset.py`
2. run `pipelines/yolo/step2_make_label_subset.py`
3. label `screen`, `host`, `welcome_screen` in Label Studio
4. run `pipelines/yolo/step4_label_studio_to_yolo.py`
5. run `pipelines/yolo/step5_train_yolo_screen.py`
   then select the trained weight as current:
   ```bash
   mkdir -p yolo/weights
   cp yolo/runs/screen_label_subset/weights/best.pt yolo/weights/current.pt
   ```
6. run `pipelines/yolo/step6_predict_yolo_screen.py`

Batch notes:

- `step2` creates a new batch like `batch_001`, `batch_002`, ...
- each batch lives under:
  - `yolo/images/batches/`
  - `yolo/labels/batches/`
- `step5` merges all labeled batches back into:
  - `yolo/images/train_label`
  - `yolo/labels/train_label`
  before training
- important:
  - `step5` uses every batch folder under `yolo/images/batches/`
  - if a batch should not be part of training, delete that batch first

YOLO label format:

- one line per box
- `class_id x_center y_center width height`
- all box numbers normalized to `0~1`

Class mapping:

- `0 = screen`
- `1 = host`
- `2 = welcome_screen`
