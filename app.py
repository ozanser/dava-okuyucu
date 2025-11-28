import streamlit as st
import PyPDF2
import re
import pandas as pd
from collections import Counter

# Sayfa Ayarları
st.set_page_config(page_title="Akıllı Hukuk Asistanı", layout="wide", page_icon="⚖️")

# --- SOL MENÜ ---
with st.sidebar:
    st.title("⚖️ Hukuk Asistanı")
    st.info("Bu sürüm 'Konu' kısmını metin içeriğine göre tahmin eder.")
    st.write("---")

# --- ANA SAYFA ---
st.title("📄 Gelişmiş Dava Analizcisi")
st.markdown("PDF dosyanızı yükleyin, sistem davanın türünü ve detaylarını çıkarsın.")

uploaded_file = st.file_uploader("", type="pdf")

# --- AKILLI FONKSİYONLAR ---

def pdf_metin_oku(dosya):
    okuyucu = PyPDF2.PdfReader(dosya)
    metin = ""
    for sayfa in okuyucu.pages:
        metin += sayfa.extract_text() or ""
    return metin

def konu_tahmin_et(metin):
    """
    Önce başlık arar, bulamazsa kelime sayarak tahmin yürütür.
    """
    metin_lower = metin.lower()
    
    # 1. YÖNTEM: Açıkça yazılmış başlık ara
    baslik_kalibi = r"(?i)(KONU|DAVA KONUSU|TALEP KONUSU)\s*[:;]\s*(.*?)(?=\n|AÇIKLAMA)"
    bulunan = re.search(baslik_kalibi, metin, re.DOTALL)
    
    if bulunan:
        # Başlık bulduysa temizleyip döndür
        return bulunan.group(2).strip()[:200].replace("\n", " ")
    
    # 2. YÖNTEM: Başlık yoksa, kelime avına çık (Puanlama Sistemi)
    # Hangi kelime hangi dava türüne işaret eder?
    kategoriler = {
        "Boşanma / Aile Hukuku": ["boşanma", "velayet", "nafaka", "ziynet", "mal rejimi", "evlilik birliği"],
        "İş Hukuku / Alacak": ["kıdem", "ihbar", "fazla mesai", "işe iade", "iş akdi", "maaş"],
        "Ceza Hukuku": ["sanık", "suç", "ceza", "hapis", "beraat", "hakaret", "tehdit", "yaralama"],
        "Gayrimenkul / Tapu": ["tapu", "tahliye", "kira", "ecrimisil", "arsa", "kamulaştırma"],
        "Borçlar / Ticaret": ["alacak", "senet", "fatura", "icra", "itirazın iptali", "tazminat"]
    }
    
    skorlar = {}
    
    for kategori, kelimeler in kategoriler.items():
        skor = 0
        for kelime in kelimeler:
            skor += metin_lower.count(kelime)
        skorlar[kategori] = skor
    
    # En yüksek puanı alan kategoriyi bul
    en_yuksek_kategori = max(skorlar, key=skorlar.get)
    
    # Eğer hiçbiri geçmiyorsa (Skor 0 ise)
    if skorlar[en_yuksek_kategori] == 0:
        return "Genel Hukuk Davası (Konu tespit edilemedi)"
    
    return f"{en_yuksek_kategori} (Otomatik Tespit)"

def analiz_et(metin):
    # Standart verileri çek
    aramalar = {
        "Davacı": r"DAVACI\s*[:;]\s*(.*?)(?=\n)",
        "Davalı": r"DAVALI\s*[:;]\s*(.*?)(?=\n)",
        "Esas No": r"ESAS\s*NO\s*[:;]?\s*(\d{4}/\d+)",
        "Karar/Sonuç": r"(HÜKÜM|KARAR|SONUÇ)\s*[:;]\s*(.*)"
    }
    
    sonuclar = {}
    
    # Regex ile standart verileri al
    for baslik, kalip in aramalar.items():
        bulunan = re.search(kalip, metin, re.IGNORECASE | re.DOTALL)
        deger = bulunan.group(1).strip()[:200] if bulunan else "-"
        sonuclar[baslik] = deger.replace("\n", " ")
    
    # Konuyu özel fonksiyonumuzla bul
    sonuclar["Konu / Dava Türü"] = konu_tahmin_et(metin)
    
    return sonuclar

# --- ÇALIŞTIRMA ---
if uploaded_file:
    metin = pdf_metin_oku(uploaded_file)
    if len(metin) > 50:
        veriler = analiz_et(metin)
        
        # Ekrana Yazdır
        st.subheader("📋 Analiz Sonuçları")
        
        # Özel vurgulu gösterim (Metrics)
        col1, col2 = st.columns(2)
        col1.success(f"**Tespit Edilen Konu:**\n\n{veriler['Konu / Dava Türü']}")
        col2.info(f"**Esas No:** {veriler['Esas No']}")
        
        # Diğer detaylar tablo olarak
        df = pd.DataFrame(list(veriler.items()), columns=["Alan", "Bilgi"])
        st.table(df)
        
    else:
        st.error("Metin okunamadı.")
