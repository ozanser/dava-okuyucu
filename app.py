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

# --- 2. CSS TASARIMI ---
st.markdown("""
<style>
    h1 { color: #2c3e50; font-family: 'Helvetica Neue', sans-serif; }
    .stSuccess { background-color: #d4edda; border-left: 5px solid #28a745; }
    .stError { background-color: #f8d7da; border-left: 5px solid #dc3545; }
    footer {visibility: hidden;}
    .mali-kutu {
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        border: 1px solid #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. FONKSİYONLAR ---

def metni_temizle_ve_duzelt(metin):
    """OCR hatalarını temizler."""
    duzeltmeler = {
        r"HAK M": "HAKİM", r"KAT P": "KATİP", r"VEK L": "VEKİL",
        r"T RAZ": "İTİRAZ", r"PTAL": "İPTAL", r"TAHL YE": "TAHLİYE",
        r"DAVACI": "DAVACI", r"DAVALI": "DAVALI", r"HÜKÜM": "HÜKÜM",
        r"TL": "TL", r"TL'nin": "TL",
        r"DAVANIN KABULÜNE": "DAVANIN KABULÜNE"
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

def para_bul(metin, anahtar_kelime):
    """
    Belirli bir kelimenin (örn: vekalet ücreti) yanındaki TL tutarını bulur.
    Örn: "18.000,00 TL vekalet ücreti" -> 18.000,00 TL
    """
    # Regex: Sayı + (. veya ,) + Sayı + TL kelimesini arar
    kalip = fr"([\d\.,]+)\s*TL.*?{anahtar_kelime}|{anahtar_kelime}.*?([\d\.,]+)\s*TL"
    bulunan = re.search(kalip, metin, re.IGNORECASE)
    
    if bulunan:
        # Grup 1 veya Grup 2 dolu olabilir
        tutar = bulunan.group(1) if bulunan.group(1) else bulunan.group(2)
        return f"{tutar} TL"
    return "Tutar Tespit Edilemedi"

def sonuc_ve_mali_analiz(metin):
    """Gelişmiş Mali Analiz"""
    analiz = {
        "Kazanan": "Belirsiz", "Kaybeden": "Belirsiz",
        "Vekalet Yönü": "-", "Gider Yönü": "-",
        "Vekalet Tutar": "-", "Harç Tutar": "-",
        "Faiz": "Yok",
        "Durum": "⚠️ Belirsiz"
    }
    
    # Kazanma Durumu
    if re.search(r"KISMEN\s*KABUL", metin, re.IGNORECASE):
        analiz["Durum"] = "⚠️ KISMEN KABUL"
        analiz["Kazanan"] = "Ortak"
        analiz["Vekalet Yönü"] = "Karşılıklı (Oranına Göre)"
        
    elif re.search(r"DAVANIN\s*KABUL", metin, re.IGNORECASE):
        analiz.update({"Kazanan": "DAVACI", "Kaybeden": "DAVALI", "Durum": "✅ KABUL"})
        analiz["Vekalet Yönü"] = "Davalı ➡️ Davacı Avukatına"
        analiz["Gider Yönü"] = "Davalı Öder"
        
    elif re.search(r"DAVANIN\s*RED", metin, re.IGNORECASE):
        analiz.update({"Kazanan": "DAVALI", "Kaybeden": "DAVACI", "Durum": "❌ RED"})
        analiz["Vekalet Yönü"] = "Davacı ➡️ Davalı Avukatına"
        analiz["Gider Yönü"] = "Davacı Üzerinde Kalır"

    # --- YENİ ÖZELLİK: RAKAM AVCISI ---
    # Vekalet ücreti tutarını bul
    analiz["Vekalet Tutar"] = para_bul(metin, "vekalet ücreti")
    
    # Harç tutarını bul (karar harcı, ilam harcı)
    analiz["Harç Tutar"] = para_bul(metin, "harc")

    # --- YENİ ÖZELLİK: FAİZ DEDEKTİFİ ---
    if re.search(r"(yasal|ticari|avans)\s*faiz", metin, re.IGNORECASE):
        analiz["Faiz"] = "⚠️ Kararda FAİZ İşletilmesi Var!"
    else:
        analiz["Faiz"] = "Faiz belirtilmemiş."

    return analiz

def detayli_analiz(ham_metin, dosya_adi):
    metin = metni_temizle_ve_duzelt(ham_metin)
    bilgiler = {"Dosya Adı": dosya_adi}
    
    # Regexler
    regex_listesi = {
        "Mahkeme": r"(T\.?C\.?.*?MAHKEMES.*?)Esas",
        "Esas No": r"ESAS\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Karar No": r"KARAR\s*NO\s*[:;]?\
