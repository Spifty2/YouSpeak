# YouSpeak - Voice Cloner

YouSpeak is a Windows app for generating speech in the style of a selected reference voice from an audio file (.mp3 or .wav) or a YouTube URL.

## Requirements

- 64-bit Windows
- A compatible 64-bit Python installation
- FFmpeg, required to convert audio
- An internet connection the first time you clone a voice to download the model from Hugging Face
- Enough free disk space and memory for the model and its dependencies (about 4.5Gb)

The app uses Windows playback (winsound), so it is not cross-platform compatible. A GPU can improve generation speed but hardware support depends on the PyTorch installation.

## Set up and run from source 

Open PowerShell in the folder containing `voiceCloner.py` and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python .\voiceCloner.py
```
## IMPORTANT

Please install ffmpeg for teh audio conversion

Install FFmpeg separately and ensure `ffmpeg` is on `PATH` to convert or shorten non-WAV audio. For example:

```powershell
winget install Gyan.FFmpeg
```

The first voice-cloning run downloads `Qwen/Qwen3-TTS-12Hz-1.7B-Base` from Hugging Face and requires internet access, disk space, and sufficient memory. It is quite a large model so please be sure. May take up to an hour depending on internet speed.

Voice profiles are saved under `Sounds\<voice name>` beside the source code. In a packaged executable, profiles are stored under `%LOCALAPPDATA%\YouSpeak\Sounds`, so the app can write them without modifying its installation folder.

ENJOY :)

