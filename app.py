import streamlit as st
import PyPDF2
import re
import pandas as pd
import os

# --- 1. AYARLAR ---
st.set_page_config(page_title="Hukuk Asistanı", layout="wide", page_icon="⚖️")
VERITABANI_DOSYASI = "dava_arsivi.csv"

# --- 2. FONKSİYONLAR ---

def veritabani_yukle():
    if os.path.exists(VERITABANI_DOSYASI): return pd.read_csv(VERITABANI_DOSYASI)
    # YENİ SÜTUN: "Dava Türü"
    cols = ["Dosya Adı", "Dava Türü", "Mahkeme", "Esas No", "Karar No", "Dava Konusu", 
            "Davacı", "Davacı Vekili", "Davalı", "Davalı Vekili",
            "Dava Tarihi", "Karar Tarihi", "Sonuç", 
            "Vekalet Ücreti", "Yargılama Gideri", "Harç"]
    return pd.DataFrame(columns=cols)

def veritabanina_kaydet(yeni_veri):
    df = veritabani_yukle()
    yeni_satir = pd.DataFrame([yeni_veri])
    df = pd.concat([df, yeni_satir], ignore_index=True)
    df.to_csv(VERITABANI_DOSYASI, index=False)

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
    """Mahkeme adına ve içeriğe bakarak dava türünü tahmin eder."""
    mahkeme_lower = mahkeme_adi.lower()
    metin_lower = metin.lower()
    
    # 1. Öncelik: Mahkeme Adı
    if "icra" in mahkeme_lower: return "⚡ İCRA HUKUKU"
    if "ceza" in mahkeme_lower: return "🛑 CEZA HUKUKU"
    if "idare" in mahkeme_lower or "vergi" in mahkeme_lower: return "🏛️ İDARE HUKUKU"
    if "sulh hukuk" in mahkeme_lower or "asliye hukuk" in mahkeme_lower or "aile" in mahkeme_lower or "iş" in mahkeme_lower: return "⚖️ ÖZEL HUKUK"
    
    # 2. Öncelik: İçerik Kelimeleri
    if "sanık" in metin_lower or "suç" in metin_lower or "beraat" in metin_lower: return "🛑 CEZA HUKUKU"
    if "yürütmenin durdurulması" in metin_lower or "iptali" in metin_lower: return "🏛️ İDARE HUKUKU"
    if "ödeme emri" in metin_lower or "takip" in metin_lower: return "⚡ İCRA HUKUKU"
    
    return "⚖️ ÖZEL HUKUK" # Varsayılan

def analiz_yap(metin, dosya_adi):
    metin = metni_temizle(metin)
    bilgi = {"Dosya Adı": dosya_adi}
    
    # Künye Regex
    regexler = {
        "Mahkeme": r"(T\.?C\.?.*?MAHKEMES.*?)Esas",
        "Esas No": r"ESAS\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Karar No": r"KARAR\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Dava Konusu": r"\bDAVA\b\s*[:;]?\s*(.*?)(?=DAVA TARİHİ|KARAR TARİHİ|ESAS)",
        "Davacı": r"DAVACI\s*[:;]?\s*(.*?)(?=VEKİL|DAVALI)",
        "Davacı Vekili": r"(?:DAVACI\s*)?VEKİL[İI]\s*[:;]?\s*(.*?)(?=DAVALI|DAVA)",
        "Davalı": r"DAVALI\s*[:;]?\s*(.*?)(?=VEKİL|DAVA|KONU)",
        "Davalı Vekili": r"DAVALI.*?VEKİL[İI]\s*[:;]?\s*(.*?)(?=DAVA|KONU)",
        "Dava Tarihi": r"DAVA\s*TARİH[İI]\s*[:;]?\s*(\d{2}[./]\d{2}[./]\d{4})",
        "Karar Tarihi": r"KARAR\s*TARİH[İI]\s*[:;]?\s*(\d{2}[./]\d{2}[./]\d{4})"
    }
    
    for k, v in regexler.items():
        m = re.search(v, metin, re.IGNORECASE)
        bilgi[k] = m.group(1).strip().replace(":", "") if m else ""

    # DAVA TÜRÜNÜ BELİRLE (YENİ FONKSİYON)
    bilgi["Dava Türü"] = dava_turu_belirle(bilgi["Mahkeme"], metin)

    # Sonuç
    alan = metin.upper()[-3000:]
    if "KISMEN KABUL" in alan: bilgi["Sonuç"] = "⚠️ KISMEN KABUL"
    elif re.search(r"DAVANIN\s*KABUL", alan) or re.search(r"İTİRAZIN\s*İPTAL", alan): bilgi["Sonuç"] = "✅ KABUL"
    elif re.search(r"DAVANIN\s*RED", alan): bilgi["Sonuç"] = "❌ RED"
    else: bilgi["Sonuç"] = "❓ Belirsiz"

    # Mali
    bilgi["Vekalet Ücreti"] = para_bul(alan, ["vekalet ücreti", "ücreti vekalet"])
    bilgi["Yargılama Gideri"] = para_bul(alan, ["toplam yargılama gideri", "yapılan masraf", "yargılama giderinin"])
    bilgi["Harç"] = para_bul(alan, ["bakiye", "karar harcı", "eksik kalan"])
    return bilgi

