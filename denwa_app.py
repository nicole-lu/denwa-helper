import streamlit as st
import pyaudio
import wave
import struct
import math
import time
import os
import threading
from google import genai

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

INPUT_RATE = 16000
CHUNK = 1024
VOLUME_THRESHOLD = 500
SILENCE_SECONDS = 3.0

PROMPT = """
You are DenwaHelper, a real-time Japanese phone call assistant for foreigners living in Japan.

Analyze the audio and respond using EXACTLY this format:

[TRANSLATION]
EN: (English translation)
中文: (Chinese translation)

[SITUATION]
EN: (one sentence - IVR menu / bank agent / government office / delivery / other)
中文: (同上中文)

[REQUIRED]
EN: (what is being asked from you)
中文: (需要你做什么)

[OPTIONS]
(If IVR button menu:
  Press 1 → balance inquiry / 按1→查余额
If no options, write: None)

[SUGGESTED REPLY]
(Japanese phrase to say back, or None)
"""

def get_volume(data):
    count = len(data) // 2
    shorts = struct.unpack(f"{count}h", data)
    rms = math.sqrt(sum(s * s for s in shorts) / count)
    return rms

def record_with_vad(status_placeholder):
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=INPUT_RATE,
                    input=True, frames_per_buffer=CHUNK)

    frames = []
    started = False
    silence_start = None

    status_placeholder.info("👂 Listening... play Japanese audio near microphone")

    start_time = time.time()
    while time.time() - start_time < 30:
        data = stream.read(CHUNK, exception_on_overflow=False)
        volume = get_volume(data)

        if volume > VOLUME_THRESHOLD:
            if not started:
                status_placeholder.warning("🔴 Recording...")
                started = True
            silence_start = None
            frames.append(data)
        else:
            if started:
                frames.append(data)
                if silence_start is None:
                    silence_start = time.time()
                elif time.time() - silence_start >= SILENCE_SECONDS:
                    break

    stream.stop_stream()
    stream.close()
    p.terminate()

    if not frames:
        return None

    filename = "temp_recording.wav"
    wf = wave.open(filename, "wb")
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(INPUT_RATE)
    wf.writeframes(b"".join(frames))
    wf.close()

    return filename

def analyze(filename, status_placeholder):
    status_placeholder.info("⚙️ Analyzing with Gemini...")
    audio_file = client.files.upload(file=filename)

    while audio_file.state.name == "PROCESSING":
        time.sleep(1)
        audio_file = client.files.get(name=audio_file.name)

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=[audio_file, PROMPT]
    )

    client.files.delete(name=audio_file.name)
    return response.text

def parse_result(text):
    sections = {}
    current = None
    current_lines = []

    for line in text.split("\n"):
        if line.startswith("[") and "]" in line:
            if current:
                sections[current] = "\n".join(current_lines).strip()
            current = line.strip("[]").strip()
            current_lines = []
        elif current:
            current_lines.append(line)

    if current:
        sections[current] = "\n".join(current_lines).strip()

    return sections

# ── UI ──────────────────────────────────────────────
st.set_page_config(page_title="DenwaHelper", page_icon="📞", layout="centered")

st.markdown("""
<h1 style='text-align:center'>📞 DenwaHelper <span style='font-size:0.5em; color:gray'>電話ヘルパー</span></h1>
<p style='text-align:center; color:gray'>AI assistant for Japanese phone calls</p >
<hr>
""", unsafe_allow_html=True)

if "history" not in st.session_state:
    st.session_state.history = []

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    start_btn = st.button("🎙️ Start Listening", use_container_width=True, type="primary")

status = st.empty()

if start_btn:
    filename = record_with_vad(status)

    if filename is None:
        status.error("No audio detected. Try again.")
    else:
        result_text = analyze(filename, status)
        status.success("✅ Done!")

        sections = parse_result(result_text)
        st.session_state.history.insert(0, {
            "time": time.strftime("%H:%M:%S"),
            "sections": sections,
            "raw": result_text
        })

# Show history
for i, entry in enumerate(st.session_state.history):
    with st.expander(f"📋 Call at {entry['time']}", expanded=(i == 0)):
        s = entry["sections"]

        if "TRANSLATION" in s:
            st.markdown("### 🔵 Translation")
            st.info(s["TRANSLATION"])

        if "SITUATION" in s:
            st.markdown("### Situation")
            st.write(s["SITUATION"])

        if "REQUIRED" in s:
            st.markdown("### ⚠️ Required Action")
            st.warning(s["REQUIRED"])

        if "OPTIONS" in s and s["OPTIONS"].lower() != "none":
            st.markdown("### 🔢 Button Options")
            st.success(s["OPTIONS"])

        if "SUGGESTED REPLY" in s and s["SUGGESTED REPLY"].lower() != "none":
            st.markdown("### 🟢 Suggested Reply in Japanese")
            st.success(s["SUGGESTED REPLY"])
