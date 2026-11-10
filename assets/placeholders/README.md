# Placeholder art

Placeholder portraits and scenes are generated procedurally as SVG by `backend/app/assets/image_service.py`
(`PlaceholderImageProvider`). Set `IMAGE_PROVIDER=huggingface` and `HF_TOKEN` to use FLUX instead. Generated assets are cached per
campaign in `ASSET_DIR` and recorded in the `assets` table with provider, model id, prompt and prompt hash.
