import soundfile as sf
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from tkinter import font
from tkinter import filedialog
import sv_ttk
import winsound
import time 
from pathlib import Path
import shutil
import subprocess
import queue
import tempfile
import threading
import pydub
from pydub import AudioSegment

window = tk.Tk()
window.title("YouSpeak - Voice Cloning")
window.header = ttk.Label(window, text="YouSpeak - Voice Cloning", font=("Helvetica", 16))
window.header.pack(pady=10)
window.geometry("800x600")
window.configure(bg="#8eacaa")
voice_list = tk.Listbox(window, height=5, selectmode=tk.SINGLE)
add_button = ttk.Button(window, text="Add New Voice", command=lambda: open_add_voice_window())
add_button.pack(pady=5)
voice_list.pack(pady=5)
ttk.Label(window, text="Enter text to clone voice:", font=("Helvetica", 12)).pack(pady=5)
text_entry = ttk.Entry(window, width=50)
text_entry.pack(pady=5)
clone_status_label = ttk.Label(window, text="")
clone_status_label.pack(pady=5)
enter_button = ttk.Button(window, text="Clone Voice", command=lambda: clone_voice(text_entry.get()))
enter_button.pack(pady=5)
output_button = ttk.Button(window, text="Outputs", command=lambda: open_output_window())
output_button.pack(pady=5)

BASE_DIR = Path(__file__).resolve().parent
Sounds_DIR = BASE_DIR / "Sounds"
Sounds_DIR.mkdir(exist_ok=True)

def refresh_voice_list():
    voice_list.delete(0, tk.END)
    for name in list_sounds():
        voice_list.insert(tk.END, name)

def refresh_output_list(output_list):
    output_list.delete(0, tk.END)
    for name in list_outputs():
        output_list.insert(tk.END, name)


def run_background_task(parent, status_label, buttons, initial_status, task, on_success, on_error):
    result_queue = queue.Queue()
    started_at = time.monotonic()

    for button in buttons:
        button.configure(state=tk.DISABLED)
    status_label.configure(text=f"{initial_status} (0s elapsed)")

    def report_status(text):
        result_queue.put(("status", text))

    def worker():
        try:
            result_queue.put(("success", task(report_status)))
        except Exception as error:
            result_queue.put(("error", error))

    def poll_result():
        if not parent.winfo_exists():
            return

        final_result = None
        latest_status = None
        while True:
            try:
                kind, value = result_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "status":
                latest_status = value
            else:
                final_result = (kind, value)

        if final_result is not None:
            for button in buttons:
                button.configure(state=tk.NORMAL)
            kind, value = final_result
            if kind == "success":
                try:
                    on_success(value)
                except Exception as error:
                    on_error(error)
            else:
                on_error(value)
            return

        elapsed = int(time.monotonic() - started_at)
        if latest_status:
            status_label.configure(text=f"{latest_status} ({elapsed}s elapsed)")
        else:
            current_status = status_label.cget("text").rsplit(" (", 1)[0]
            status_label.configure(text=f"{current_status} ({elapsed}s elapsed)")
        parent.after(250, poll_result)

    threading.Thread(target=worker, daemon=True).start()
    parent.after(100, poll_result)


