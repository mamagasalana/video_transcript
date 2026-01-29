cd /home/ytee/test/video_transcript
cp --update=none ~/ysg_backup/*.mp4 /home/ytee/test/ysg_backup/

export CUDNN_PATH="/home/ytee/test/trade_bot/venv/lib/python3.11/site-packages/nvidia/cudnn/lib"
export LD_LIBRARY_PATH="/home/ytee/test/trade_bot/venv/lib/python3.11/site-packages/nvidia/cudnn/lib"


/home/ytee/test/trade_bot/venv/bin/python src/generate_transcript.py