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

def open_add_voice_window():

    def select_file():
        file_selected = filedialog.askopenfilename(title="Select Reference Audio", filetypes=[("Audio Files", "*.wav *.mp3")])
        if not file_selected:
            messagebox.showwarning("No file selected", "You must select an audio file to add a new voice.")
        return file_selected

    add_voice_window = tk.Toplevel(window, bg="#8eacaa")
    add_voice_window.header = ttk.Label(add_voice_window, text="Add New Voice", font=("Helvetica", 14))
    add_voice_window.header.pack(pady=10)
    add_voice_window.geometry("400x300")
    voice_choice = "new"
    add_voice_window.title("Add New Voice")
    add_voice_window.geometry("400x300")
    select_file_button = ttk.Button(add_voice_window, text="Select Reference Audio", command=lambda: select_file())
    select_file_button.pack(pady=10)
    transcript_label = ttk.Label(add_voice_window, text="Exact transcript of that audio:")
    transcript_label.pack(pady=5)
    transcript_entry = ttk.Entry(add_voice_window, width=50)
    transcript_entry.pack(pady=5)
    enter_name_label = ttk.Label(add_voice_window, text="Name for new voice:")
    enter_name_label.pack(pady=5)
    enter_name_entry = ttk.Entry(add_voice_window, width=50)
    enter_name_entry.pack(pady=5)
    finish_button = ttk.Button(add_voice_window, text="Finish", command=lambda: finish_adding_sound(enter_name_entry.get(), file_selected, transcript_entry.get()))
    finish_button.pack(pady=20)

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

def convert_audio_to_wav(input_path, output_path):
    if input_path.suffix.lower() == ".wav":
        shutil.copy(input_path, output_path)
        return
    else:
        try:
            audio = AudioSegment.from_file(input_path)
            audio.export(output_path, format="wav")
            tk.messagebox.showinfo("Conversion Complete", f"Converted {input_path.name} to WAV format.")
        except Exception as e:
            tk.messagebox.showerror("Conversion Failed", f"Failed to convert audio file {input_path} to WAV: {e}")
            raise RuntimeError(f"Failed to convert audio file {input_path} to WAV: {e}")

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
    convert_audio_to_wav(audio_file, folder / "ref.wav")
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
    tk.messagebox.showinfo("Voice Added", f"Successfully added new voice: {name}")

voices = list_sounds()
refresh_voice_list()
print("Voices:", ", ".join(voices) if voices else "(none yet)")

def clone_voice(text):
    from qwen_tts import Qwen3TTSModel
    TTS_MODEL = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-Base")
    language = "English"

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
    sf.write(str(BASE_DIR / f"output_{voice_choice}_{int(time.time())}.wav"), wavs[0], samplerate=sr)
    tk.messagebox.showinfo("Voice Cloning Complete", f"Output audio saved as output_{voice_choice}_{int(time.time())}.wav")
    refresh_output_list(globals()["output_list"])

window.mainloop()
