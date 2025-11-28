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
    cols = ["Dosya Adı", "Mahkeme", "Esas No", "Karar No", "Dava Konusu", 
            "Davacı", "Davacı Vekili", "Davalı", 
            "Dava Tarihi", "Karar Tarihi", "Sonuç", 
            "Vekalet Ücreti", "Yargılama Gideri", "Harç"]
    return pd.DataFrame(columns=cols)

def veritabanina_kaydet(yeni_veri):
    df = veritabani_yukle()
    yeni_satir = pd.DataFrame([yeni_veri])
    df = pd.concat([df, yeni_satir], ignore_index=True)
    df.to_csv(VERITABANI_DOSYASI, index=False)

def metni_temizle(metin):
    # Satır sonlarını boşlukla birleştir (Böylece alt satıra geçen parantez içleri bölünmez)
    temiz = metin.replace("\n", " ").strip()
    temiz = re.sub(r'\s+', ' ', temiz)
    temiz = re.sub(r'(?<=\d)\?(?=\d)', '0', temiz)
    
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
        m = re.search(fr"([\d\.,]+\s*TL).{{0,100}}?{anahtar}|{anahtar}.{{0,100}}?([\d\.,]+\s*TL)", metin, re.IGNORECASE)
        if m: return (m.group(1) or m.group(2)).strip()
    return "0,00 TL"

def analiz_yap(metin, dosya_adi):
    metin = metni_temizle(metin)
    bilgi = {"Dosya Adı": dosya_adi}
    
    # Künye Regex
    regexler = {
        "Mahkeme": r"(T\.?C\.?.*?MAHKEMES.*?)Esas",
        "Esas No": r"ESAS\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Karar No": r"KARAR\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        # BURASI DEĞİŞTİ: Parantez dahil her şeyi alır
        "Dava Konusu": r"DAVA\s*[:;]?\s*(.*?)(?=DAVA TARİHİ|KARAR TARİHİ|ESAS)", 
        "Davacı": r"DAVACI\s*[:;]?\s*(.*?)(?=VEKİL|DAVALI)",
        "Davacı Vekili": r"(?:DAVACI\s*)?VEKİL[İI]\s*[:;]?\s*(.*?)(?=DAVALI|DAVA)",
        "Davalı": r"DAVALI\s*[:;]?\s*(.*?)(?=VEKİL|DAVA|KONU)",
        "Dava Tarihi": r"DAVA\s*TARİH[İI]\s*[:;]?\s*(\d{2}[./]\d{2}[./]\d{4})",
        "Karar Tarihi": r"KARAR\s*TARİH[İI]\s*[:;]?\s*(\d{2}[./]\d{2}[./]\d{4})"
    }
    for k, v in regexler.items():
        m = re.search(v, metin, re.IGNORECASE)
        if m:
            raw_val = m.group(1).strip().replace(":", "")
            bilgi[k] = raw_val
        else:
            bilgi[k] = "-"

    # Sonuç
    alan = metin.upper()[-2500:]
    if "KISMEN KABUL" in alan: bilgi["Sonuç"] = "⚠️ KISMEN KABUL"
    elif re.search(r"DAVANIN\s*KABUL", alan) or re.search(r"İTİRAZIN\s*İPTAL", alan): bilgi["Sonuç"] = "✅ KABUL"
    elif re.search(r"DAVANIN\s*RED", alan): bilgi["Sonuç"] = "❌ RED"
    else: bilgi["Sonuç"] = "❓ Belirsiz"

    # Mali
    bilgi["Vekalet Ücreti"] = para_bul(alan, ["vekalet ücreti", "ücreti vekalet"])
    bilgi["Yargılama Gideri"] = para_bul(alan, ["toplam yargılama gideri", "yapılan masraf"])
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
        st.dataframe(df[["Esas No", "Dava Konusu", "Sonuç"]].tail(10), hide_index=True)
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
    m1.metric("Sonuç", veri["Sonuç"])
    m2.metric("Vekalet", veri["Vekalet Ücreti"])
    m3.metric("Giderler", veri["Yargılama Gideri"])
    m4.metric("Harç", veri["Harç"])
    st.divider()

    # --- DÜZENLEME FORMU ---
    st.subheader("📝 Bilgileri Doğrula")
    
    with st.form("kayit_formu"):
        
        # 1. SATIR: Kimlik
        c1, c2, c3 = st.columns(3)
        y_mahkeme = c1.text_input("Mahkeme", veri["Mahkeme"])
        y_esas = c2.text_input("Esas No", veri["Esas No"])
        y_karar = c3.text_input("Karar No", veri["Karar No"])
        
        # 2. SATIR: Dava Konusu ve Tarihler
        c_konu, c_tar1, c_tar2 = st.columns([2, 1, 1])
        # Artık parantezleri SİLMİYORUZ, olduğu gibi gösteriyoruz.
        y_konu = c_konu.text_input("Dava Konusu", veri["Dava Konusu"]) 
        y_dava_t = c_tar1.text_input("Dava Tarihi", veri["Dava Tarihi"])
        y_karar_t = c_tar2.text_input("Karar Tarihi", veri["Karar Tarihi"])

        # 3. SATIR: Taraflar
        st.markdown("---")
        c4, c5, c6 = st.columns(3)
        y_davaci = c4.text_input("Davacı", veri["Davacı"])
        y_vekil = c5.text_input("Davacı Vekili", veri["Davacı Vekili"])
        y_davali = c6.text_input("Davalı", veri["Davalı"])
        
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
                "Dosya Adı": veri["Dosya Adı"], "Mahkeme": y_mahkeme,
                "Esas No": y_esas, "Karar No": y_karar, "Dava Konusu": y_konu,
                "Davacı": y_davaci, "Davacı Vekili": y_vekil, "Davalı": y_davali,
                "Dava Tarihi": y_dava_t, "Karar Tarihi": y_karar_t,
                "Sonuç": y_sonuc, "Vekalet Ücreti": y_vekalet, 
                "Yargılama Gideri": y_gider, "Harç": y_harc
            }
            veritabanina_kaydet(kayit)
            st.success("Dosya eksiksiz şekilde arşivlendi.")
            st.rerun()
