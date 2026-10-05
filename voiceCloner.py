from qwen_tts import Qwen3TTSModel
import soundfile as sf
import tkinter as tk
from tkinter import messagebox
import time 
from pathlib import Path
import shutil

window = tk.Tk()
window.title("YouSpeak - Voice Cloning")
window.geometry("800x600")
window.configure(bg="#7b0416")
voice_list = tk.Listbox(window, height=5, selectmode=tk.SINGLE)
add_button = tk.Button(window, text="Add New Voice", command=lambda: open_add_voice_window())
add_button.pack(pady=5)
voice_list.pack(pady=5)
tk.Label(window, text="Enter text to clone voice:").pack(pady=5)
text_entry = tk.Entry(window, width=50)
text_entry.pack(pady=5)
enter_button = tk.Button(window, text="Clone Voice", command=lambda: clone_voice(text_entry.get()))
enter_button.pack(pady=5)

TTS_MODEL = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-Base")
language = "English"

BASE_DIR = Path(__file__).resolve().parent
Sounds_DIR = BASE_DIR / "Sounds"
Sounds_DIR.mkdir(exist_ok=True)

def refresh_voice_list():
    voice_list.delete(0, tk.END)
    for name in list_sounds():
        voice_list.insert(tk.END, name)

def open_add_voice_window():

    voice_choice = "new"
    add_voice_window = tk.Toplevel(window)

    add_voice_window.title("Add New Voice")
    add_voice_window.geometry("400x300")
    path_label = tk.Label(add_voice_window, text="Path to reference audio:")
    path_label.pack(pady=5)
    path_entry = tk.Entry(add_voice_window, width=50)
    path_entry.pack(pady=5)
    transcript_label = tk.Label(add_voice_window, text="Exact transcript of that audio:")
    transcript_label.pack(pady=5)
    transcript_entry = tk.Entry(add_voice_window, width=50)
    transcript_entry.pack(pady=5)
    enter_name_label = tk.Label(add_voice_window, text="Name for new voice:")
    enter_name_label.pack(pady=5)
    enter_name_entry = tk.Entry(add_voice_window, width=50)
    enter_name_entry.pack(pady=5)
    finish_button = tk.Button(add_voice_window, text="Finish", command=lambda: finish_adding_sound(enter_name_entry.get(), path_entry.get(), transcript_entry.get()))
    finish_button.pack(pady=20)

def open_output_window():
    output_window = tk.Toplevel(window)
    output_window.title("Output Audio Files")
    output_window.geometry("400x300")
    output_list = tk.Listbox(output_window, height=10, selectmode=tk.SINGLE)
    output_list.pack(pady=5)
    for name in list_outputs():
        output_list.insert(tk.END, name)

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


def add_sound(name, audio_path, transcript):
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
    shutil.copy(audio_file, folder / "ref.wav")
    (folder / "ref.txt").write_text(transcript.strip(), encoding="utf-8")
    return name

def finish_adding_sound(name, audio_path, transcript):
    try:
        add_sound(name, audio_path, transcript)
    except FileNotFoundError as error:
        messagebox.showerror("Invalid audio file", str(error))
        return
    refresh_voice_list()
    print(f"Added new voice: {name}")

voices = list_sounds()
refresh_voice_list()
print("Voices:", ", ".join(voices) if voices else "(none yet)")

def clone_voice(text):
    selection = voice_list.curselection()
    if not selection:
        messagebox.showwarning("Select a voice", "Choose a voice before cloning.")
        return

    voice_choice = voice_list.get(selection[0])
    ref_audio_path, ref_text = load_sound(voice_choice)
    start_time = time.time()
    wavs, sr = TTS_MODEL.generate_voice_clone(
        text=text,
        language=language,
        ref_audio=ref_audio_path,
        ref_text=ref_text,
    )
    end_time = time.time()
    print(f"Voice cloning completed in {end_time - start_time:.2f} seconds.")
    sf.write(str(BASE_DIR / f"output_{voice_choice}.wav"), wavs[0], samplerate=sr)

window.mainloop()
