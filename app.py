import streamlit as st
import PyPDF2
import re
import pandas as pd
from collections import Counter

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Hukuk Bürosu Paneli", layout="wide", page_icon="⚖️")

# --- FONKSİYONLAR ---

def pdf_metin_oku(dosya):
    """PDF'ten metni çeker."""
    okuyucu = PyPDF2.PdfReader(dosya)
    metin = ""
    # Sadece ilk 5 sayfayı okumak hız kazandırır ve genelde yeterlidir
    for sayfa in okuyucu.pages[:5]:
        metin += sayfa.extract_text() or ""
    return metin

def mahkeme_bul(metin):
    """Metnin başındaki T.C. ... MAHKEMESİ ibaresini arar."""
    kalip = r"(T\.?C\.?.*?MAHKEMESİ)"
    bulunan = re.search(kalip, metin, re.IGNORECASE | re.DOTALL)
    if bulunan:
        return bulunan.group(1).replace("\n", " ").strip()
    return "Mahkeme Belirtilmemiş"

def konu_tahmin_et(metin):
    """Dava türünü tahmin eder."""
    metin_lower = metin.lower()
    
    kategoriler = {
        "Boşanma / Aile": ["boşanma", "velayet", "nafaka", "ziynet", "aile mahkemesi"],
        "İş / Alacak": ["kıdem", "ihbar", "işe iade", "fazla mesai", "sgk", "iş mahkemesi"],
        "Ceza Dosyası": ["sanık", "suç", "ceza", "hapis", "beraat", "ağır ceza", "asliye ceza"],
        "Gayrimenkul": ["tapu", "tahliye", "kira", "ecrimisil", "kadastro"],
        "İcra / Borç": ["icra", "alacak", "borç", "haciz", "taahhüt"]
    }
    
    skorlar = {}
    for kategori, kelimeler in kategoriler.items():
        skor = 0
        for kelime in kelimeler:
            skor += metin_lower.count(kelime)
        skorlar[kategori] = skor
    
    en_yuksek = max(skorlar, key=skorlar.get)
    return en_yuksek if skorlar[en_yuksek] > 0 else "Genel / Belirsiz"

def detayli_analiz(metin, dosya_adi):
    """Tek bir dosya için tüm analizleri yapar."""
    bilgiler = {
        "Dosya Adı": dosya_adi,
        "Mahkeme": mahkeme_bul(metin),
        "Dava Türü": konu_tahmin_et(metin)
    }
    
    aramalar = {
        "Esas No": r"ESAS\s*NO\s*[:;]?\s*(\d{4}/\d+)",
        "Karar No": r"KARAR\s*NO\s*[:;]?\s*(\d{4}/\d+)",
        "Tarih": r"(\d{1,2}[./]\d{1,2}[./]\d{4})",
        "Davacı": r"DAVACI\s*[:;]\s*(.*?)(?=\n)",
        "Davalı": r"DAVALI\s*[:;]\s*(.*?)(?=\n)"
    }
    
    for baslik, kalip in aramalar.items():
        bulunan = re.search(kalip, metin, re.IGNORECASE | re.DOTALL)
        deger = bulunan.group(1).strip()[:100] if bulunan else "-"
        bilgiler[baslik] = deger.replace("\n", " ")
        
    return bilgiler

# --- ARAYÜZ TASARIMI ---

st.title("⚖️ Toplu Dava Yönetim Paneli")
st.markdown("Birden fazla dava dosyasını (PDF) aynı anda yükleyin, sistem hepsini tek tabloda özetlesin.")

# ÇOKLU DOSYA YÜKLEME (accept_multiple_files=True)
uploaded_files = st.file_uploader("Dosyaları Sürükleyip Bırakın (Çoklu Seçim Yapabilirsiniz)", 
                                  type="pdf", 
                                  accept_multiple_files=True)

if uploaded_files:
    tum_veriler = []
    
    # İlerleme Çubuğu (Bar)
    bar = st.progress(0)
    toplam_dosya = len(uploaded_files)
    
    for i, dosya in enumerate(uploaded_files):
        # Her dosyayı sırayla işle
        metin = pdf_metin_oku(dosya)
        if len(metin) > 50:
            veri = detayli_analiz(metin, dosya.name)
            tum_veriler.append(veri)
        
        # İlerleme çubuğunu güncelle
        bar.progress((i + 1) / toplam_dosya)
    
    # Verileri Tabloya (DataFrame) Dönüştür
    df = pd.DataFrame(tum_veriler)
    
    if not df.empty:
        # --- İSTATİSTİK PANELİ (Üst Kısım) ---
        st.write("---")
        col1, col2, col3 = st.columns(3)
        col1.metric("Toplam Dosya", len(df))
        col2.metric("En Çok Görülen Dava", df["Dava Türü"].mode()[0] if not df.empty else "-")
        col3.metric("Tespit Edilen Mahkemeler", df["Mahkeme"].nunique())

        # --- GRAFİKSEL GÖSTERİM ---
        # Sol tarafta Dava Türü Dağılımı
        col_grafik1, col_grafik2 = st.columns([1, 2])
        
        with col_grafik1:
            st.subheader("Dava Türü Dağılımı")
            tur_sayilari = df["Dava Türü"].value_counts()
            st.bar_chart(tur_sayilari)

        with col_grafik2:
            st.subheader("📄 Detaylı Dosya Listesi")
            st.dataframe(df) # İnteraktif tablo
            
        # --- EXCEL İNDİRME ---
        st.write("---")
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Tüm Listeyi Excel (CSV) Olarak İndir",
            data=csv,
            file_name='dava_listesi_ozeti.csv',
            mime='text/csv',
            use_container_width=True
        )
    else:
        st.error("Yüklenen dosyalardan metin okunamadı.")
        
else:
    st.info("👆 Başlamak için yukarıya bir veya daha fazla PDF dosyası bırakın.")

# --- SIDEBAR BİLGİ ---
with st.sidebar:
    st.header("Nasıl Kullanılır?")
    st.write("1. Bilgisayarınızdaki dava klasörüne gidin.")
    st.write("2. İstediğiniz kadar PDF'i seçin.")
    st.write("3. Hepsini buraya sürükleyin.")
    st.success("Sistem otomatik olarak:\n* Mahkemeyi\n* Konuyu\n* Tarafları\nayıklar ve listeler.")
