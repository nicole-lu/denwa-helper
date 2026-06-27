import pyaudio
import struct
import math
import time

p = pyaudio.PyAudio()
s = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)
print("录音中，对着麦克风说话或播放音频，10秒...")
start = time.time()
while time.time() - start < 10:
    data = s.read(1024, exception_on_overflow=False)
    shorts = struct.unpack("1024h", data)
    rms = math.sqrt(sum(x*x for x in shorts) / len(shorts))
    print(f"音量: {rms:.0f}")
s.stop_stream()
s.close()
p.terminate()
