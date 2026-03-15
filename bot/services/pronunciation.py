import io
import json
import logging
import re
import wave
from difflib import SequenceMatcher
from typing import Any

import requests

from bot.config import (
    AZURE_SPEECH_KEY,
    AZURE_SPEECH_REGION,
    PRONUN_CLOUD_API_KEY,
    PRONUN_CLOUD_ENABLED,
    PRONUN_LOCAL_ENABLED,
    PRONUN_MAX_AUDIO_BYTES,
    PRONUN_MIN_AUDIO_BYTES,
    PRONUN_MIN_CONFIDENCE,
    PRONUN_TIMEOUT_SEC,
    PRONUN_VOSK_MODEL_PATH,
)

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    text = (text or "").strip().lower()
    text = (
        text.replace("ß", "ss")
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
    )
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        return _levenshtein(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(
                prev[j + 1] + 1,
                curr[j] + 1,
                prev[j] + (0 if ca == cb else 1),
            ))
        prev = curr
    return prev[-1]


def _word_diff(target: str, recognized: str) -> dict[str, Any]:
    t_words = target.split()
    r_words = recognized.split()
    sm = SequenceMatcher(None, t_words, r_words)
    missing = []
    extra = []
    replaced = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "delete":
            missing.extend(t_words[i1:i2])
        elif op == "insert":
            extra.extend(r_words[j1:j2])
        elif op == "replace":
            replaced.append({
                "expected": " ".join(t_words[i1:i2]),
                "got": " ".join(r_words[j1:j2]),
            })
    return {"missing": missing, "extra": extra, "replaced": replaced}


def _score_pronunciation(target_text: str, recognized_text: str) -> dict[str, Any]:
    target = _normalize_text(target_text)
    recognized = _normalize_text(recognized_text)
    if not target:
        return {
            "score": 0,
            "verdict": "Повторить",
            "mistakes": ["Пустой эталонный текст"],
            "tips": ["Передайте слово или фразу для проверки."],
        }

    char_distance = _levenshtein(target, recognized)
    char_total = max(1, len(target))
    char_accuracy = max(0.0, 1.0 - (char_distance / char_total))

    target_words = target.split()
    recognized_words = recognized.split()
    word_distance = _levenshtein(" ".join(target_words), " ".join(recognized_words))
    word_total = max(1, len(" ".join(target_words)))
    word_accuracy = max(0.0, 1.0 - (word_distance / word_total))

    score = int(round((char_accuracy * 0.45 + word_accuracy * 0.55) * 100))

    diff = _word_diff(target, recognized)
    critical_articles = {"der", "die", "das", "ein", "eine", "einen"}
    article_missing = [w for w in diff["missing"] if w in critical_articles]
    if article_missing:
        score = max(0, score - min(15, 5 * len(article_missing)))

    mistakes = []
    if diff["missing"]:
        mistakes.append(f"Пропущено: {', '.join(diff['missing'][:4])}")
    if diff["extra"]:
        mistakes.append(f"Лишнее: {', '.join(diff['extra'][:4])}")
    if diff["replaced"]:
        first_rep = diff["replaced"][0]
        mistakes.append(f"Замена: '{first_rep['expected']}' -> '{first_rep['got']}'")

    tips = []
    if article_missing:
        tips.append("Обратите внимание на артикли (der/die/das/ein/eine).")
    if score < 65:
        tips.append("Скажите фразу медленнее и чуть громче.")
    if "ch" in target_text.lower():
        tips.append("Проверьте звук 'ch' (мягкий выдох).")
    if any(ch in target_text.lower() for ch in ("ä", "ö", "ü")):
        tips.append("Отдельно потренируйте умлауты ä/ö/ü.")

    if score >= 85:
        verdict = "Отлично"
    elif score >= 65:
        verdict = "Хорошо"
    else:
        verdict = "Повторить"

    return {
        "score": score,
        "verdict": verdict,
        "mistakes": mistakes[:3],
        "tips": tips[:3],
    }


