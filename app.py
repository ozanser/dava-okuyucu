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
</style>
""", unsafe_allow_html=True)

# --- 3. FONKSİYONLAR ---

def veritabani_yukle():
    """Varsa eski kayıtları yükler, yoksa boş yaratır."""
    if os.path.exists(VERITABANI_DOSYASI):
        return pd.read_csv(VERITABANI_DOSYASI)
    else:
        return pd.DataFrame(columns=["Dosya Adı", "Mahkeme", "Esas No", "Karar No", 
                                     "Davacı", "Davalı", "Sonuç", "Vekalet Ücreti"])

def veritabanina_kaydet(yeni_veri):
    """Kullanıcının düzelttiği veriyi Excel/CSV'ye ekler."""
    df = veritabani_yukle()
    # Yeni veriyi DataFrame'e çevir (tek satırlık)
    yeni_satir = pd.DataFrame([yeni_veri])
    # Eski veriyle birleştir
    df = pd.concat([df, yeni_satir], ignore_index=True)
    # Kaydet
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
        
    # Sonuç Analizi
    if "KABUL" in metin.upper(): bilgi["Sonuç"] = "KABUL"
    elif "RED" in metin.upper(): bilgi["Sonuç"] = "RED"
    else: bilgi["Sonuç"] = "Belirsiz"
    
    bilgi["Vekalet Ücreti"] = para_bul(metin, "vekalet ücreti")
    return bilgi

# --- 4. ARAYÜZ ---

st.title("🧠 Öğrenen Hukuk Asistanı")
st.markdown("Yapay zeka hatalıysa kutucukları düzeltip **'Veritabanına Kaydet'** butonuna basın. Sistem bunu hafızasına alacaktır.")

# Yan Menü: Veritabanı Durumu
with st.sidebar:
    st.header("💾 Hafıza Durumu")
    df_db = veritabani_yukle()
    st.metric("Kaydedilen Dava Sayısı", len(df_db))
    if not df_db.empty:
        st.download_button("📂 Veritabanını İndir (Excel)", df_db.to_csv().encode('utf-8'), "hafiza.csv")

# Dosya Yükleme
uploaded_file = st.file_uploader("Dosya Seç", type="pdf")

if uploaded_file:
    # Analiz sadece dosya değişince yapılsın diye session state kullanıyoruz
    if "analiz_sonucu" not in st.session_state or st.session_state.dosya_adi != uploaded_file.name:
        text = pdf_oku(uploaded_file)
        st.session_state.analiz_sonucu = analiz_yap(text, uploaded_file.name)
        st.session_state.dosya_adi = uploaded_file.name
    
    veri = st.session_state.analiz_sonucu

    # --- DÜZENLEME FORMU ---
    st.subheader("📝 Analiz ve Doğrulama Ekranı")
    
    with st.form("dogrulama_formu"):
        col1, col2 = st.columns(2)
        
        # Kutucuklar artık düzenlenebilir! (value=... diyerek varsayılanı AI tahmini yapıyoruz)
        yeni_mahkeme = col1.text_input("Mahkeme", value=veri["Mahkeme"])
        yeni_esas = col2.text_input("Esas No", value=veri["Esas No"])
        
        yeni_davaci = col1.text_input("Davacı", value=veri["Davacı"])
        yeni_davali = col2.text_input("Davalı", value=veri["Davalı"])
        
        yeni_sonuc = col1.selectbox("Sonuç", ["KABUL", "RED", "KISMEN KABUL", "Belirsiz"], 
                                    index=["KABUL", "RED", "KISMEN KABUL", "Belirsiz"].index(veri["Sonuç"]) if veri["Sonuç"] in ["KABUL", "RED"] else 3)
        
        yeni_vekalet = col2.text_input("Vekalet Ücreti", value=veri["Vekalet Ücreti"])
        
        # Kaydet Butonu
        kaydet_butonu = st.form_submit_button("✅ Doğrula ve Hafızaya Kaydet")
        
        if kaydet_butonu:
            # Kullanıcının son yazdığı (belki düzelttiği) verileri paketle
            kaydedilecek_veri = {
                "Dosya Adı": veri["Dosya Adı"],
                "Mahkeme": yeni_mahkeme,
                "Esas No": yeni_esas,
                "Karar No": veri["Karar No"], # Bunu formda göstermedik ama arkada saklayalım
                "Davacı": yeni_davaci,
                "Davalı": yeni_davali,
                "Sonuç": yeni_sonuc,
                "Vekalet Ücreti": yeni_vekalet
            }
            
            # Veritabanına Yaz
            veritabanina_kaydet(kaydedilecek_veri)
            st.success("Bilgiler 'dogrulanmis_veri.csv' dosyasına başarıyla kaydedildi! Sistem bunu hafızasına aldı.")
            
            # Güncel tabloyu göster
            st.write("### 📂 Güncel Veritabanı Kayıtları")
            st.dataframe(veritabani_yukle().tail(5)) # Son 5 kaydı göster
