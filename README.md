# GCP ACE Exam Trainer

Google Cloud **Associate Cloud Engineer (ACE)** sertifika sınavına hazırlık için masaüstü pratik uygulaması.
Hazır Türkçe soru bankası, gerçek sınavı taklit eden süreli mod ve ilerleme takibi içerir.
**Tamamen çevrimdışı çalışır**: internet erişimi, hesap veya ek paket gerekmez.

> *English summary: an offline Tkinter desktop quiz app for the Google Cloud Associate Cloud Engineer exam, with a
> built-in bilingual (Turkish/English) question bank, timed exam simulation and progress tracking.
> No dependencies beyond Python.*

## Özellikler

- **360 hazır ACE sorusu (Türkçe + İngilizce)**: [resmi sınav rehberinin](https://services.google.com/fh/files/misc/associate_cloud_engineer_exam_guide_english.pdf)
  alt başlıklarına (1.1–4.2) göre dağıtılmış ve rehberdeki alan ağırlıklarına (%20 / %30 / %30 / %20) yakın;
  14 konu başlığıyla etiketli
  (IAM, Compute Engine, GKE, Cloud Run, VPC, Cloud Storage, veritabanları, Logging/Monitoring…).
  Sorular güncel ürün adlarına göre yazıldı (Artifact Registry, Cloud Run functions, Infrastructure Manager,
  Workload Identity Federation vb.).
- **Türkçe / English / İki dilli**: tüm sorular ve açıklamalar iki dilde. Gerçek sınav İngilizce olduğu için
  sınava yaklaştıkça English modunda çalışmanız önerilir. Herhangi bir soruda `T` tuşuyla dili anında değiştirin.
- **Arayüz dili TR / EN**: ana ekranın sağ üstündeki `TR | EN` düğmesiyle menüler, düğmeler ve mesajlar
  Türkçe ya da İngilizce olur. Soru dili ayrı bir ayardır; örneğin arayüz Türkçe, sorular English olabilir.
- **Pratik modu**: her sorudan sonra anında doğru/yanlış ve açıklama.
- **Sınav simülasyonu**: gerçek sınav gibi süreli (50 soru / 120 dk), sorular alan ağırlıklarına göre dağıtılır,
  işaretleme (⚑) ve soru listesi ile gezinme.
- **Akıllı tekrar**: daha önce yanlış yaptığınız veya hiç görmediğiniz sorulara öncelik; "yalnızca yanlışlarım" modu.
- **İlerleme**: alan bazında başarı oranı ve oturum geçmişi.
- **JSON içe/dışa aktarma**: kendi sorularınızı ekleyin.

## Soruların güvenilirliği

Her hazır soruda, sınav rehberindeki alt başlık kodu (`objective`, ör. `2.3`), doğru cevabı destekleyen **resmi Google Cloud dokümantasyonu linki** (`source_url`) ve o sayfada
geçmesi gereken **anahtar ifadeler** (`check`) bulunur. Pratik modunda açıklamanın altında kaynak linki gösterilir;
şüphelendiğiniz bir soruyu oradan kendiniz doğrulayabilirsiniz.

`tools/check_sources.py` betiği tüm kaynak sayfalarını indirip bu ifadelerin hâlâ dokümanda geçtiğini kontrol eder.
Google dokümanları değiştiğinde hangi soruların gözden geçirilmesi gerektiğini gösterir (internet gerekir;
uygulamanın kendisi çevrimdışı çalışır):

```bash
python tools/check_sources.py
```

Bu kontrol, doğru cevaptaki bilginin resmi kaynakta geçtiğini doğrular; sorunun gerçek sınavla aynı olduğunu garanti
etmez. Sorular özgündür, gerçek sınav soruları değildir. Ek pratik için Google'ın resmi
[örnek soruları](https://cloud.google.com/learn/certification/cloud-engineer) en güvenilir kaynaktır.

### Soru kalitesi kuralları

Sorular gerçek sınav gibi bilgiyle çözülsün, sınav tekniğiyle (ipucu avlayarak) çözülmesin diye
`tests/test_quality.py` şu kuralları denetler:

- Doğru cevap çoğunlukla en uzun şık olmamalı (sorulara göre %30'un altında).
- "always / never / only" gibi kesin ifadeler yanlış şıklarda belirgin şekilde daha sık geçmemeli.
- Doğru cevabın konumu dengeli dağılmalı.
- Bankanın en az %8'i "iki seçenek seçin" tipinde olmalı (şu an 30 soru).
- Aynı kavramı soran neredeyse aynı iki soru olmamalı.

Yeni soru eklerken `python -m unittest discover -s tests` komutunu çalıştırın.

## Kurulum

Tek gereksinim **Python 3.10+**. [python.org](https://www.python.org/downloads/) kurulumu Tkinter'ı içerir;
kurulumda **"Add python.exe to PATH"** seçeneğini işaretleyin.

**Windows:** `start-windows.bat` dosyasına çift tıklayın. Başka kurulum adımı yoktur.
Masaüstünde simgeli bir kısayol isterseniz `create-desktop-shortcut.bat` dosyasını bir kez çalıştırın.

**macOS / Linux:**

```bash
./start.sh
```

veya doğrudan `python3 main.py`. Linux'ta Tkinter yoksa: `sudo apt install python3-tk`

## Klavye kısayolları

| Tuş | İşlev |
|---|---|
| `1`–`5` | Seçenek seç / işaretle |
| `Enter` | Kontrol et / sonraki soru |
| `←` `→` | Önceki / sonraki soru |
| `T` | Sorunun dilini değiştir (Türkçe ⇄ English) |

## Kendi sorularınızı eklemek (JSON)

```json
[
  {
    "exam": "ACE",
    "domain": 2,
    "topic": "Cloud Storage",
    "difficulty": "orta",
    "question": "Soru metni…",
    "options": ["A seçeneği", "B seçeneği", "C seçeneği", "D seçeneği"],
    "correct": [0],
    "explanation": "Neden A doğru…",
    "source_url": "https://cloud.google.com/…",
    "en": {
      "question": "Question text…",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "explanation": "Why A is correct…"
    }
  }
]
```

`correct` 0 tabanlı indeks listesidir; birden fazla doğru cevap için `[0, 2]` gibi yazın.
`en` alanı isteğe bağlıdır; seçenekler Türkçedekiyle aynı sırada olmalıdır. Yoksa soru Türkçe gösterilir.
Seçenekler her oturumda karıştırılır.

## Proje yapısı

```
main.py                 Başlatıcı
examtrainer/exams.py    Sınav tanımları, alanlar ve ağırlıklar
examtrainer/store.py    Soru bankası, istatistik ve ayar dosyaları
examtrainer/engine.py   Soru seçimi, karıştırma, puanlama
examtrainer/gui.py      Tkinter arayüzü
examtrainer/i18n.py     Arayüz metinleri (Türkçe / English)
examtrainer/assets/     Uygulama simgesi
questions/ace.json      Hazır ACE soru bankası
tests/                  Birim testleri (python -m unittest discover -s tests)
tools/check_sources.py  Soruları resmi dokümantasyonla karşılaştırır
data/                   İlerleme verileri (otomatik oluşur, git'e girmez)
```

## Notlar

- Alan adları ve ağırlıkları resmi rehbere göre yaklaşıktır; Google sınavı zaman zaman günceller.
  Güncel rehber: <https://cloud.google.com/learn/certification/cloud-engineer>
- Google geçme notunu açıklamaz; uygulama %70'i hedef olarak kullanır.
- Bu proje Google ile bağlantılı değildir; sorular özgün pratik sorularıdır, gerçek sınav soruları değildir.

## Lisans

[MIT](LICENSE). Google Cloud, Google Cloud Platform ve Associate Cloud Engineer, Google LLC'nin ticari markalarıdır;
bu proje Google ile bağlantılı değildir ve Google tarafından onaylanmamıştır.
