import os
import torchaudio
import torch
import torchaudio.transforms as T
from speechbrain.inference import SpeakerRecognition
from speechbrain.inference import VAD

# 1. 입력 오디오 파일 경로
audio_path = r"C:\DavidProject\flask_project\flask_schedular\pybo\tts_gen\voice_20250110_141317.wav"

# 2. SpeechBrain의 SpeakerRecognition 모델 로드
recognizer = SpeakerRecognition.from_hparams(source="speechbrain/spkrec-xvect-voxceleb", savedir="speaker_model")

# VAD 모델 로드
vad_model = VAD.from_hparams(source="speechbrain/vad-crdnn-libriparty", savedir="vad_model")

# 3. 오디오 파일 로드
audio, sample_rate = torchaudio.load(audio_path)
print(f"Loaded audio with shape: {audio.shape}, Sample rate: {sample_rate}")

# 다중 채널 오디오를 단일 채널로 변환 (평균)
if audio.shape[0] > 1:  # 스테레오 데이터인 경우
    audio = torch.mean(audio, dim=0, keepdim=True)  # 단일 채널로 변환
    print(f"Converted to mono. New shape: {audio.shape}")

# 4. 샘플레이트 변환 (VAD 모델 요구 샘플레이트: 16kHz)
required_sample_rate = 16000
if sample_rate != required_sample_rate:
    resample = T.Resample(orig_freq=sample_rate, new_freq=required_sample_rate)
    audio = resample(audio)
    sample_rate = required_sample_rate
    print(f"Resampled audio to {required_sample_rate} Hz")

# 5. 텐서를 임시 WAV 파일로 저장
temp_audio_path = "temp_audio.wav"
torchaudio.save(temp_audio_path, audio, sample_rate)

# 6. VAD를 사용하여 음성 구간 탐지
print("Detecting speech segments using VAD...")
boundaries = vad_model.get_speech_segments(temp_audio_path)
print(f"Detected {len(boundaries)} speech segments.")

# 7. 화자별 세그먼트 저장
output_dir = "output_speakers"
os.makedirs(output_dir, exist_ok=True)

threshold = 0.7  # 코사인 유사도 임계값
speaker_segments = {0: [], 1: []}  # 화자별 세그먼트 저장

# 화자 구분을 위해 첫 번째 세그먼트의 임베딩 계산
first_segment_start, first_segment_end = boundaries[0]
first_segment = audio[:, int(first_segment_start * sample_rate):int(first_segment_end * sample_rate)]
embedding_reference = recognizer.encode_batch(first_segment).squeeze(0).mean(dim=0)  # (512,)
print(f"Reference embedding shape: {embedding_reference.shape}")

for i, (start, end) in enumerate(boundaries):
    print(f"Processing segment {i} from {start:.2f}s to {end:.2f}s")

    segment = audio[:, int(start * sample_rate):int(end * sample_rate)]
    if segment.shape[1] == 0:  # 빈 세그먼트 스킵
        print(f"Skipping empty segment {i}")
        continue

    # 현재 세그먼트의 임베딩 계산
    embedding_current = recognizer.encode_batch(segment).squeeze(0).mean(dim=0)  # (512,)
    print(f"Segment {i} embedding shape: {embedding_current.shape}")

    # 코사인 유사도 계산
    similarity = torch.nn.functional.cosine_similarity(
        embedding_reference.unsqueeze(0),  # (1, 512)
        embedding_current.unsqueeze(0),  # (1, 512)
        dim=1  # 배치 차원에 대해 계산
    ).item()

    print(f"Segment {i}, Similarity: {similarity}")

    # 화자 ID 결정
    speaker_id = 0 if similarity > threshold else 1
    speaker_segments[speaker_id].append(segment)
    output_file = os.path.join(output_dir, f"voice{speaker_id + 1}_{i:04d}.wav")
    torchaudio.save(output_file, segment, sample_rate)
    print(f"Saved segment {i} as {output_file}")

# 8. 화자별 파일 통합
final_output_dir = "final_output"
os.makedirs(final_output_dir, exist_ok=True)

for speaker_id, segments in speaker_segments.items():
    if segments:
        combined_audio = torch.cat(segments, dim=1)  # 화자별 세그먼트 병합
        output_file = os.path.join(final_output_dir, f"voice{speaker_id + 1}.wav")
        torchaudio.save(output_file, combined_audio, sample_rate)
        print(f"Saved final combined audio for Speaker {speaker_id + 1} as {output_file}")

# 9. 임시 파일 삭제
os.remove(temp_audio_path)
