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
    div[data-testid="stForm"] {
        border: 2px solid #f0f2f6;
        padding: 20px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. FONKSİYONLAR ---

def veritabani_yukle():
    if os.path.exists(VERITABANI_DOSYASI):
        return pd.read_csv(VERITABANI_DOSYASI)
    else:
        return pd.DataFrame(columns=["Dosya Adı", "Mahkeme", "Esas No", "Karar No", 
                                     "Davacı", "Davalı", "Sonuç", "Vekalet Ücreti"])

def veritabanina_kaydet(yeni_veri):
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
    regex_str = r"([\d\.,]+\s*TL).*?{0}|{0}.*?([\d\.,]+\s*TL)".format(kelime)
    m = re.search(regex_str, metin, re.IGNORECASE)
    return (m.group(1) or m.group(2)) if m else "-"

def analiz_yap(metin, dosya_adi):
    metin = metni_temizle(metin)
    bilgi = {"Dosya Adı": dosya_adi}
    
    # Regex Aramaları
    patterns = {
        "Mahkeme": r"(T\.?C\.?.*?MAHKEMES.*?)Esas",
        "Esas No": r"ESAS\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Karar No": r"KARAR\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Davacı": r"DAVACI\s*.*?[:;]\s*(.*?)(?=VEKİL|DAVALI)",
        "Davalı": r"DAVALI\s*.*?[:;]\s*(.*?)(?=VEKİL|DAVA|KONU)"
    }
    
    for k, v in patterns.items():
        m = re.search(v, metin, re.IGNORECASE)
        bilgi[k] = m.group(1).strip() if m else "-"
        
    # --- SONUÇ MANTIĞI GÜNCELLENDİ ---
    metin_upper = metin.upper()
    
    if "KISMEN KABUL" in metin_upper:
        bilgi["Sonuç"] = "⚠️ KISMEN KABUL (Ortak)"
    elif "DAVANIN KABUL" in metin_upper:
        bilgi["Sonuç"] = "✅ KABUL (Davacı Kazandı)"
    elif "DAVANIN RED" in metin_upper:
        bilgi["Sonuç"] = "❌ RED (Davalı Kazandı)"
    elif "KABUL" in metin_upper: # Yedek kontrol
        bilgi["Sonuç"] = "✅ KABUL (Davacı Kazandı)"
    elif "RED" in metin_upper:   # Yedek kontrol
        bilgi["Sonuç"] = "❌ RED (Davalı Kazandı)"
    else:
        bilgi["Sonuç"] = "❓ Belirsiz"
    
    bilgi["Vekalet Ücreti"] = para_bul(metin, "vekalet ücreti")
    return bilgi

# --- 4. ARAYÜZ ---

st.title("🧠 Öğrenen Hukuk Asistanı")
st.markdown("Analizi kontrol edin. **Kabul/Red** durumunda kimin kazandığı otomatik belirtilmiştir.")

# Yan Menü
with st.sidebar:
    st.header("💾 Arşiv Durumu")
    df_db = veritabani_yukle()
    st.metric("Kaydedilen Dosya", len(df_db))
    if not df_db.empty:
        st.dataframe(df_db[["Esas No", "Sonuç"]].tail(5), hide_index=True)
        st.download_button("📂 Arşivi İndir", df_db.to_csv(index=False).encode('utf-8'), "dava_arsivi.csv")

# Dosya Yükleme
uploaded_file = st.file_uploader("Karar Dosyası (PDF)", type="pdf")

if uploaded_file:
    if "analiz_sonucu" not in st.session_state or st.session_state.dosya_adi != uploaded_file.name:
        text = pdf_oku(uploaded_file)
        st.session_state.analiz_sonucu = analiz_yap(text, uploaded_file.name)
        st.session_state.dosya_adi = uploaded_file.name
    
    veri = st.session_state.analiz_sonucu

    # --- DÜZENLEME FORMU ---
    st.subheader("📝 Doğrulama Paneli")
    
    with st.form("dogrulama_formu"):
        st.write("#### 1. Dosya Kimlik Bilgileri")
        yeni_mahkeme = st.text_input("Mahkeme Adı", value=veri["Mahkeme"])
        
        c1, c2 = st.columns(2)
        yeni_esas = c1.text_input("Esas No", value=veri["Esas No"])
        yeni_karar = c2.text_input("Karar No", value=veri["Karar No"])
        
        st.write("---")
        st.write("#### 2. Taraflar ve Sonuç")
        
        c3, c4 = st.columns(2)
        yeni_davaci = c3.text_input("Davacı", value=veri["Davacı"])
        yeni_davali = c4.text_input("Davalı", value=veri["Davalı"])
        
        c5, c6 = st.columns(2)
        
        # --- YENİ SEÇENEK LİSTESİ ---
        secenekler = [
            "✅ KABUL (Davacı Kazandı)", 
            "❌ RED (Davalı Kazandı)", 
            "⚠️ KISMEN KABUL (Ortak)", 
            "❓ Belirsiz"
        ]
        
        # Otomatik gelen veri listede var mı kontrol et, yoksa 'Belirsiz' yap
        varsayilan_index = 3
        if veri["Sonuç"] in secenekler:
            varsayilan_index = secenekler.index(veri["Sonuç"])
            
        yeni_sonuc = c5.selectbox("Karar Sonucu (Kimin Kazandığı)", secenekler, index=varsayilan_index)
        yeni_vekalet = c6.text_input("Vekalet Ücreti", value=veri["Vekalet Ücreti"])
        
        st.write("---")
        kaydet_butonu = st.form_submit_button("✅ Onayla ve Kaydet")
        
        if kaydet_butonu:
            kaydedilecek_veri = {
                "Dosya Adı": veri["Dosya Adı"],
                "Mahkeme": yeni_mahkeme,
                "Esas No": yeni_esas,
                "Karar No": yeni_karar,
                "Davacı": yeni_davaci,
                "Davalı": yeni_davali,
                "Sonuç": yeni_sonuc,
                "Vekalet Ücreti": yeni_vekalet
            }
            veritabanina_kaydet(kaydedilecek_veri)
            st.success(f"Kayıt Başarılı: {yeni_sonuc}")
            st.write("### 📂 Güncel Veritabanı")
            st.dataframe(veritabani_yukle().tail(3))