def open_add_voice_window():
    selected_file_path = None
    selected_youtube_url = None
    downloaded_youtube_path = None
    download_temp_dir = None
    download_in_progress = False
    download_success_action = None
    download_started_at = None
    download_status_text = ""
    download_results = queue.Queue()
    shorten_audio_flag = tk.BooleanVar(value=False)

    def cleanup_download_temp_dir():
        nonlocal download_temp_dir, downloaded_youtube_path
        if download_temp_dir:
            shutil.rmtree(download_temp_dir)
            download_temp_dir = None
        downloaded_youtube_path = None

    def select_file():
        nonlocal selected_file_path, selected_youtube_url, downloaded_youtube_path
        cleanup_download_temp_dir()
        selected_file_path = filedialog.askopenfilename(
            parent=add_voice_window,
            title="Select Reference Audio",
            filetypes=[("Audio Files", "*.wav *.mp3")],
        )
        if selected_file_path:
            selected_youtube_url = None
            downloaded_youtube_path = None
            enter_youtube_url.delete(0, tk.END)
        else:
            messagebox.showwarning("No file selected", "You must select an audio file to add a new voice.")
            print("No file selected for reference audio.")

    def select_youtube_url():
        nonlocal selected_file_path, selected_youtube_url, downloaded_youtube_path
        url = enter_youtube_url.get().strip()
        if not url:
            messagebox.showwarning("No URL entered", "You must enter a YouTube URL to add a new voice.")
            print("No URL entered for YouTube reference audio.")
            return
        if url != selected_youtube_url:
            cleanup_download_temp_dir()
        selected_youtube_url = url
        selected_file_path = None

    def get_reference_audio_path():
        nonlocal selected_file_path, selected_youtube_url, downloaded_youtube_path
        url = enter_youtube_url.get().strip()
        if url:
            if url != selected_youtube_url:
                cleanup_download_temp_dir()
            selected_youtube_url = url
            selected_file_path = None
        if downloaded_youtube_path and downloaded_youtube_path.is_file():
            return downloaded_youtube_path
        return Path(selected_file_path) if selected_file_path else None

    def set_download_controls_enabled(enabled, allow_finish=False):
        state = tk.NORMAL if enabled else tk.DISABLED
        select_file_button.configure(state=state)
        enter_youtube_url.configure(state=state)
        select_youtube_button.configure(state=state)
        convert_button.configure(state=state)
        finish_button.configure(state=tk.NORMAL if enabled or allow_finish else tk.DISABLED)

    def run_download_action(on_success, audio_path):
        try:
            on_success(audio_path)
        except Exception as error:
            status_label.configure(text=f"Could not complete: {error}")
            print(f"Could not complete YouTube audio action: {error}")
            messagebox.showerror(
                "Could Not Complete",
                f"The audio downloaded, but the next step failed:\n{error}",
                parent=add_voice_window,
            )

    def poll_download_result():
        nonlocal downloaded_youtube_path, download_temp_dir, download_in_progress
        nonlocal download_success_action, download_started_at
        nonlocal download_status_text
        try:
            success, result = download_results.get_nowait()
        except queue.Empty:
            if add_voice_window.winfo_exists():
                add_voice_window.after(100, poll_download_result)
            return

        while True:
            try:
                success, result = download_results.get_nowait()
            except queue.Empty:
                break

        if success is None:
            download_status_text = result
            status_label.configure(text=result)
            add_voice_window.after(100, poll_download_result)
            return

        download_in_progress = False
        download_started_at = None
        on_success = download_success_action
        download_success_action = None
        set_download_controls_enabled(True)
        if not add_voice_window.winfo_exists():
            return
        if success:
            downloaded_youtube_path = result
            status_label.configure(
                text="Download complete. Add the voice name and transcript, then click Finish."
            )
            if on_success:
                run_download_action(on_success, downloaded_youtube_path)
        else:
            cleanup_download_temp_dir()
            status_label.configure(text="Download failed.")
            messagebox.showerror("YouTube Download Failed", str(result), parent=add_voice_window)

    def start_youtube_download(on_success):
        nonlocal download_temp_dir, download_in_progress, download_success_action
        nonlocal download_started_at, download_status_text
        url = enter_youtube_url.get().strip()
        if not url:
            messagebox.showwarning(
                "No URL entered",
                "Enter a YouTube URL or select an audio file first.",
                parent=add_voice_window,
            )
            return

        if download_in_progress:
            download_success_action = on_success
            status_label.configure(text="Download in progress; will finish adding the voice when it completes.")
            return
        if url != selected_youtube_url:
            select_youtube_url()
        audio_path = get_reference_audio_path()
        if audio_path is not None:
            run_download_action(on_success, audio_path)
            return

        download_temp_dir = tempfile.mkdtemp(prefix="voice-cloner-")
        audio_path = Path(download_temp_dir) / "reference.wav"
        download_in_progress = True
        download_started_at = time.monotonic()
        download_status_text = "Downloading YouTube audio..."
        download_success_action = on_success
        set_download_controls_enabled(False, allow_finish=True)
        status_label.configure(text=download_status_text)

        def update_download_elapsed():
            if (
                not download_in_progress
                or download_started_at is None
                or not add_voice_window.winfo_exists()
            ):
                return
            elapsed = int(time.monotonic() - download_started_at)
            status_label.configure(
                text=f"{download_status_text} ({elapsed}s elapsed)"
            )
            add_voice_window.after(1000, update_download_elapsed)

        def download():
            try:
                download_youtube_audio(
                    url,
                    audio_path,
                    lambda status: download_results.put((None, status)),
                )
                download_results.put((True, audio_path))
            except Exception as error:
                download_results.put((False, error))

        threading.Thread(target=download, daemon=True).start()
        add_voice_window.after(100, poll_download_result)
        add_voice_window.after(1000, update_download_elapsed)

    def convert_selected_audio():
        def convert_audio(path):
            def convert(report_status):
                report_status("Converting audio to WAV...")
                convert_audio_to_wav(path, BASE_DIR / "temp.wav")

            def conversion_complete(_result):
                status_label.configure(text="WAV conversion complete.")

            run_background_task(
                add_voice_window,
                status_label,
                (
                    select_file_button,
                    enter_youtube_url,
                    select_youtube_button,
                    transcript_entry,
                    enter_name_entry,
                    shorten_button,
                    convert_button,
                    finish_button,
                ),
                "Converting audio to WAV...",
                convert,
                conversion_complete,
                show_operation_error,
            )

        audio_path = get_reference_audio_path()
        if audio_path is None and selected_youtube_url:
            start_youtube_download(convert_audio)
            return
        if audio_path is None:
            messagebox.showwarning("No audio selected", "Select an audio file or enter a YouTube URL first.")
            return
        convert_audio(audio_path)

    def finish_selected_sound():
        def finish_with_path(path):
            name = enter_name_entry.get()
            transcript = transcript_entry.get()

            def save_voice(report_status):
                return add_sound(name, str(path), transcript, report_status)

            def voice_added(added_name):
                refresh_voice_list()
                status_label.configure(text=f"Voice '{added_name}' added.")
                messagebox.showinfo(
                    "Voice Added",
                    f"Successfully added new voice: {added_name}",
                    parent=add_voice_window,
                )
                cleanup_download_temp_dir()
                add_voice_window.destroy()

            run_background_task(
                add_voice_window,
                status_label,
                (
                    select_file_button,
                    enter_youtube_url,
                    select_youtube_button,
                    transcript_entry,
                    enter_name_entry,
                    shorten_button,
                    convert_button,
                    finish_button,
                ),
                "Saving voice...",
                save_voice,
                voice_added,
                show_operation_error,
            )

        audio_path = get_reference_audio_path()
        if audio_path is None and selected_youtube_url:
            start_youtube_download(finish_with_path)
            return
        if audio_path is None:
            messagebox.showwarning("No audio selected", "Select an audio file or enter a YouTube URL first.")
            return
        finish_with_path(audio_path)

    def use_youtube_url():
        def show_download_complete(_path):
            status_label.configure(
                text="Download complete. Enter the voice name and transcript, then click Finish."
            )
            messagebox.showinfo(
                "Download Complete",
                "YouTube audio is ready. Enter the voice name and transcript, then click Finish.",
                parent=add_voice_window,
            )

        select_youtube_url()
        if selected_youtube_url:
            start_youtube_download(show_download_complete)

    def show_operation_error(error):
        status_label.configure(text=f"Operation failed: {error}")
        print(f"Add voice operation failed: {error}")
        messagebox.showerror(
            "Add Voice Failed",
            str(error),
            parent=add_voice_window,
        )

    add_voice_window = tk.Toplevel(window, bg="#8eacaa")
    add_voice_window.header = ttk.Label(add_voice_window, text="Add New Voice", font=("Helvetica", 14))
    add_voice_window.header.pack(pady=10)
    add_voice_window.geometry("500x500")
    add_voice_window.title("Add New Voice")
    add_voice_window.geometry("500x500")
    select_file_button = ttk.Button(add_voice_window, text="Select Reference Audio", command=lambda: select_file())
    select_file_button.pack(pady=10)
    enter_youtube_label = ttk.Label(add_voice_window, text="Or enter YouTube URL for reference audio:")
    enter_youtube_label.pack(pady=5)
    enter_youtube_url = ttk.Entry(add_voice_window, width=50)
    enter_youtube_url.pack(pady=5)
    select_youtube_button = ttk.Button(add_voice_window, text="Download YouTube Audio", command=use_youtube_url)
    select_youtube_button.pack(pady=10)
    status_label = ttk.Label(add_voice_window, text="")
    status_label.pack(pady=5)
    transcript_label = ttk.Label(add_voice_window, text="Enter Transcript of audio ")
    transcript_label.pack(pady=5)
    transcript_entry = ttk.Entry(add_voice_window, width=50)
    transcript_entry.pack(pady=5)
    enter_name_label = ttk.Label(add_voice_window, text="Name for new voice:")
    enter_name_label.pack(pady=5)
    enter_name_entry = ttk.Entry(add_voice_window, width=50)
    enter_name_entry.pack(pady=5)
    shorten_button = ttk.Checkbutton(add_voice_window, text="Shorten Audio", variable=shorten_audio_flag)
    shorten_button.pack(pady=10)
    convert_button = ttk.Button(add_voice_window, text="Convert to WAV", command=convert_selected_audio)
    convert_button.pack(pady=10)
    finish_button = ttk.Button(add_voice_window, text="Finish", command=finish_selected_sound)
    finish_button.pack(pady=20)

    def close_add_voice_window():
        cleanup_download_temp_dir()
        add_voice_window.destroy()

    add_voice_window.protocol("WM_DELETE_WINDOW", close_add_voice_window)

