# Audio assets

The MVP ships **no third-party audio files**: all ambience and effects are generated procedurally with the Web Audio API
(`frontend/lib/audio-manager.ts`), so there are no licensing concerns.

To mix in richer, licensed recordings (rain, wind, cave reverb), place files here, serve them from `frontend/public/audio/`,
and load them in `AudioManager.buildLayer` with `fetch` + `decodeAudioData`. Only add files whose licence permits redistribution
and record their source and licence in this folder.
