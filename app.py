import streamlit as st
import PyPDF2
import re
import pandas as pd
import io

# --- 1. AYARLAR ---
st.set_page_config(page_title="Hukuk Asistanı", layout="wide", page_icon="⚖️")

# --- 2. CSS TASARIMI (BEYAZ TEMA KİLİDİ) ---
st.markdown("""
<style>
    /* 1. Ana Arkaplanı Bembeyaz Yap */
    .stApp {
        background-color: #ffffff;
        color: #31333F; /* Koyu Gri Yazı (Okunaklı) */
    }
    
    /* 2. Yan Menü (Sidebar) Açık Gri Olsun */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #dee2e6;
    }

    /* 3. Form Kutularının İçini Beyaz Yap ve Çerçeve Ekle */
    div[data-testid="stForm"] {
        background-color: #ffffff;
        padding: 25px;
        border-radius: 12px;
        border: 2px solid #e9ecef;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
    }
    
    /* 4. Başlıkları Koyu Lacivert Yap (Profesyonel Dursun) */
    h1, h2, h3 {
        color: #2c3e50 !important;
    }
    
    /* 5. Yazı Giriş Kutularını (Input) Belirginleştir */
    .stTextInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #fdfdfd;
        color: #333;
        border-color: #ced4da;
    }
    
    /* 6. Metrik Kutularını Düzenle */
    div[data-testid="stMetric"] {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #e9ecef;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. FONKSİYONLAR ---

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

# --- 4. ARAYÜZ ---

st.title("⚖️ Hukuk Asistanı")
st.markdown("---")

# Dosya Yükleme
dosya = st.file_uploader("Analiz Edilecek PDF Dosyasını Buraya Bırakın", type="pdf")

if dosya:
    if "analiz_sonucu" not in st.session_state or st.session_state.dosya_adi != dosya.name:
        with st.spinner("Dosya okunuyor, lütfen bekleyin..."):
            text = pdf_oku(dosya)
            st.session_state.analiz_sonucu = analiz_yap(text, dosya.name)
            st.session_state.dosya_adi = dosya.name
    
    veri = st.session_state.analiz_sonucu

    # --- ÖZET METRİKLER (Beyaz Temada Şık Görünür) ---
    c_m1, c_m2, c_m3, c_m4 = st.columns(4)
    c_m1.metric("Sonuç", veri["Sonuç"])
    c_m2.metric("Vekalet", veri["Vekalet Ücreti"])
    c_m3.metric("Giderler", veri["Yargılama Gideri"])
    c_m4.metric("Harç", veri["Harç"])

    st.write("") 
    
    # --- FORM ---
    st.subheader("📝 Analiz Detayları")
    
    with st.form("analiz_formu"):
        
        # 1. SATIR: Kimlik
        st.write("###### 🗂 Dosya Kimliği")
        c1, c2, c3, c4 = st.columns(4)
        
        turler = ["⚖️ ÖZEL HUKUK", "🛑 CEZA HUKUKU", "⚡ İCRA HUKUKU", "🏛️ İDARE HUKUKU"]
        secili_idx = 0
        if veri["Dava Türü"] in turler: secili_idx = turler.index(veri["Dava Türü"])
        
        y_tur = c1.selectbox("Tür", turler, index=secili_idx)
        y_mahkeme = c2.text_input("Mahkeme", veri["Mahkeme"])
        y_esas = c3.text_input("Esas No", veri["Esas No"])
        y_karar = c4.text_input("Karar No", veri["Karar No"])
        
        # 2. SATIR: Konu
        c_konu, c_t1, c_t2 = st.columns([2, 1, 1])
        y_konu = c_konu.text_input("Dava Konusu", veri["Dava Konusu"]) 
        y_dava_t = c_t1.text_input("Dava Tarihi", veri["Dava Tarihi"])
        y_karar_t = c_t2.text_input("Karar Tarihi", veri["Karar Tarihi"])

        # 3. SATIR: Taraflar
        st.markdown("---")
        st.write("###### 👥 Taraflar")
        c4, c5 = st.columns(2)
        y_davaci = c4.text_input("Davacı", veri["Davacı"])
        y_d_vekil = c5.text_input("Davacı Vekili", veri["Davacı Vekili"])
        
        c6, c7 = st.columns(2)
        y_davali = c6.text_input("Davalı", veri["Davalı"])
        y_davali_vekil = c7.text_input("Davalı Vekili", veri["Davalı Vekili"])
        
        # 4. SATIR: Mali
        st.markdown("---")
        st.write("###### 💰 Mali Detaylar")
        m_c0, m_c1, m_c2, m_c3 = st.columns(4)
        y_sonuc = m_c0.selectbox("Sonuç", ["✅ KABUL", "❌ RED", "⚠️ KISMEN KABUL", "❓ Belirsiz"], index=0)
        y_vekalet = m_c1.text_input("Vekalet", veri["Vekalet Ücreti"])
        y_gider = m_c2.text_input("Gider", veri["Yargılama Gideri"])
        y_harc = m_c3.text_input("Harç", veri["Harç"])

        st.markdown("---")
        submitted = st.form_submit_button("Analizi Güncelle")

    # --- EXCEL İNDİRME ---
    guncel_veri = {
        "Dosya": veri["Dosya Adı"], "Tür": y_tur, "Mahkeme": y_mahkeme,
        "Esas": y_esas, "Karar": y_karar, "Konu": y_konu,
        "Davacı": y_davaci, "Davalı": y_davali, "Sonuç": y_sonuc,
        "Vekalet": y_vekalet, "Gider": y_gider
    }
    
    df_single = pd.DataFrame([guncel_veri])
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df_single.to_excel(writer, index=False, sheet_name='Analiz')
        
    st.download_button(
        label="📥 Bu Analizi Excel Olarak İndir",
        data=buffer.getvalue(),
        file_name=f"Analiz_{y_esas.replace('/', '-')}.xlsx",
        mime="application/vnd.ms-excel"
    )
