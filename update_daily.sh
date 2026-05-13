cd /home/ytee/test/GuruArena
cp --update=none ~/ysg_backup/*.mp4 /home/ytee/test/ysg_backup/

export CUDNN_PATH="/home/ytee/test/GuruArena/venv/lib/python3.11/site-packages/nvidia/cudnn/lib"
export LD_LIBRARY_PATH="/home/ytee/test/GuruArena/venv/lib/python3.11/site-packages/nvidia/cudnn/lib"

venv/bin/python pipelines/transcript/generate_transcript.py
