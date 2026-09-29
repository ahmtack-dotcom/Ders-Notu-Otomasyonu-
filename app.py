import os
import base64
import json
import re
from flask import Flask, request, jsonify, send_from_directory
from google import genai
from google.genai import types

APP_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=".", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 55 * 1024 * 1024

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()

SYSTEM = """Sen ders notu analiz eden bir eğitim asistanısın.
Yüklenen PDF sayfalarının görüntülerini incele. El yazısı, basılı metin, tablo,
şema, başlık, renkli kutu ve görselleri birlikte değerlendir.

TEMEL KURAL:
- Sadece görüntülerde gerçekten desteklenen bilgileri çıkar.
- Kullanıcının seçtiği sınıf, ders ve üniteyi bağlam olarak kullan.
- Görüntüde olmayan bilgiyi genel bilgiden ekleme.
- Okunamayan/şüpheli bir bölüm varsa tahmin etmek yerine uncertain alanına yaz.
- Aynı konuyu farklı sayfalarda tekrar ediyorsa birleştir.
- Türkçe cevap ver.

Yalnızca geçerli JSON döndür:
{
  "topics": [{"title": "...", "detail": "...", "status": "desteklendi|kısmen_desteklendi|belirsiz"}],
  "important_points": ["..."],
  "vocabulary": [{"term": "...", "meaning": "..."}],
  "uncertain": ["..."]
}
"""


def get_client():
    if not GEMINI_API_KEY:
        raise RuntimeError("Sunucuda GEMINI_API_KEY tanımlı değil.")
    return genai.Client(api_key=GEMINI_API_KEY)


def clean_json_text(text: str):
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b < 0:
        raise ValueError("AI geçerli JSON döndürmedi.")
    return json.loads(text[a : b + 1])


def parse_data_url(data_url: str):
    """data:image/jpeg;base64,... → (mime_type, raw_bytes)"""
    if not data_url or not data_url.startswith("data:"):
        raise ValueError("Geçersiz görüntü formatı (data URL bekleniyor).")
    header, b64data = data_url.split(",", 1)
    mime = "image/jpeg"
    if ";" in header:
        mime = header.split(";")[0].replace("data:", "").strip() or mime
    return mime, base64.b64decode(b64data)


def call_gemini(images, task: str, force_json: bool = True) -> str:
    client = get_client()

    parts = [types.Part.from_text(text=task)]
    for item in images:
        data_url = item.get("image") or item.get("data") or ""
        mime, raw = parse_data_url(data_url)
        parts.append(types.Part.from_bytes(data=raw, mime_type=mime))

    config_kwargs = {
        "system_instruction": SYSTEM,
        "temperature": 0.2,
    }
    if force_json:
        config_kwargs["response_mime_type"] = "application/json"

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=parts,
        config=types.GenerateContentConfig(**config_kwargs),
    )

    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("Gemini yanıtında metin bulunamadı.")
    return text


def normalize(obj):
    return {
        "topics": obj.get("topics", []) if isinstance(obj, dict) else [],
        "important_points": obj.get("important_points", []) if isinstance(obj, dict) else [],
        "vocabulary": obj.get("vocabulary", []) if isinstance(obj, dict) else [],
        "uncertain": obj.get("uncertain", []) if isinstance(obj, dict) else [],
    }


def merge_results(results):
    topics, points, vocab, uncertain = [], [], [], []
    seen_topics, seen_vocab, seen_points = set(), set(), set()

    for obj in results:
        obj = normalize(obj)
        for t in obj["topics"]:
            title = str(t.get("title", t) if isinstance(t, dict) else t).strip()
            key = re.sub(r"\s+", " ", title.lower())
            if title and key not in seen_topics:
                seen_topics.add(key)
                topics.append(
                    t
                    if isinstance(t, dict)
                    else {"title": title, "detail": "", "status": "desteklendi"}
                )
        for p in obj["important_points"]:
            p = str(p).strip()
            key = p.lower()
            if p and key not in seen_points:
                seen_points.add(key)
                points.append(p)
        for v in obj["vocabulary"]:
            term = str(v.get("term", "") if isinstance(v, dict) else v).strip()
            key = term.lower()
            if term and key not in seen_vocab:
                seen_vocab.add(key)
                vocab.append(
                    v if isinstance(v, dict) else {"term": term, "meaning": ""}
                )
        for u in obj["uncertain"]:
            u = str(u).strip()
            if u and u not in uncertain:
                uncertain.append(u)

    return {
        "topics": topics,
        "important_points": points,
        "vocabulary": vocab,
        "uncertain": uncertain,
    }


