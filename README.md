# Ders Notu Otomasyonu V0.5 (Gemini)

Bu sürüm OpenAI yerine **Google Gemini** kullanır.  
Ücretsiz API anahtarı ile çalışır (Google AI Studio).

## Ne değişti? (V0.4 → V0.5)
- OpenAI tamamen kaldırıldı, yerine **Gemini** eklendi.
- Varsayılan model: `gemini-2.5-flash` (ücretsiz katmanda iyi vision + hızlı).
- Ortam değişkeni artık `GEMINI_API_KEY`.
- JSON çıktısı Gemini’nin `response_mime_type="application/json"` özelliği ile daha stabil.
- Bağımlılık: `google-genai` (resmi SDK).

## Ücretsiz API Anahtarı Alma (1 dakika)

1. https://aistudio.google.com/apikey adresine git
2. Google hesabınla giriş yap
3. **Create API key** → bir proje seç veya yeni oluştur
4. Anahtarı kopyala

Kredi kartı istemez. Günlük ücretsiz limit vardır (Flash modelleri için genellikle yeterlidir).

## Bilgisayarda çalıştırma

### Windows PowerShell
```powershell
cd ders_notu_otomasyonu_v0_4
py -m pip install -r requirements.txt
$env:GEMINI_API_KEY="BURAYA_API_ANAHTARINIZ"
$env:GEMINI_MODEL="gemini-2.5-flash"   # isteğe bağlı
py app.py
```

### Linux / macOS
```bash
cd ders_notu_otomasyonu_v0_4
python3 -m pip install -r requirements.txt
export GEMINI_API_KEY="BURAYA_API_ANAHTARINIZ"
export GEMINI_MODEL="gemini-2.5-flash"   # isteğe bağlı
python3 app.py
```

Sonra aynı bilgisayarda:
`http://127.0.0.1:5000`

## Telefonda aynı Wi-Fi üzerinden kullanma

Bilgisayarda uygulama çalışırken bilgisayarın yerel IP adresini öğrenin (ör. `192.168.1.20`).
Telefonda tarayıcıdan:
`http://192.168.1.20:5000`

Windows güvenlik duvarı bağlantıyı engellerse 5000 portuna yerel ağ erişimi izni gerekebilir.

## Önemli

- API anahtarını **asla** `index.html` içine yazmayın.
- ZIP dosyasını doğrudan `content://` veya `file://` ile açmak sadece PDF önizlemesini çalıştırır. AI analizi için Flask sunucusunun çalışması gerekir.
- Ücretsiz katmanda günlük istek limiti vardır. Çok fazla sayfa analiz ediyorsanız limit dolabilir; o zaman birkaç saat bekleyin veya bir sonraki güne geçin.

## Sağlık kontrolü

Tarayıcıda `/api/health` açıldığında örneğin:
```json
{
  "ok": true,
  "api_key_configured": true,
  "model": "gemini-2.5-flash",
  "provider": "gemini",
  "message": "Sunucu hazır."
}
```
görmelisiniz.

## Desteklenen modeller (ücretsiz katman örnekleri)

| Model                  | Not                          |
|------------------------|------------------------------|
| `gemini-2.5-flash`     | Varsayılan, dengeli          |
| `gemini-2.0-flash`     | Daha eski, hâlâ iyi          |
| `gemini-2.5-flash-lite`| Daha hızlı / daha ucuz limit |

Model değiştirmek için:
```bash
export GEMINI_MODEL="gemini-2.0-flash"
```