def _transcribe_local_vosk(audio_bytes: bytes) -> tuple[str, float] | tuple[None, float]:
    if not PRONUN_LOCAL_ENABLED:
        return None, 0.0
    if not PRONUN_VOSK_MODEL_PATH:
        return None, 0.0
    try:
        from vosk import Model, KaldiRecognizer  # type: ignore
    except Exception:
        logger.info("Vosk is not available; local STT skipped")
        return None, 0.0

    try:
        wf = wave.open(io.BytesIO(audio_bytes), "rb")
    except Exception:
        logger.info("Local STT requires WAV input; skipping local")
        return None, 0.0

    try:
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
            logger.info("Unsupported WAV format for local STT")
            return None, 0.0

        model = Model(PRONUN_VOSK_MODEL_PATH)
        recognizer = KaldiRecognizer(model, wf.getframerate())
        recognizer.SetWords(True)

        conf_values = []
        while True:
            data = wf.readframes(4000)
            if not data:
                break
            if recognizer.AcceptWaveform(data):
                partial = json.loads(recognizer.Result())
                for part in partial.get("result", []):
                    conf_values.append(float(part.get("conf", 0.0)))

        final = json.loads(recognizer.FinalResult())
        text = (final.get("text") or "").strip()
        for part in final.get("result", []):
            conf_values.append(float(part.get("conf", 0.0)))
        confidence = sum(conf_values) / len(conf_values) if conf_values else 0.0
        return text or None, confidence
    except Exception as e:
        logger.warning("Local STT failed: %s", e)
        return None, 0.0
    finally:
        wf.close()


def _transcribe_cloud(audio_bytes: bytes, filename: str, mime_type: str) -> tuple[str, float] | tuple[None, float]:
    """Transcribe audio using OpenAI Whisper (used for basic users)."""
    if not PRONUN_CLOUD_ENABLED:
        return None, 0.0
    if not PRONUN_CLOUD_API_KEY:
        logger.warning("Cloud STT enabled but API key is missing")
        return None, 0.0

    try:
        resp = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {PRONUN_CLOUD_API_KEY}"},
            data={"model": "whisper-1", "language": "de", "response_format": "verbose_json"},
            files={"file": (filename, audio_bytes, mime_type or "application/octet-stream")},
            timeout=PRONUN_TIMEOUT_SEC,
        )
        if not resp.ok:
            logger.warning("Cloud STT HTTP %s: %s", resp.status_code, resp.text[:200])
            return None, 0.0
        payload = resp.json()
        text = (payload.get("text") or "").strip()
        return (text or None), 0.85 if text else 0.0
    except Exception as e:
        logger.warning("Cloud STT failed: %s", e)
        return None, 0.0


def _transcribe_and_assess_azure(
    audio_bytes: bytes, target_text: str,
) -> dict[str, Any] | None:
    """Use Azure Pronunciation Assessment for phoneme-level scoring."""
    if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
        logger.warning("Azure Speech key/region not configured")
        return None

    try:
        import azure.cognitiveservices.speech as speechsdk  # type: ignore
    except Exception:
        logger.info("Azure Speech SDK not available; skipping Azure assessment")
        return None

    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION,
        )
        speech_config.speech_recognition_language = "de-DE"

        audio_format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=16000, bits_per_sample=16, channels=1,
        )
        push_stream = speechsdk.audio.PushAudioInputStream(stream_format=audio_format)

        # Strip 44-byte WAV header to get raw PCM
        pcm_data = audio_bytes[44:] if len(audio_bytes) > 44 else audio_bytes
        push_stream.write(pcm_data)
        push_stream.close()

        audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

        pronunciation_config = speechsdk.PronunciationAssessmentConfig(
            reference_text=target_text,
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
            enable_miscue=True,
        )
        pronunciation_config.enable_prosody_assessment()

        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config, audio_config=audio_config,
        )
        pronunciation_config.apply_to(recognizer)

        result = recognizer.recognize_once()

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            pron = speechsdk.PronunciationAssessmentResult(result)
            words_data = []
            for w in pron.words:
                phonemes = []
                for p in w.phonemes:
                    phonemes.append({
                        "phoneme": p.phoneme,
                        "accuracy_score": round(p.accuracy_score, 1),
                    })
                words_data.append({
                    "word": w.word,
                    "accuracy_score": round(w.accuracy_score, 1),
                    "error_type": w.error_type,
                    "phonemes": phonemes,
                })

            return {
                "recognized_text": result.text.strip(),
                "confidence": round(pron.pronunciation_score / 100.0, 3),
                "azure_assessment": {
                    "accuracy_score": round(pron.accuracy_score, 1),
                    "fluency_score": round(pron.fluency_score, 1),
                    "completeness_score": round(pron.completeness_score, 1),
                    "pronunciation_score": round(pron.pronunciation_score, 1),
                    "words": words_data,
                },
            }

        if result.reason == speechsdk.ResultReason.NoMatch:
            logger.info("Azure: no speech recognized")
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            logger.warning("Azure cancelled: %s — %s", cancellation.reason, cancellation.error_details)
        return None

    except Exception as e:
        logger.warning("Azure pronunciation assessment failed: %s", e)
        return None


