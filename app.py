import streamlit as st
import PyPDF2
import re
import pandas as pd

# --- 1. AYARLAR ---
st.set_page_config(page_title="Hukuk Asistanı", layout="wide", page_icon="⚖️")

# --- 2. FONKSİYONLAR ---

def metni_temizle(metin):
    temiz = metin.replace("\n", " ").strip()
    temiz = re.sub(r'\s+', ' ', temiz)
    temiz = re.sub(r'(?<=\d)\?(?=\d)', '0', temiz) 
    temiz = re.sub(r'(?<=\d)\?', '', temiz) 
    
    duzeltmeler = {
        r"HAK M": "HAKİM", r"KAT P": "KATİP", r"VEK L": "VEKİL", 
        r"T RAZ": "İTİRAZ", r"PTAL": "İPTAL"
    }
    for b, d in duzeltmeler.items(): temiz = re.sub(b, d, temiz, flags=re.IGNORECASE)
    return temiz

def pdf_oku(dosya):
    okuyucu = PyPDF2.PdfReader(dosya)
    metin = ""
    for sayfa in okuyucu.pages: metin += sayfa.extract_text() or ""
    return metin

def para_bul(metin, anahtar_kelime_grubu):
    for anahtar in anahtar_kelime_grubu:
        regex = fr"([\d\.,]+\s*TL).{{0,100}}?{anahtar}|{anahtar}.{{0,100}}?([\d\.,]+\s*TL)"
        m = re.search(regex, metin, re.IGNORECASE)
        if m: return (m.group(1) or m.group(2)).strip()
    return "0,00 TL"

def dava_turu_belirle(mahkeme_adi, metin):
    mahkeme_lower = mahkeme_adi.lower()
    metin_lower = metin.lower()
    
    if "icra" in mahkeme_lower: return "⚡ İCRA HUKUKU"
    if "ceza" in mahkeme_lower: return "🛑 CEZA HUKUKU"
    if "idare" in mahkeme_lower or "vergi" in mahkeme_lower: return "🏛️ İDARE HUKUKU"
    if "sulh hukuk" in mahkeme_lower or "asliye hukuk" in mahkeme_lower or "aile" in mahkeme_lower or "iş" in mahkeme_lower: return "⚖️ ÖZEL HUKUK"
    
    if "sanık" in metin_lower or "suç" in metin_lower: return "🛑 CEZA HUKUKU"
    if "yürütme" in metin_lower or "iptali" in metin_lower: return "🏛️ İDARE HUKUKU"
    if "ödeme emri" in metin_lower or "takip" in metin_lower: return "⚡ İCRA HUKUKU"
    
    return "⚖️ ÖZEL HUKUK"

def analiz_yap(metin, dosya_adi):
    metin = metni_temizle(metin)
    bilgi = {"Dosya Adı": dosya_adi}
    
    # Regex Kalıpları
    regexler = {
        "Mahkeme": r"(T\.?C\.?.*?MAHKEMES.*?)Esas",
        "Esas No": r"ESAS\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Karar No": r"KARAR\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Dava Konusu": r"\bDAVA\b\s*[:;]?\s*(.*?)(?=DAVA TARİHİ|KARAR TARİHİ|ESAS)",
        
        # --- ÇOKLU TARAF İÇİN GENİŞLETİLMİŞ ARAMA ---
        # "DAVACI" kelimesinden sonra "VEKİL" veya "DAVALI" görene kadar ne varsa al.
        # re.DOTALL sayesinde birden fazla satırı da kapsar.
        "Davacı": r"DAVACI(?:LAR)?\s*[:;]?\s*(.*?)(?=VEKİL|DAVALI)",
        "Davacı Vekili": r"(?:DAVACI\s*)?VEKİL[İI]\s*[:;]?\s*(.*?)(?=DAVALI|DAVA)",
        
        # "DAVALI" kelimesinden sonra "VEKİL", "DAVA" veya "KONU" görene kadar ne varsa al.
        "Davalı": r"DAVALI(?:LAR)?\s*[:;]?\s*(.*?)(?=VEKİL|DAVA|KONU)",
        "Davalı Vekili": r"DAVALI.*?VEKİL[İI]\s*[:;]?\s*(.*?)(?=DAVA|KONU)",
        
        "Dava Tarihi": r"DAVA\s*TARİH[İI]\s*[:;]?\s*(\d{2}[./]\d{2}[./]\d{4})",
        "Karar Tarihi": r"KARAR\s*TARİH[İI]\s*[:;]?\s*(\d{2}[./]\d{2}[./]\d{4})"
    }
    
    for k, v in regexler.items():
        # re.DOTALL ile satır atlamaları yoksayarak geniş arama yapıyoruz
        m = re.search(v, metin, re.IGNORECASE | re.DOTALL)
        if m:
            # Bulunan metni temizle (Çoklu boşlukları sil, gereksiz karakterleri at)
            raw_val = m.group(1).replace(":", "").strip()
            # Eğer çok uzunsa (500 karakterden fazla) muhtemelen hata yapmıştır, kırp.
            bilgi[k] = raw_val[:500] 
        else:
            bilgi[k] = "" 

    bilgi["Dava Türü"] = dava_turu_belirle(bilgi["Mahkeme"], metin)

    alan = metin.upper()[-3000:]
    if "KISMEN KABUL" in alan: bilgi["Sonuç"] = "⚠️ KISMEN KABUL"
    elif re.search(r"DAVANIN\s*KABUL", alan) or re.search(r"İTİRAZIN\s*İPTAL", alan): bilgi["Sonuç"] = "✅ KABUL"
    elif re.search(r"DAVANIN\s*RED", alan): bilgi["Sonuç"] = "❌ RED"
    else: bilgi["Sonuç"] = "❓ Belirsiz"

    bilgi["Vekalet Ücreti"] = para_bul(alan, ["vekalet ücreti", "ücreti vekalet"])
    bilgi["Yargılama Gideri"] = para_bul(alan, ["toplam yargılama gideri", "yapılan masraf", "yargılama giderinin"])
    bilgi["Harç"] = para_bul(alan, ["bakiye", "karar harcı", "eksik kalan"])
    return bilgi

