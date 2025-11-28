import streamlit as st
import PyPDF2
import re
import pandas as pd

# --- 1. SAYFA YAPILANDIRMASI ---
st.set_page_config(
    page_title="Hukuk Asistanı Pro", 
    layout="wide", 
    page_icon="⚖️",
    initial_sidebar_state="expanded"
)

# --- 2. ÖZEL CSS (MAKYAJ KISMI) ---
st.markdown("""
<style>
    /* Ana başlık rengi ve fontu */
    h1 {
        color: #2c3e50;
        font-family: 'Helvetica Neue', sans-serif;
    }
    
    /* Alt başlıklar */
    h3 {
        color: #34495e;
        border-bottom: 2px solid #ecf0f1;
        padding-bottom: 10px;
    }

    /* Başarı (Yeşil) Kutusu Özelleştirme */
    .stSuccess {
        background-color: #d4edda;
        color: #155724;
        border-left: 5px solid #28a745;
    }

    /* Hata (Kırmızı) Kutusu Özelleştirme */
    .stError {
        background-color: #f8d7da;
        color: #721c24;
        border-left: 5px solid #dc3545;
    }

    /* Streamlit Footer'ı Gizle (Daha profesyonel görünüm) */
    footer {visibility: hidden;}
    
    /* Butonları Güzelleştir */
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. FONKSİYONLAR (BEYİN KISMI) ---
def metni_temizle_ve_duzelt(metin):
    """OCR hatalarını ve Türkçe karakterleri düzeltir."""
    duzeltmeler = {
        r"HAK M": "HAKİM", r"KAT P": "KATİP", r"VEK L": "VEKİL",
        r"T RAZ": "İTİRAZ", r"PTAL": "İPTAL", r"TAHL YE": "TAHLİYE",
        r"DAVACI": "DAVACI", r"DAVALI": "DAVALI", r"HÜKÜM": "HÜKÜM",
        r"GEREKÇEL KARAR": "GEREKÇELİ KARAR",
        r"YÜKLET LMES NE": "YÜKLETİLMESİNE",
        r"DAVANIN KABULÜNE": "DAVANIN KABULÜNE",
        r"DAVANIN REDD NE": "DAVANIN REDDİNE"
    }
    temiz_metin = metin.replace("\n", " ").strip()
    temiz_metin = re.sub(r'\s+', ' ', temiz_metin)
    for bozuk, duzgun in duzeltmeler.items():
        temiz_metin = re.sub(bozuk, duzgun, temiz_metin, flags=re.IGNORECASE)
    return temiz_metin

def pdf_metin_oku(dosya):
    okuyucu = PyPDF2.PdfReader(dosya)
    metin = ""
    for sayfa in okuyucu.pages:
        metin += sayfa.extract_text() or ""
    return metin

def sonuc_ve_mali_analiz(metin):
    analiz = {
        "Kazanan": "Belirsiz", "Kaybeden": "Belirsiz",
        "Vekalet Ücreti": "-", "Yargılama Gideri": "-",
        "Durum": "⚠️ Belirsiz"
    }
    kabul_kalibi = r"