def _azure_to_legacy_analysis(azure_data: dict, target_text: str) -> dict[str, Any]:
    """Convert Azure assessment to legacy score/verdict/mistakes/tips format."""
    assessment = azure_data["azure_assessment"]
    score = int(round(assessment["pronunciation_score"]))

    mistakes = []
    weak_phonemes = []
    for w in assessment["words"]:
        if w["error_type"] == "Omission":
            mistakes.append(f"Пропущено: {w['word']}")
        elif w["error_type"] == "Insertion":
            mistakes.append(f"Лишнее: {w['word']}")
        elif w["error_type"] == "Mispronunciation":
            bad = [p for p in w["phonemes"] if p["accuracy_score"] < 60]
            if bad:
                phoneme_str = ", ".join(p["phoneme"] for p in bad[:3])
                mistakes.append(f"'{w['word']}': звуки [{phoneme_str}]")
                weak_phonemes.extend(bad)
            else:
                mistakes.append(f"Неточно: '{w['word']}'")

    tips = []
    if assessment["fluency_score"] < 70:
        tips.append("Говорите плавнее, без долгих пауз между словами.")
    if assessment["completeness_score"] < 80:
        tips.append("Произнесите все слова из фразы.")
    if score < 65:
        tips.append("Скажите фразу медленнее и чуть громче.")
    if any(ch in target_text.lower() for ch in ("ä", "ö", "ü")):
        for w in assessment["words"]:
            if w["accuracy_score"] < 70 and any(ch in w["word"].lower() for ch in ("ä", "ö", "ü")):
                tips.append("Отдельно потренируйте умлауты ä/ö/ü.")
                break
    if "ch" in target_text.lower():
        for w in assessment["words"]:
            if w["accuracy_score"] < 70 and "ch" in w["word"].lower():
                tips.append("Проверьте звук 'ch' (мягкий выдох).")
                break

    if score >= 85:
        verdict = "Отлично"
    elif score >= 65:
        verdict = "Хорошо"
    else:
        verdict = "Повторить"

    return {
        "score": score,
        "verdict": verdict,
        "mistakes": mistakes[:3],
        "tips": tips[:3],
    }


def evaluate_pronunciation(
    *,
    audio_bytes: bytes,
    filename: str,
    mime_type: str,
    target_text: str,
    is_premium: bool = False,
) -> dict[str, Any]:
    if not target_text.strip():
        raise ValueError("target_text is required")
    if len(audio_bytes) < PRONUN_MIN_AUDIO_BYTES:
        raise ValueError("Аудио слишком короткое")
    if len(audio_bytes) > PRONUN_MAX_AUDIO_BYTES:
        raise ValueError("Аудио слишком большое")

    # Premium path: Azure Pronunciation Assessment (phoneme-level analysis)
    if is_premium and AZURE_SPEECH_KEY and AZURE_SPEECH_REGION:
        azure_result = _transcribe_and_assess_azure(audio_bytes, target_text)
        if azure_result:
            analysis = _azure_to_legacy_analysis(azure_result, target_text)
            return {
                "recognized_text": azure_result["recognized_text"],
                "score": analysis["score"],
                "verdict": analysis["verdict"],
                "mistakes": analysis["mistakes"],
                "tips": analysis["tips"],
                "engine": "cloud_azure",
                "confidence": azure_result["confidence"],
                "fallback_used": False,
                "azure_assessment": azure_result["azure_assessment"],
            }
        logger.warning("Azure assessment returned no result; falling back to OpenAI Whisper")

    # Basic path (and premium fallback): OpenAI Whisper + text-based scoring
    recognized_text = None
    confidence = 0.0
    engine = "none"
    fallback_used = False

    local_text, local_conf = _transcribe_local_vosk(audio_bytes)
    if local_text:
        recognized_text = local_text
        confidence = local_conf
        engine = "local_vosk"

    need_cloud = (not recognized_text) or (confidence < PRONUN_MIN_CONFIDENCE)
    if need_cloud and PRONUN_CLOUD_ENABLED:
        cloud_text, cloud_conf = _transcribe_cloud(audio_bytes, filename, mime_type)
        if cloud_text:
            recognized_text = cloud_text
            confidence = cloud_conf
            engine = "cloud_openai"
            fallback_used = local_text is not None

    if not recognized_text:
        raise RuntimeError("Не удалось распознать речь. Попробуйте ещё раз.")

    analysis = _score_pronunciation(target_text, recognized_text)
    return {
        "recognized_text": recognized_text,
        "score": analysis["score"],
        "verdict": analysis["verdict"],
        "mistakes": analysis["mistakes"],
        "tips": analysis["tips"],
        "engine": engine,
        "confidence": round(confidence, 3),
        "fallback_used": fallback_used,
    }
