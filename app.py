import streamlit as st
import PyPDF2
import re
import pandas as pd

# Sayfa Ayarları (Geniş görünüm ve Başlık)
st.set_page_config(page_title="Hukuk Asistanı Pro", layout="wide", page_icon="⚖️")

# --- SOL MENÜ (SIDEBAR) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2237/2237936.png", width=100)
    st.title("Hukuk Asistanı")
    st.info("Bu uygulama dava dosyalarını analiz eder ve özet çıkarır.")
    st.warning("⚠️ Veriler sunucuda kaydedilmez, güvenlidir.")
    st.write("---")
    st.write("Geliştirici: [Senin Adın]")

# --- ANA SAYFA ---
st.title("⚖️ Akıllı Dava Analiz Sistemi")
st.markdown("PDF dosyanızı aşağıya bırakın, gerisini sisteme bırakın.")

# Dosya Yükleme Alanı
uploaded_file = st.file_uploader("", type="pdf", help="Sadece PDF dosyaları kabul edilir.")

# --- FONKSİYONLAR ---
def pdf_metin_oku(dosya):
    okuyucu = PyPDF2.PdfReader(dosya)
    metin = ""
    for sayfa in okuyucu.pages:
        metin += sayfa.extract_text() or ""
    return metin

def analiz_et(metin):
    aramalar = {
        "Davacı": r"DAVACI\s*[:;]\s*(.*?)(?=\n)",
        "Davalı": r"DAVALI\s*[:;]\s*(.*?)(?=\n)",
        "Konu": r"KONU\s*[:;]\s*(.*?)(?=\n)",
        "Esas No": r"ESAS\s*NO\s*[:;]?\s*(\d{4}/\d+)",
        "Dava Tarihi": r"(\d{1,2}[./]\d{1,2}[./]\d{4})",
        "Karar/Sonuç": r"(HÜKÜM|KARAR|SONUÇ)\s*[:;]\s*(.*)"
    }
    
    sonuclar = {}
    for baslik, kalip in aramalar.items():
        bulunan = re.search(kalip, metin, re.IGNORECASE | re.DOTALL)
        deger = bulunan.group(1).strip()[:200] if bulunan else "Tespit Edilemedi"
        # Gereksiz satır sonlarını temizle
        sonuclar[baslik] = deger.replace("\n", " ")
    return sonuclar

# --- İŞLEM ALANI ---
if uploaded_file:
    with st.spinner('Dosya okunuyor, lütfen bekleyin...'):
        ham_metin = pdf_metin_oku(uploaded_file)
        
        if len(ham_metin) > 50:
            veriler = analiz_et(ham_metin)
            
            # Verileri Tabloya Çevir (Pandas ile)
            df = pd.DataFrame(list(veriler.items()), columns=["Bilgi Türü", "Tespit Edilen İçerik"])
            
            # İki Kolona Böl: Solda Tablo, Sağda İndirme Butonları
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.subheader("📋 Analiz Sonucu")
                st.table(df) # Şık tablo gösterimi
            
            with col2:
                st.subheader("💾 İşlemler")
                st.write("Bu analizi bilgisayarına kaydet:")
                
                # CSV (Excel) İndirme Butonu
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Excel Olarak İndir (CSV)",
                    data=csv,
                    file_name='dava_ozeti.csv',
                    mime='text/csv',
                )
                
                with st.expander("Ham Metni Göster"):
                    st.text_area("PDF İçeriği", ham_metin, height=200)
                    
            st.success("İşlem Başarıyla Tamamlandı! ✅")
            
        else:
            st.error("❌ Bu PDF okunabilir metin içermiyor. (Resim formatında olabilir)")

else:
    # Dosya yüklenmediyse boş durmasın, bilgi versin
    st.info("👆 Başlamak için yukarıdan bir dosya seçin.")
