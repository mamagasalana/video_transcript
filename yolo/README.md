YOLO screen detector starter files.

Folder layout:

- `yolo/images/train`
- `yolo/images/val`
- `yolo/labels/train`
- `yolo/labels/val`
- `yolo/dataset_train_label.yaml`

Use:

1. run `pipelines/yolo/generate_yolo_dataset.py`
2. label `screen`, `host`, `welcome_screen`
3. run `pipelines/yolo/train_yolo_screen.py`

YOLO label format:

- one line per box
- `class_id x_center y_center width height`
- all box numbers normalized to `0~1`

For the current labeled subset:

- `0 = screen`
- `1 = host`
- `2 = welcome_screen`
