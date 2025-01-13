import os
import torchaudio
import torch
import torchaudio.transforms as T
from torchaudio.functional import highpass_biquad, lowpass_biquad
from speechbrain.inference import SpeakerRecognition


# 음악 제거를 위한 개선된 필터 적용 함수
def remove_background_music(audio, sample_rate):
    low_freq = 300.0
    high_freq = 3400.0
    filtered_audio = highpass_biquad(audio, sample_rate, low_freq)
    filtered_audio = lowpass_biquad(filtered_audio, sample_rate, high_freq)
    return filtered_audio


# 기준 음성 학습을 위한 데이터 증강 함수
def augment_audio(audio, sample_rate, augment_iterations=5):
    augments = []
    # 원본 추가
    augments.append(audio)

    for _ in range(augment_iterations):
        # 속도 변환
        speed_up = T.Resample(orig_freq=sample_rate, new_freq=int(sample_rate * 1.1))(audio)
        slow_down = T.Resample(orig_freq=sample_rate, new_freq=int(sample_rate * 0.9))(audio)
        augments.append(speed_up)
        augments.append(slow_down)

        # 볼륨 증강
        louder = audio * (1.0 + 0.25 * torch.rand(1).item())
        quieter = audio * (1.0 - 0.25 * torch.rand(1).item())
        augments.append(louder)
        augments.append(quieter)

        # 피치 변환 (랜덤 편향 추가)
        pitch_up = T.Resample(orig_freq=sample_rate, new_freq=sample_rate)(audio + torch.rand(1).item())
        pitch_down = T.Resample(orig_freq=sample_rate, new_freq=sample_rate)(audio - torch.rand(1).item())
        augments.append(pitch_up)
        augments.append(pitch_down)

    return augments


# 세그먼트와 기준 임베딩 리스트의 평균 유사도 계산
def calculate_similarity(reference_embeddings, segment_embedding):
    similarities = torch.nn.functional.cosine_similarity(
        reference_embeddings, segment_embedding.unsqueeze(0), dim=1
    )
    return similarities.mean().item()


# 학습 반복 횟수 지정
REFERENCE_AUGMENT_ITERATIONS = 5  # reference_audio 학습 반복 횟수
SEGMENT_TRAIN_ITERATIONS = 3  # 입력 오디오 학습 반복 횟수


# 1. 입력 파일 경로
audio_path = r"C:\\DavidProject\\flask_project\\flask_schedular\\pybo\\tts_gen\\voice_20250110_141317.wav"
reference_audio_path = r"C:\\DavidProject\\flask_project\\flask_schedular\\pybo\\tts_gen\\voice_20250110_145052.wav"

# 2. SpeechBrain 모델 로드
recognizer = SpeakerRecognition.from_hparams(source="speechbrain/spkrec-xvect-voxceleb", savedir="speaker_model")

# 3. 기준 음성 파일 로드 및 음악 제거
reference_audio, ref_sample_rate = torchaudio.load(reference_audio_path)
if ref_sample_rate != 16000:
    resample = T.Resample(orig_freq=ref_sample_rate, new_freq=16000)
    reference_audio = resample(reference_audio)
reference_audio = remove_background_music(reference_audio, 16000)

# 기준 화자 임베딩 생성 및 데이터 증강
audio_variants = augment_audio(reference_audio, 16000, augment_iterations=REFERENCE_AUGMENT_ITERATIONS)
reference_embeddings = []
for variant in audio_variants:
    embedding = recognizer.encode_batch(variant).squeeze(0).mean(dim=0)
    reference_embeddings.append(embedding)
reference_embeddings = torch.stack(reference_embeddings)
print(f"Generated {len(reference_embeddings)} augmented embeddings for reference audio.")

# 4. 입력 오디오 파일 로드 및 음악 제거
audio, sample_rate = torchaudio.load(audio_path)
if audio.shape[0] > 1:  # 스테레오 -> 모노 변환
    audio = torch.mean(audio, dim=0, keepdim=True)
if sample_rate != 16000:  # 샘플레이트 변환
    resample = T.Resample(orig_freq=sample_rate, new_freq=16000)
    audio = resample(audio)
    sample_rate = 16000
audio = remove_background_music(audio, 16000)

# 5. 2초씩 나누어 세그먼트 생성 및 비교
segment_duration = 2.0
segment_samples = int(sample_rate * segment_duration)
output_dir = "output_speakers"
os.makedirs(output_dir, exist_ok=True)
similar_segments = []

for iteration in range(SEGMENT_TRAIN_ITERATIONS):  # 입력 오디오 반복 학습
    print(f"Segment training iteration {iteration + 1}/{SEGMENT_TRAIN_ITERATIONS}")
    for start in range(0, audio.shape[1], segment_samples):
        segment = audio[:, start:start + segment_samples]
        if segment.shape[1] == 0:
            continue

        # 세그먼트 임베딩 계산
        embedding_current = recognizer.encode_batch(segment).squeeze(0).mean(dim=0)
        similarity = calculate_similarity(reference_embeddings, embedding_current)

        print(f"Segment {start // segment_samples}, Similarity: {similarity}")
        if similarity > 0.8:  # 임계값을 설정 (높은 유사도만 포함)
            similar_segments.append(segment)
            output_file = os.path.join(output_dir, f"similar_segment_{start // segment_samples:04d}.wav")
            torchaudio.save(output_file, segment, sample_rate)
            print(f"Saved segment {start // segment_samples} as {output_file}")

# 6. 유사 세그먼트를 병합하여 최종 파일 생성
final_output_path = "final_output/target_voice.wav"
os.makedirs("final_output", exist_ok=True)
if similar_segments:
    combined_audio = torch.cat(similar_segments, dim=1)
    torchaudio.save(final_output_path, combined_audio, sample_rate)
    print(f"Saved final combined audio as {final_output_path}")
