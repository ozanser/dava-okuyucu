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
    if "idare" in mahkeme_lower: return "🏛️ İDARE HUKUKU"
    
    if "sanık" in metin_lower: return "🛑 CEZA HUKUKU"
    if "yürütme" in metin_lower: return "🏛️ İDARE HUKUKU"
    if "ödeme emri" in metin_lower: return "⚡ İCRA HUKUKU"
    
    return "⚖️ ÖZEL HUKUK"

def analiz_yap(metin, dosya_adi):
    metin = metni_temizle(metin)
    bilgi = {"Dosya Adı": dosya_adi}
    
    regexler = {
        "Mahkeme": r"(T\.?C\.?.*?MAHKEMES.*?)Esas",
        "Esas No": r"ESAS\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Karar No": r"KARAR\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Dava Konusu": r"\bDAVA\b\s*[:;]?\s*(.*?)(?=DAVA TARİHİ|KARAR TARİHİ|ESAS)",
        "Davacı": r"DAVACI(?:LAR)?\s*[:;]?\s*(.*?)(?=VEKİL|DAVALI)",
        "Davacı Vekili": r"(?:DAVACI\s*)?VEKİL[İI]\s*[:;]?\s*(.*?)(?=DAVALI|DAVA)",
        "Davalı": r"DAVALI(?:LAR)?\s*[:;]?\s*(.*?)(?=VEKİL|DAVA|KONU)",
        "Davalı Vekili": r"DAVALI.*?VEKİL[İI]\s*[:;]?\s*(.*?)(?=DAVA|KONU)",
        "Dava Tarihi": r"DAVA\s*TARİH[İI]\s*[:;]?\s*(\d{2}[./]\d{2}[./]\d{4})",
        "Karar Tarihi": r"KARAR\s*TARİH[İI]\s*[:;]?\s*(\d{2}[./]\d{2}[./]\d{4})"
    }
    
    for k, v in regexler.items():
        m = re.search(v, metin, re.IGNORECASE | re.DOTALL)
        bilgi[k] = m.group(1).replace(":", "").strip()[:500] if m else ""

    bilgi["Dava Türü"] = dava_turu_belirle(bilgi["Mahkeme"], metin)

    # --- SONUÇ VE KAZANAN ANALİZİ ---
    alan = metin.upper()[-3000:]
    
    if "KISMEN KABUL" in alan:
        bilgi["Sonuç"] = "⚠️ KISMEN KABUL"
        bilgi["Kazanan"] = "Ortak (Kısmi)"
        bilgi["Ödeme Yönü"] = "Oranına Göre Paylaşılır"
        
    elif re.search(r"DAVANIN\s*KABUL", alan) or re.search(r"İTİRAZIN\s*İPTAL", alan):
        bilgi["Sonuç"] = "✅ KABUL"
        bilgi["Kazanan"] = "DAVACI (Alacaklı)"
        bilgi["Ödeme Yönü"] = "🔴 DAVALI ÖDER -> 🔵 DAVACIYA"
        
    elif re.search(r"DAVANIN\s*RED", alan):
        bilgi["Sonuç"] = "❌ RED"
        bilgi["Kazanan"] = "DAVALI (Borçlu)"
        bilgi["Ödeme Yönü"] = "🔵 DAVACI ÖDER -> 🔴 DAVALIYA"
        
    else:
        bilgi["Sonuç"] = "❓ Belirsiz"
        bilgi["Kazanan"] = "-"
        bilgi["Ödeme Yönü"] = "-"

    bilgi["Vekalet Ücreti"] = para_bul(alan, ["vekalet ücreti", "ücreti vekalet"])
    bilgi["Yargılama Gideri"] = para_bul(alan, ["toplam yargılama gideri", "yapılan masraf", "yargılama giderinin"])
    bilgi["Harç"] = para_bul(alan, ["bakiye", "karar harcı", "eksik kalan"])
    
    return bilgi

# --- 3. ARAYÜZ ---

st.title("⚖️ Hukuk Asistanı")
st.markdown("---")

dosya = st.file_uploader("Analiz Edilecek PDF Dosyasını Yükleyin", type="pdf")

if dosya:
    if "analiz_sonucu" not in st.session_state or st.session_state.dosya_adi != dosya.name:
        with st.spinner("Yapay zeka analiz ediyor..."):
            text = pdf_oku(dosya)
            st.session_state.analiz_sonucu = analiz_yap(text, dosya.name)
            st.session_state.dosya_adi = dosya.name
    
    veri = st.session_state.analiz_sonucu

    # --- ANALİZ DETAYLARI ---
    st.subheader("📝 Analiz Detayları")
    
    # 1. SATIR: Kimlik ve Tür
    st.write("###### 🗂 Dosya Kimliği")
    c1, c2, c3, c4 = st.columns(4)
    c1.text_input("Hukuk Türü", value=veri["Dava Türü"], disabled=True)
    c2.text_input("Mahkeme", veri["Mahkeme"])
    c3.text_input("Esas No", veri["Esas No"])
    c4.text_input("Karar No", veri["Karar No"])
    
    # 2. SATIR: Konu
    c_konu, c_t1, c_t2 = st.columns([2, 1, 1])
    c_konu.text_input("Dava Konusu", veri["Dava Konusu"]) 
    c_t1.text_input("Dava Tarihi", veri["Dava Tarihi"])
    c_t2.text_input("Karar Tarihi", veri["Karar Tarihi"])

    # 3. SATIR: Taraflar
    st.markdown("---")
    st.write("###### 👥 Taraflar")
    c4, c5 = st.columns(2)
    c4.text_area("Davacı Taraf", veri["Davacı"], height=68)
    c5.text_area("Davacı Vekili", veri["Davacı Vekili"], height=68)
    
    c6, c7 = st.columns(2)
    c6.text_area("Davalı Taraf", veri["Davalı"], height=68)
    c7.text_area("Davalı Vekili", veri["Davalı Vekili"], height=68)
    
    # 4. SATIR: SONUÇ VE ÖDEME YÖNÜ (YENİ)
    st.markdown("---")
    st.write("###### 🏆 Karar ve Kazanan")
    res1, res2, res3 = st.columns([1, 1, 2])
    
    # Bu alanlar yapay zeka tespitidir, kullanıcı değiştiremez (Güvenlik için)
    res1.text_input("Sonuç", value=veri["Sonuç"], disabled=True)
    res2.text_input("Kazanan Taraf", value=veri["Kazanan"], disabled=True) # <-- YENİ
    res3.text_input("Parayı Kim Kime Öder?", value=veri["Ödeme Yönü"], disabled=True) # <-- YENİ

    # 5. SATIR: Mali Rakamlar
    st.write("###### 💰 Mali Yükümlülükler")
    m1, m2, m3 = st.columns(3)
    m1.text_input("Vekalet Ücreti", veri["Vekalet Ücreti"])
    m2.text_input("Giderler", veri["Yargılama Gideri"])
    m3.text_input("Harç", veri["Harç"])
