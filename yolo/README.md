YOLO screen detector starter files.

Folder layout:

- `yolo/images/train`
- `yolo/images/val`
- `yolo/labels/train`
- `yolo/labels/val`
- `yolo/dataset_train_label.yaml`

Use:

1. run `pipelines/yolo/step1_generate_yolo_dataset.py`
2. run `pipelines/yolo/step2_make_label_subset.py`
3. label `screen`, `host`, `welcome_screen` in Label Studio
4. run `pipelines/yolo/step4_label_studio_to_yolo.py`
5. run `pipelines/yolo/step5_train_yolo_screen.py`
6. run `pipelines/yolo/step6_predict_yolo_screen.py`

YOLO label format:

- one line per box
- `class_id x_center y_center width height`
- all box numbers normalized to `0~1`

For the current labeled subset:

- `0 = screen`
- `1 = host`
- `2 = welcome_screen`