# --- 3. ARAYÜZ ---

st.title("⚖️ Hukuk Asistanı")
st.markdown("---")

# Dosya Yükleme
dosya = st.file_uploader("Analiz Edilecek PDF Dosyasını Yükleyin", type="pdf")

if dosya:
    if "analiz_sonucu" not in st.session_state or st.session_state.dosya_adi != dosya.name:
        with st.spinner("Dosya okunuyor..."):
            text = pdf_oku(dosya)
            st.session_state.analiz_sonucu = analiz_yap(text, dosya.name)
            st.session_state.dosya_adi = dosya.name
    
    veri = st.session_state.analiz_sonucu

    # --- DETAYLI BİLGİ ALANLARI ---
    st.subheader("📝 Analiz Detayları")
    
    # 1. SATIR
    st.write("###### 🗂 Dosya Kimliği")
    c1, c2, c3, c4 = st.columns(4)
    
    c1.text_input("Hukuk Türü", value=veri["Dava Türü"], disabled=True)
    y_mahkeme = c2.text_input("Mahkeme", veri["Mahkeme"])
    y_esas = c3.text_input("Esas No", veri["Esas No"])
    y_karar = c4.text_input("Karar No", veri["Karar No"])
    
    # 2. SATIR
    c_konu, c_t1, c_t2 = st.columns([2, 1, 1])
    y_konu = c_konu.text_input("Dava Konusu", veri["Dava Konusu"]) 
    y_dava_t = c_t1.text_input("Dava Tarihi", veri["Dava Tarihi"])
    y_karar_t = c_t2.text_input("Karar Tarihi", veri["Karar Tarihi"])

    # 3. SATIR
    st.markdown("---")
    st.write("###### 👥 Taraflar")
    # Çoklu isimler uzun olabileceği için text_area (geniş kutu) kullanmak daha iyidir
    c4, c5 = st.columns(2)
    y_davaci = c4.text_area("Davacı(lar)", veri["Davacı"], height=68)
    y_d_vekil = c5.text_area("Davacı Vekili", veri["Davacı Vekili"], height=68)
    
    c6, c7 = st.columns(2)
    y_davali = c6.text_area("Davalı(lar)", veri["Davalı"], height=68)
    y_davali_vekil = c7.text_area("Davalı Vekili", veri["Davalı Vekili"], height=68)
    
    # 4. SATIR
    st.markdown("---")
    st.write("###### 💰 Mali Detaylar")
    m_c0, m_c1, m_c2, m_c3 = st.columns(4)
    m_c0.text_input("Sonuç", value=veri["Sonuç"], disabled=True)
    y_vekalet = m_c1.text_input("Vekalet", veri["Vekalet Ücreti"])
    y_gider = m_c2.text_input("Gider", veri["Yargılama Gideri"])
    y_harc = m_c3.text_input("Harç", veri["Harç"])