# --- 3. ARAYÜZ ---

st.title("⚖️ Hukuk Asistanı")

# Sidebar
with st.sidebar:
    st.header("Arşiv")
    df = veritabani_yukle()
    st.metric("Kayıtlı Dosya", len(df))
    if not df.empty:
        # Tabloya Dava Türünü de ekledik
        st.dataframe(df[["Esas No", "Dava Türü", "Sonuç"]].tail(10), hide_index=True)
        st.download_button("Excel İndir", df.to_csv(index=False).encode('utf-8'), "arsiv.csv")

# Upload
dosya = st.file_uploader("Karar Dosyası Yükle (PDF)", type="pdf")

if dosya:
    if "analiz_sonucu" not in st.session_state or st.session_state.dosya_adi != dosya.name:
        text = pdf_oku(dosya)
        st.session_state.analiz_sonucu = analiz_yap(text, dosya.name)
        st.session_state.dosya_adi = dosya.name
    
    veri = st.session_state.analiz_sonucu

    # Özet Kartlar
    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Hukuk Türü", veri["Dava Türü"]) # <-- BURASI YENİ
    m2.metric("Sonuç", veri["Sonuç"])
    m3.metric("Vekalet", veri["Vekalet Ücreti"])
    m4.metric("Giderler", veri["Yargılama Gideri"])
    st.divider()

    # --- DÜZENLEME FORMU ---
    st.subheader("📝 Bilgileri Doğrula")
    
    with st.form("kayit_formu"):
        
        # 1. SATIR: Tür ve Kimlik
        st.write("###### 🗂 Dosya Bilgileri")
        c0, c1, c2, c3 = st.columns(4)
        
        # Dava Türü Seçimi (Otomatik gelir, elle değiştirebilirsin)
        turler = ["⚖️ ÖZEL HUKUK", "🛑 CEZA HUKUKU", "⚡ İCRA HUKUKU", "🏛️ İDARE HUKUKU"]
        secili_tur_index = 0
        if veri["Dava Türü"] in turler:
            secili_tur_index = turler.index(veri["Dava Türü"])
            
        y_tur = c0.selectbox("Dava Türü", turler, index=secili_tur_index)
        y_mahkeme = c1.text_input("Mahkeme", veri["Mahkeme"])
        y_esas = c2.text_input("Esas No", veri["Esas No"])
        y_karar = c3.text_input("Karar No", veri["Karar No"])
        
        # 2. SATIR: Konu ve Tarih
        c_konu, c_tar1, c_tar2 = st.columns([2, 1, 1])
        y_konu = c_konu.text_input("Dava Konusu", veri["Dava Konusu"]) 
        y_dava_t = c_tar1.text_input("Dava Tarihi", veri["Dava Tarihi"])
        y_karar_t = c_tar2.text_input("Karar Tarihi", veri["Karar Tarihi"])

        # 3. SATIR: Taraflar
        st.markdown("---")
        st.write("###### 👥 Taraflar")
        c4, c5 = st.columns(2)
        y_davaci = c4.text_input("Davacı", veri["Davacı"])
        y_d_vekil = c5.text_input("Davacı Vekili", veri["Davacı Vekili"])
        
        c6, c7 = st.columns(2)
        y_davali = c6.text_input("Davalı", veri["Davalı"])
        y_davali_vekil = c7.text_input("Davalı Vekili", veri["Davalı Vekili"])
        
        # 4. SATIR: Mali Detaylar
        st.markdown("---")
        m_c0, m_c1, m_c2, m_c3 = st.columns(4)
        y_sonuc = m_c0.selectbox("Sonuç", ["✅ KABUL", "❌ RED", "⚠️ KISMEN KABUL", "❓ Belirsiz"], index=0)
        y_vekalet = m_c1.text_input("Vekalet", veri["Vekalet Ücreti"])
        y_gider = m_c2.text_input("Gider", veri["Yargılama Gideri"])
        y_harc = m_c3.text_input("Harç", veri["Harç"])

        st.markdown("---")
        if st.form_submit_button("✅ VERİLERİ KAYDET", use_container_width=True):
            kayit = {
                "Dosya Adı": veri["Dosya Adı"], "Dava Türü": y_tur,
                "Mahkeme": y_mahkeme, "Esas No": y_esas, "Karar No": y_karar, "Dava Konusu": y_konu,
                "Davacı": y_davaci, "Davacı Vekili": y_d_vekil, 
                "Davalı": y_davali, "Davalı Vekili": y_davali_vekil,
                "Dava Tarihi": y_dava_t, "Karar Tarihi": y_karar_t,
                "Sonuç": y_sonuc, "Vekalet Ücreti": y_vekalet, 
                "Yargılama Gideri": y_gider, "Harç": y_harc
            }
            veritabanina_kaydet(kayit)
            st.success("Dosya eksiksiz şekilde arşivlendi.")
            st.rerun()
