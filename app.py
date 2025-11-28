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
    /* Form alanlarını belirginleştir */
    div[data-testid="stForm"] {
        border: 2px solid #f0f2f6;
        padding: 20px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. FONKSİYONLAR ---

def veritabani_yukle():
    """Varsa eski kayıtları yükler, yoksa boş yaratır."""
    if os.path.exists(VERITABANI_DOSYASI):
        return pd.read_csv(VERITABANI_DOSYASI)
    else:
        # Sütunları netleştiriyoruz
        return pd.DataFrame(columns=["Dosya Adı", "Mahkeme", "Esas No", "Karar No", 
                                     "Davacı", "Davalı", "Sonuç", "Vekalet Ücreti"])

def veritabanina_kaydet(yeni_veri):
    """Kullanıcının düzelttiği veriyi CSV'ye ekler."""
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
    m = re.search(fr"([\d\.,]+\s*TL).*?{kelime}|{kelime}.*?([\d\.,]+\s*TL)", metin, re.IGNORECASE)
    return (m.group(1) or m.group(2)) if m else "-"

def analiz_yap(metin, dosya_adi):
    metin = metni_temizle(metin)
    bilgi = {"Dosya Adı": dosya_adi}
    
    # Regex Aramaları (Esas ve Karar No burada aranıyor)
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
st.markdown("Yapay zeka analizini kontrol edin, **hatalı kısımları (özellikle Esas/Karar No)** düzeltip kaydedin.")

# Yan Menü: Veritabanı Durumu
with st.sidebar:
    st.header("💾 Arşiv Durumu")
    df_db = veritabani_yukle()
    st.metric("Kaydedilen Dosya", len(df_db))
    if not df_db.empty:
        st.write("Son Eklenenler:")
        st.dataframe(df_db[["Esas No", "Sonuç"]].tail(5), hide_index=True)
        st.download_button("📂 Arşivi İndir (Excel)", df_db.to_csv(index=False).encode('utf-8'), "dava_arsivi.csv")

# Dosya Yükleme
uploaded_file = st.file_uploader("Karar Dosyası (PDF)", type="pdf")

if uploaded_file:
    # Session state ile analizi hafızada tut (sayfa yenilenince gitmesin)
    if "analiz_sonucu" not in st.session_state or st.session_state.dosya_adi != uploaded_file.name:
        text = pdf_oku(uploaded_file)
        st.session_state.analiz_sonucu = analiz_yap(text, uploaded_file.name)
        st.session_state.dosya_adi = uploaded_file.name
    
    veri = st.session_state.analiz_sonucu

    # --- DÜZENLEME FORMU (Burayı Geliştirdik) ---
    st.subheader("📝 Analiz ve Doğrulama Paneli")
    st.info("Aşağıdaki kutucuklardaki bilgiler PDF'ten otomatik çekildi. Hata varsa üzerine tıklayıp düzeltebilirsiniz.")
    
    with st.form("dogrulama_formu"):
        st.write("#### 1. Dosya Kimlik Bilgileri")
        # Mahkeme tek satır
        yeni_mahkeme = st.text_input("Mahkeme Adı", value=veri["Mahkeme"])
        
        # Esas ve Karar No Yan Yana (İsteğin üzerine eklendi)
        c1, c2 = st.columns(2)
        yeni_esas = c1.text_input("Esas No (Örn: 2024/1048)", value=veri["Esas No"])
        yeni_karar = c2.text_input("Karar No (Örn: 2025/1155)", value=veri["Karar No"])
        
        st.write("---")
        st.write("#### 2. Taraflar ve Sonuç")
        
        c3, c4 = st.columns(2)
        yeni_davaci = c3.text_input("Davacı", value=veri["Davacı"])
        yeni_davali = c4.text_input("Davalı", value=veri["Davalı"])
        
        c5, c6 = st.columns(2)
        # Sonuç Seçim Kutusu
        secenekler = ["KABUL", "RED", "KISMEN KABUL", "Belirsiz"]
        varsayilan_index = 0
        if veri["Sonuç"] in secenekler:
            varsayilan_index = secenekler.index(veri["Sonuç"])
            
        yeni_sonuc = c5.selectbox("Karar Sonucu", secenekler, index=varsayilan_index)
        yeni_vekalet = c6.text_input("Vekalet Ücreti", value=veri["Vekalet Ücreti"])
        
        st.write("---")
        # Kaydet Butonu
        kaydet_butonu = st.form_submit_button("✅ Onayla ve Veritabanına Kaydet")
        
        if kaydet_butonu:
            # Kullanıcının son haliyle verileri paketle
            kaydedilecek_veri = {
                "Dosya Adı": veri["Dosya Adı"],
                "Mahkeme": yeni_mahkeme,
                "Esas No": yeni_esas,   # Artık düzenlenmiş hali gidiyor
                "Karar No": yeni_karar, # Artık düzenlenmiş hali gidiyor
                "Davacı": yeni_davaci,
                "Davalı": yeni_davali,
                "Sonuç": yeni_sonuc,
                "Vekalet Ücreti": yeni_vekalet
            }
            
            # Veritabanına Yaz
            veritabanina_kaydet(kaydedilecek_veri)
            st.success(f"Dosya ({yeni_esas}) başarıyla arşive eklendi!")
            
            # Güncel tabloyu hemen göster
            st.write("### 📂 Güncel Veritabanı")
            st.dataframe(veritabani_yukle().tail(3))
