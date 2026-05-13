Put custom OCR recognition model files here.

Expected file names:

- `rec.onnx`
- `dict.txt`

If `ocr/models/rec.onnx` exists, `pipelines/ocr_text/generate_ocr.py` will use it.

If `ocr/models/dict.txt` also exists, it will be passed as `rec_keys_path`.

If no custom model is found, the script falls back to RapidOCR default models.


mkdir -p ocr/models
curl -L 'https://huggingface.co/monkt/paddleocr-onnx/resolve/main/languages/chinese/dict.txt' -o ocr/models/dict.txt

curl -L 'https://huggingface.co/monkt/paddleocr-onnx/resolve/main/languages/chinese/rec.onnx' -o ocr/models/rec.onnx

