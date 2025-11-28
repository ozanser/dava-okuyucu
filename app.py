import streamlit as st
import PyPDF2
import re
import pandas as pd
import os

# --- 1. AYARLAR ---
st.set_page_config(page_title="Öğrenen Hukuk Asistanı", layout="wide", page_icon="🧠")
VERITABANI_DOSYASI = "dogrulanmis_veri.csv"

# --- 2. CSS TASARIMI ---
st.markdown("""
<style>
    .stSuccess { background-color: #d4edda; border-left: 5px solid #28a745; }
    .stError { background-color: #f8d7da; border-left: 5px solid #dc3545; }
    .big-font { font-size:20px !important; font-weight: bold; }
    /* Form alanlarını belirginleştir */
    div[data-testid="stForm"] {
        border: 2px solid #f0f2f6;
        padding: 20px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. FONKSİYONLAR ---

def veritabani_yukle():
    """Varsa eski kayıtları yükler, yoksa boş yaratır."""
    if os.path.exists(VERITABANI_DOSYASI):
        return pd.read_csv(VERITABANI_DOSYASI)
    else:
        # Sütunları netleştiriyoruz
        return pd.DataFrame(columns=["Dosya Adı", "Mahkeme", "Esas No", "Karar No", 
                                     "Davacı", "Davalı", "Sonuç", "Vekalet Ücreti"])

def veritabanina_kaydet(yeni_veri):
    """Kullanıcının düzelttiği veriyi CSV'ye ekler."""
    df = veritabani_yukle()
    yeni_satir = pd.DataFrame([yeni_veri])
    df = pd.concat([df, yeni_satir], ignore_index=True)
    df.to_csv(VERITABANI_DOSYASI, index=False)
    return df

def metni_temizle(metin):
    duzeltmeler = {
        r"HAK M": "HAKİM", r"KAT P": "KATİP", r"VEK L": "VEKİL",
        r"T RAZ": "İTİRAZ", r"PTAL": "İPTAL", r"DAVANIN KABULÜNE": "DAVANIN KABULÜNE"
    }
    temiz = metin.replace("\n", " ").strip()
    temiz = re.sub(r'\s+', ' ', temiz)
    for bozuk, duzgun in duzeltmeler.items():
        temiz = re.sub(bozuk, duzgun, temiz, flags=re.IGNORECASE)
    return temiz

def pdf_oku(dosya):
    okuyucu = PyPDF2.PdfReader(dosya)
    metin = ""
    for sayfa in okuyucu.pages:
        metin += sayfa.extract_text() or ""
    return metin

def para_bul(metin, kelime):
    m = re.search(fr"([\d\.,]+\s*TL).*?{kelime}|{kelime}.*?([\d\.,]+\s*TL)", metin, re.IGNORECASE)
    return (m.group(1) or m.group(2)) if m else "-"

def analiz_yap(metin, dosya_adi):
    metin = metni_temizle(metin)
    bilgi = {"Dosya Adı": dosya_adi}
    
    # Regex Aramaları (Esas ve Karar No burada aranıyor)
    patterns = {
        "Mahkeme": r"(T\.?C\.?.*?MAHKEMES.*?)Esas",
        "Esas No": r"ESAS\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Karar No": r"KARAR\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Davacı": r"DAVACI\s*.*?[:;]\s*(.*?)(?=VEKİL|DAVALI)",
        "Davalı":
