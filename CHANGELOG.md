# Changelog

## 1.2.4
Security and reliability fixes (no feature changes, no login added):
- Fixed path traversal in `GET /clones/{id}/sample` and `DELETE /clones/{id}` (ids are now validated and confined to `clones/`).
- `/api/settings` now accepts only known keys with valid values.
- Added 25 MB upload limit for `/transcribe` and `/clone-voice`; 20,000 character limit for `/insert-text`.
- Clipboard is restored only if the user did not copy something else in the meantime.
- Removed silent runtime `pip install`; offline Whisper is now an explicit optional install (`requirements-offline.txt`).
- Dependency ranges now have upper bounds.
- `voice-server.log` rotates at 5 MB.
- Installer copies `VERSION` and `requirements-offline.txt`; uninstaller asks for confirmation and only stops VOICE processes.
- README: fixed broken download link, version mismatches, and overstated claims; documented the Google STT and clipboard behavior.