@app.get("/")
def home():
    return send_from_directory(APP_DIR, "index.html")


@app.get("/api/health")
def health():
    return jsonify(
        {
            "ok": True,
            "api_key_configured": bool(GEMINI_API_KEY),
            "model": GEMINI_MODEL,
            "provider": "gemini",
            "message": (
                "Sunucu hazır."
                if GEMINI_API_KEY
                else "Sunucu çalışıyor ancak GEMINI_API_KEY tanımlı değil."
            ),
        }
    )


@app.post("/api/analyze")
def analyze():
    d = request.get_json(force=True, silent=False) or {}
    images = d.get("pages", [])
    if not images:
        return jsonify(error="Sayfa görüntüsü bulunamadı."), 400
    if len(images) > 12:
        images = images[:12]

    grade = d.get("grade", "")
    subject = d.get("subject", "")
    unit = d.get("unit", "")

    results = []
    batch_size = 3
    try:
        for start in range(0, len(images), batch_size):
            batch = images[start : start + batch_size]
            nums = ", ".join(str(x.get("page", "?")) for x in batch)
            task = f"""Sınıf: {grade}
Ders: {subject}
Ünite: {unit}

Bu mesajdaki {len(batch)} PDF sayfasını birlikte incele (sayfa: {nums}).
El yazısı notları okumaya özellikle dikkat et.
Başlıkları, alt başlıkları, önemli tanımları, maddeleri ve sayfalardaki terimleri çıkar.
Aynı sayfadaki görselin açıklamayı destekleyip desteklemediğini dikkate al.
Bu sayfalardan desteklenmeyen konu veya bilgi ekleme.
Yalnızca JSON döndür."""
            raw = call_gemini(batch, task, force_json=True)
            results.append(clean_json_text(raw))

        merged = merge_results(results)
        merged["pages_read"] = len(images)
        merged["batches"] = len(results)
        merged["model"] = GEMINI_MODEL
        return jsonify(merged)
    except Exception as e:
        return (
            jsonify(
                error=str(e),
                hint="/api/health adresinden sunucu durumunu kontrol edin.",
            ),
            500,
        )


@app.post("/api/draft")
def draft():
    d = request.get_json(force=True) or {}
    analysis = json.dumps(d.get("analysis", {}), ensure_ascii=False)
    if not GEMINI_API_KEY:
        return jsonify(error="Sunucuda GEMINI_API_KEY tanımlı değil."), 500

    task = f"""Sınıf: {d.get('grade')}
Ders: {d.get('subject')}
Ünite: {d.get('unit')}

Aşağıdaki görüntü analizi sonucunu öğretmen kontrollü ders notu taslağına dönüştür.
Kaynak analizde olmayan bilgi ekleme. Öğrenci seviyesine uygun kısa ve açık Türkçe kullan.
Şu bölümleri oluştur:
1) KONU BAŞLIKLARI
2) KISA KONU ÖZETİ
3) DİKKAT / UNUTMA
4) SINAV TAKTİĞİ (yalnızca kaynak bunu destekliyorsa)
5) ÖNEMLİ KELİMELER
Belirsiz noktaları kesin bilgi gibi yazma.

AI GÖRÜNTÜ ANALİZİ:
{analysis}"""
    try:
        # Taslak metin olduğu için JSON zorunlu değil
        raw = call_gemini([], task, force_json=False)
        return jsonify(draft=raw)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.errorhandler(413)
def too_large(_):
    return jsonify(error="Gönderilen veri çok büyük. Sayfa görüntüleri sıkıştırılmalı."), 413


if __name__ == "__main__":
    # Telefon/aynı Wi-Fi üzerindeki başka cihazlardan erişilebilmesi için 0.0.0.0
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