def open_output_window():
    output_window = tk.Toplevel(window)
    output_window.title("Output Audio Files")
    output_window.geometry("400x300")
    output_list = tk.Listbox(output_window, height=10, selectmode=tk.SINGLE)
    output_list.pack(pady=5)
    for name in list_outputs():
        output_list.insert(tk.END, name)

    def play_selected_output():
        selection = output_list.curselection()
        if not selection:
            messagebox.showwarning("Select an output", "Choose an output file to play.")
            return

        output_path = BASE_DIR / output_list.get(selection[0])
        if not output_path.is_file():
            messagebox.showerror("Output not found", f"Output audio file not found: {output_path}")
            return

        try:
            winsound.PlaySound(
                str(output_path),
                winsound.SND_FILENAME | winsound.SND_ASYNC,
            )
        except OSError as error:
            messagebox.showerror("Playback failed", str(error))

    def stop_output_playback():
        winsound.PlaySound(None, winsound.SND_PURGE)

    def delete_selected_output():
        selection = output_list.curselection()
        if not selection:
            messagebox.showwarning("Select an output", "Choose an output file to delete.")
            return

        output_path = BASE_DIR / output_list.get(selection[0])
        if not output_path.is_file():
            messagebox.showerror("Output not found", f"Output audio file not found: {output_path}")
            return

        confirm = messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete {output_path.name}?")
        if confirm:
            try:
                output_path.unlink()
                output_list.delete(selection[0])
                print(f"Deleted output: {output_path.name}")
            except OSError as error:
                messagebox.showerror("Deletion failed", str(error))

    controls = ttk.Frame(output_window)
    controls.pack(pady=5)
    ttk.Button(controls, text="Play", command=play_selected_output).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls, text="Stop", command=stop_output_playback).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls, text="Delete", command=delete_selected_output).pack(side=tk.LEFT, padx=5)
    def close_output_window():
        stop_output_playback()
        output_window.destroy()

    output_window.protocol("WM_DELETE_WINDOW", close_output_window)

