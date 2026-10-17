# Regenerating the demo

Records `docs/demo.gif` and `docs/demo.mp4` from a scripted session against an isolated demo database.

```bash
# from the repo root
uv pip install playwright imageio-ffmpeg && uv run playwright install chromium

cd sandbox
export PYTHONPATH=../docs/demo DJANGO_SETTINGS_MODULE=demo_settings
rm -f ../docs/demo/demo.sqlite3 ../docs/demo/demo_dorm.json
uv run python manage.py migrate -v0
uv run python manage.py shell -v0 < ../docs/demo/seed.py
uv run python manage.py runserver 127.0.0.1:8001 --noreload &

cd .. && uv run python docs/demo/record.py docs/demo/raw   # prints the .webm path

FF=$(uv run python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())")
$FF -y -ss 0.6 -i docs/demo/raw/*.webm -vf "fps=10,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" docs/demo.gif
$FF -y -ss 0.6 -i docs/demo/raw/*.webm -c:v libx264 -pix_fmt yuv420p -crf 24 -preset slow -movflags +faststart -an docs/demo.mp4
```

Keep the GIF under ~5 MB, since GitHub and PyPI proxy README images.
