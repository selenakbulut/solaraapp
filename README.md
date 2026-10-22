# GES Saatlik Üretim Tahmin Motoru

Python, Streamlit ve SQLite kullanılarak geliştirilen, güneş enerjisi santralleri için **saatlik üretim tahmini** uygulaması.

> **Durum:** Model ve yazılımın kabul testleri geliştirme ortamında çalıştırılmıştır. Tarihsel Open-Meteo hava verilerinden hesaplanan üretimler **gerçekleşmiş santral üretimi değildir**. Gerçek saatlik üretim verileriyle model doğruluk değerlendirmesi henüz tamamlanmamıştır.

## Özellikler

- Santral ekleme ve teknik bilgilerini yönetme: konum, panel sayısı ve gücü, inverter AC gücü, panel eğimi, azimut ve yaş.
- Open-Meteo üzerinden saatlik hava tahmini ve geçmiş hava verilerini alma.
- Panel düzlemi ışınımı, hücre sıcaklığı, DC/AC kayıpları, inverter verimliliği, panel yaşlanması ve **clipping** etkilerini hesaba katarak saatlik kWh tahmini üretme.
- Saatlik ve günlük sonuçları grafik/tablo olarak görüntüleme; CSV/Excel dışa aktarma.
- SQLite üzerinden hava verisi önbelleği, API istek sayısı takibi ve kaydedilmiş tahminlere erişim.
- Saha bazlı kayıp katsayıları ve geçmiş gerçekleşen üretim verisiyle karşılaştırma için altyapı.

## Teknolojiler

Python 3, Streamlit, SQLite, Open-Meteo API, Pandas, Requests, Altair, Matplotlib, OpenPyXL.

## Kurulum (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python database.py
python -m streamlit run app.py
```

İlk çalıştırmada yerel veritabanı ve santral kayıtları ortamda bulunmayabilir. Gereken saha bilgileri uygulama üzerinden girilir. Uygulamanın standart yerel veritabanı `solar.db` dosyasıdır.

## Model varsayımları

Mevcut temel modelde varsayılan toplam DC kaybı **%5**, toplam AC kaybı **%2**, panel yaşlanma oranı **yıllık %0,5**, NOCT **45 °C** ve sıcaklık katsayısı **−0,004/°C** olarak kullanılır. Sahaya özel kayıp katsayıları varsa ilgili varsayımların yerine bu katsayılar uygulanabilir.

Bunlar başlangıç kabulleridir; üç santralin gerçek ölçümleriyle henüz kalibre edilmemiştir. Çıkıştaki saatlik enerji, bir saatlik aralık için **kWh** birimindedir.

## Testler

PyCharm projesinde mevcut test dosyası `test_faz1_sahalar1.py` olarak adlandırılmıştır:

```powershell
python -m unittest -v test_solar_model.py test_faz1_sahalar1.py
```

Ek yardımcı testler:

```powershell
python test_weather_cache_offline.py
```

**Test verisi notu:** Bazı testler `solar.db` içindeki tarihsel hava kayıtlarına ihtiyaç duyar. Yıllık kabul testi ayrıca geçici `solar_yillik_test.db` dosyasına ve 2025 yılına ait üç saha için 8.760'ar saatlik kayda ihtiyaç duyar. `.db` dosyaları GitHub'a yüklenmez. Geçici veritabanı mevcut değilse yıllık testin **atlanması (`skipped`)**, testin başarıyla gerçekleştirildiği anlamına gelmez. Temiz bir GitHub kurulumunda test sonuçları bu nedenle yerel geliştirme ortamındaki sonuçlardan farklı olabilir.


## Veri ve güvenlik

Hava verisi sağlayıcısı: [Open-Meteo](https://open-meteo.com/). Uygulamanın özellikle kurum içi veya ticari kullanımı için Open-Meteo'nun güncel [lisans ve kullanım koşulları](https://open-meteo.com/en/terms) ayrıca kontrol edilmelidir.
