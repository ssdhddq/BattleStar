from scipy.io import wavfile
import noisereduce as nr
from pydub import AudioSegment

def reduce_noise(input_path, output_path):
    sound = AudioSegment.from_mp3(input_path)
    sound.export("Recording.wav", format="wav")

    rate, data = wavfile.read('Recording.wav')
    if len(data.shape) > 1:
        data = data[:, 0]

    reduced_noise = nr.reduce_noise(y=data, sr=rate)
    wavfile.write(output_path, rate, reduced_noise)