def download_youtube_audio(url, output_path, progress_callback=None):
    try:
        import yt_dlp
    except ImportError as error:
        raise RuntimeError(
            "yt-dlp is required to download YouTube audio. Install it with 'pip install yt-dlp'."
        ) from error

    def report_progress(progress):
        if not progress_callback:
            return
        if progress.get("status") == "downloading":
            percent = progress.get("_percent_str", "").strip()
            progress_callback(f"Downloading YouTube audio... {percent}")
        elif progress.get("status") == "finished":
            progress_callback("Download finished. Preparing audio for conversion...")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(output_path.with_name("reference.%(ext)s")),
        "progress_hooks": [report_progress],
        "socket_timeout": 30,
        "retries": 2,
        "fragment_retries": 2,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            requested_downloads = info.get("requested_downloads", [])
            if requested_downloads and requested_downloads[0].get("filepath"):
                source_path = Path(requested_downloads[0]["filepath"])
            else:
                source_path = Path(ydl.prepare_filename(info))
    except (yt_dlp.utils.DownloadError, OSError, KeyError, TypeError) as error:
        raise RuntimeError(f"Could not download audio from the YouTube URL: {error}") from error

    if not source_path.is_file():
        raise RuntimeError(f"YouTube download did not create the expected audio file: {source_path}")

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise RuntimeError(
            "FFmpeg is required to convert the downloaded audio to WAV. "
            "Install FFmpeg and make sure 'ffmpeg' is on PATH."
        )

    if progress_callback:
        progress_callback("Converting downloaded audio to WAV (FFmpeg)...")
    try:
        subprocess.run(
            [
                ffmpeg_path,
                "-y",
                "-i",
                str(source_path),
                "-vn",
                "-acodec",
                "pcm_s16le",
                str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            "FFmpeg did not finish converting the audio within 5 minutes. "
            "Try a shorter YouTube video."
        ) from error
    except subprocess.CalledProcessError as error:
        details = error.stderr.strip() if error.stderr else str(error)
        raise RuntimeError(f"FFmpeg could not convert the YouTube audio to WAV: {details}") from error

    if not output_path.is_file():
        raise RuntimeError(f"YouTube audio download did not create the expected file: {output_path}")


def convert_audio_to_wav(input_path, output_path):
    if input_path.suffix.lower() == ".wav":
        shutil.copy(input_path, output_path)
        return
    try:
        audio = AudioSegment.from_file(input_path)
        audio.export(output_path, format="wav")
    except Exception as error:
        raise RuntimeError(
            f"Failed to convert audio file {input_path} to WAV: {error}. "
            "Please ensure FFmpeg is installed and accessible."
        ) from error

def destroy_add_voice_window():
    for widget in window.winfo_children():
        if isinstance(widget, tk.Toplevel) and widget.title() == "Add New Voice":
            widget.destroy()
            break

def list_sounds():
    return sorted(
        p.name for p in Sounds_DIR.iterdir()
        if (p / "ref.wav").exists() and (p / "ref.txt").exists()
    )

voices = list_sounds()
voice_list.insert(tk.END, *voices)

def list_outputs():
    return sorted(
        p.name for p in BASE_DIR.iterdir()
        if p.suffix == ".wav"
    )

def load_sound(name):
    folder = Sounds_DIR / name
    ref_audio = str(folder / "ref.wav")
    ref_text = (folder / "ref.txt").read_text(encoding="utf-8").strip()
    return ref_audio, ref_text


def add_sound(name, audio_path, transcript, progress_callback=None):
    name = "".join(c for c in name if c.isalnum() or c in "-_ ").strip()
    audio_path = audio_path.strip()
    if (
        len(audio_path) >= 2
        and audio_path[0] == audio_path[-1]
        and audio_path[0] in {'"', "'"}
    ):
        audio_path = audio_path[1:-1]
    audio_file = Path(audio_path)
    if not audio_file.is_file():
        raise FileNotFoundError(f"Reference audio file not found: {audio_file}")

    folder = Sounds_DIR / name
    folder.mkdir(parents=True, exist_ok=True)
    if progress_callback:
        progress_callback("Converting reference audio to WAV...")
    convert_audio_to_wav(audio_file, folder / "ref.wav")
    if progress_callback:
        progress_callback("Saving transcript...")
    (folder / "ref.txt").write_text(transcript.strip(), encoding="utf-8")
    return name

def shorten_audio(input_path, output_path, max_duration=10):
    try:
        audio = AudioSegment.from_file(input_path)
        if len(audio) > max_duration * 1000:
            audio = audio[:max_duration * 1000]
            audio.export(output_path, format="wav")
            tk.messagebox.showinfo("Audio Shortened", f"Audio shortened to {max_duration} seconds and saved as {output_path.name}.")
        else:
            shutil.copy(input_path, output_path)
            tk.messagebox.showinfo("Audio Not Shortened", f"Audio is already shorter than {max_duration} seconds. Copied to {output_path.name}.")
    except Exception as e:
        tk.messagebox.showerror("Shortening Failed", f"Failed to shorten audio file {input_path}: {e}")
        raise RuntimeError(f"Failed to shorten audio file {input_path}: {e}")

def finish_adding_sound(name, audio_path, transcript):
    try:
        add_sound(name, audio_path, transcript)
    except FileNotFoundError as error:
        messagebox.showerror("Invalid audio file", str(error))
        return False
    except (OSError, RuntimeError, ValueError) as error:
        messagebox.showerror("Could not add voice", str(error), parent=window)
        return False
    refresh_voice_list()
    print(f"Added new voice: {name}")
    tk.messagebox.showinfo(
        "Voice Added",
        f"Successfully added new voice: {name}",
        parent=window,
    )
    destroy_add_voice_window()
    return True

voices = list_sounds()
refresh_voice_list()
print("Voices:", ", ".join(voices) if voices else "(none yet)")

def clone_voice(text):
    selection = voice_list.curselection()
    if not selection:
        messagebox.showwarning("Select a voice", "Choose a voice before cloning.")
        return

    voice_choice = voice_list.get(selection[0])

    def generate_clone(report_status):
        from qwen_tts import Qwen3TTSModel

        report_status("Loading voice-cloning model...")
        model = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-Base")
        ref_audio_path, ref_text = load_sound(voice_choice)
        report_status("Generating cloned voice...")
        wavs, sample_rate = model.generate_voice_clone(
            text=text,
            language="English",
            ref_audio=ref_audio_path,
            ref_text=ref_text,
        )
        output_path = BASE_DIR / f"output_{voice_choice}_{int(time.time())}.wav"
        report_status("Saving generated audio...")
        sf.write(str(output_path), wavs[0], samplerate=sample_rate)
        return output_path

    def clone_complete(output_path):
        clone_status_label.configure(text=f"Clone complete: {output_path.name}")
        messagebox.showinfo(
            "Voice Cloning Complete",
            f"Output audio saved as {output_path.name}",
            parent=window,
        )

    def clone_failed(error):
        clone_status_label.configure(text=f"Cloning failed: {error}")
        print(f"Voice cloning failed: {error}")
        messagebox.showerror("Voice Cloning Failed", str(error), parent=window)

    run_background_task(
        window,
        clone_status_label,
        (enter_button,),
        "Starting voice clone...",
        generate_clone,
        clone_complete,
        clone_failed,
    )

window.mainloop()
