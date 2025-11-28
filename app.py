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

# --- 🔥 YENİ: DİLEKÇE VE GEREKÇE ÖZETLEYİCİLER ---

def dilekce_ozetle(metin):
    """Dava Dilekçesi için Baş (Konu) ve Son (Talep) kısmını birleştirir."""
    ozet = ""
    konu_ara = re.search(r"(?:KONU|DAVA KONUSU)\s*[:;]\s*(.*?)(?=\n|AÇIKLAMALAR|TEBLİĞ)", metin, re.IGNORECASE | re.DOTALL)
    if konu_ara:
        ozet += f"📌 KONU: {konu_ara.group(1).replace('\n', ' ').strip()[:300]}...\n"
    
    talep_ara = re.search(r"(?:NETİCE|SONUÇ VE İSTEM|SONUÇ VE TALEP)\s*[:;]?\s*(.*)", metin, re.IGNORECASE | re.DOTALL)
    if talep_ara:
        temiz_talep = re.split(r"(?:Av\.|Avukat|Saygılarımla)", talep_ara.group(1), flags=re.IGNORECASE)[0]
        ozet += f"🎯 TALEP: {temiz_talep.replace('\n', ' ').strip()}"
    
    return ozet if ozet else "Dilekçe formatı tespit edilemedi."

def gerekce_analiz_et(metin):
    """
    Mahkeme Kararı Gerekçesini Özetler.
    1. Yasa Maddesi (TBK, HMK vb.)
    2. Kritik Olay (İnkar, İkrar, Bilirkişi)
    3. Sonuç Cümlesi (Anlaşılmakla...)
    """
    gerekce_ozeti = ""
    
    # Gerekçe Bloğunu Bul
    blok = re.search(r"(GEREKÇE|GEREĞİ DÜŞÜNÜLDÜ)\s*[:;]?(.*?)(HÜKÜM|KARAR)", metin, re.IGNORECASE | re.DOTALL)
    if not blok: return "Gerekçe metni ayrıştırılamadı."
    
    icerik = blok.group(2).replace("\n", " ")
    
    # 1. YASA MADDESİ YAKALA
    yasa = re.search(r"(TBK|TMK|HMK|İİK|Kanon|Madde)\s*\d+", icerik, re.IGNORECASE)
    if yasa:
        gerekce_ozeti += f"⚖️ DAYANAK: Mahkeme {yasa.group(0)} maddesine atıf yapmıştır.\n"
    
    # 2. KRİTİK KELİMELERİ YAKALA (Cümle bazlı)
    # Cümlelere böl
    cumleler = icerik.split(".")
    kritik_kelimeler = ["inkar", "kabul etmiş sayıl", "bilirkişi", "ispat", "süresinde", "haklı", "haksız"]
    
    for cumle in cumleler:
        for kelime in kritik_kelimeler:
            if kelime in cumle.lower():
                # Çok uzun cümleleri kısalt
                temiz_cumle = cumle.strip()[:200]
                if temiz_cumle and temiz_cumle not in gerekce_ozeti:
                    gerekce_ozeti += f"👉 TESPİT: ...{temiz_cumle}...\n"
                break # Aynı cümleyi tekrar yazma
    
    # 3. SONUÇ BAĞLACI
    sonuc_cumlesi = re.search(r"([^.]*?anlaşılmakla[^.]*)", icerik, re.IGNORECASE)
    if sonuc_cumlesi:
        gerekce_ozeti += f"✅ SONUÇ: {sonuc_cumlesi.group(1).strip()}"
        
    return gerekce_ozeti if len(gerekce_ozeti) > 10 else "Gerekçe çok kısa veya standart dışı."

def analiz_yap(metin, dosya_adi):
    # Orijinal metni sakla
    ham_metin = metin
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

    alan = metin.upper()[-3000:]
    
    if "KISMEN KABUL" in alan:
        bilgi["Sonuç"] = "⚠️ KISMEN KABUL"
        bilgi["Kazanan"] = "Ortak"
        bilgi["Ödeme Yönü"] = "Paylaşılır"
    elif re.search(r"DAVANIN\s*KABUL", alan) or re.search(r"İTİRAZIN\s*İPTAL", alan):
        bilgi["Sonuç"] = "✅ KABUL"
        bilgi["Kazanan"] = "DAVACI"
        bilgi["Ödeme Yönü"] = "🔴 DAVALI ÖDER -> 🔵 DAVACIYA"
    elif re.search(r"DAVANIN\s*RED", alan):
        bilgi["Sonuç"] = "❌ RED"
        bilgi["Kazanan"] = "DAVALI"
        bilgi["Ödeme Yönü"] = "🔵 DAVACI ÖDER -> 🔴 DAVALIYA"
    else:
        bilgi["Sonuç"] = "❓ Belirsiz"
        bilgi["Kazanan"] = "-"
        bilgi["Ödeme Yönü"] = "-"

    bilgi["Vekalet Ücreti"] = para_bul(alan, ["vekalet ücreti", "ücreti vekalet"])
    bilgi["Yargılama Gideri"] = para_bul(alan, ["toplam yargılama gideri", "yapılan masraf", "yargılama giderinin"])
    bilgi["Harç"] = para_bul(alan, ["bakiye", "karar harcı", "eksik kalan"])
    
    # ÖZETLERİ ÇIKAR
    bilgi["Gerekçe Özeti"] = gerekce_analiz_et(ham_metin) # Mahkeme Kararıysa
    bilgi["Dilekçe Özeti"] = dilekce_ozetle(ham_metin)   # Dava Dilekçesiyse
    
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
    
    # 1. SATIR: Kimlik
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
    
    # --- YENİ: AKILLI ÖZET ALANI ---
    st.markdown("---")
    st.write("###### 🧠 Yapay Zeka Özeti")
    
    # Eğer bu bir kararsa Gerekçeyi göster, değilse Dilekçeyi göster
    if "KARAR" in veri["Karar No"] or "HÜKÜM" in text:
        st.info("Bu bir Mahkeme Kararıdır. Gerekçe analizi aşağıdadır:")
        st.text_area("Karar Gerekçesi (Özet)", value=veri["Gerekçe Özeti"], height=150)
    else:
        st.info("Bu bir Dava Dilekçesidir. Talep analizi aşağıdadır:")
        st.text_area("Dilekçe Özeti (Konu + Talep)", value=veri["Dilekçe Özeti"], height=150)

    # 4. SATIR: SONUÇ
    st.markdown("---")
    st.write("###### 🏆 Karar ve Kazanan")
    res1, res2, res3 = st.columns([1, 1, 2])
    res1.text_input("Sonuç", value=veri["Sonuç"], disabled=True)
