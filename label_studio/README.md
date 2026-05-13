Label Studio quick start for screen-box labeling.

1. make a new batch first

```bash
venv/bin/python pipelines/yolo/step2_make_label_subset.py
```

This creates a new batch folder like:

- `yolo/images/batches/batch_002`
- `yolo/labels/batches/batch_002`

2. start label studio

```bash
HOME=/tmp/labelstudio_home venv/bin/label-studio start
```

3. open the web UI

- usually: `http://localhost:8080`

4. create a new project

5. use this labeling config:

```xml
<View>
  <Image name="image" value="$image"/>
  <RectangleLabels name="label" toName="image">
    <Label value="screen" background="red"/>
    <Label value="host" background="blue"/>
    <Label value="welcome_screen" background="green"/>
  </RectangleLabels>
</View>
```

6. import images from the newest batch folder:

- `yolo/images/batches/batch_XXX`

Example:

- `yolo/images/batches/batch_002`

7. label these classes:

- `screen`
- `host`
- `welcome_screen`

8. export annotations as JSON, then convert them into YOLO labels:

```bash
venv/bin/python pipelines/yolo/step4_label_studio_to_yolo.py
```

Current class mapping:

- `0 = screen`
- `1 = host`
- `2 = welcome_screen`

9. train YOLO on the labeled subset:

```bash
cd /home/ytee/test/GuruArena
venv/bin/python pipelines/yolo/step5_train_yolo_screen.py
```

10. run prediction preview:

```bash
cd /home/ytee/test/GuruArena
venv/bin/python pipelines/yolo/step6_predict_yolo_screen.py
```

This currently trains from:

- `yolo/images/train_label`
- `yolo/labels/train_label`
- `yolo/dataset_train_label.yaml`

Note:

- `train_label` is now a merged training view built from all labeled batches
- current `train` and `val` both point to the same labeled subset
- this first run is mainly a smoke test before making a proper validation split
