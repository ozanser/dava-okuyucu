import streamlit as st
import PyPDF2
import re
import pandas as pd
import os

# --- 1. AYARLAR ---
st.set_page_config(page_title="Öğrenen Hukuk Asistanı", layout="wide", page_icon="🧠")
VERITABANI_DOSYASI = "dogrulanmis_veri.csv"

# --- 2. CSS ---
st.markdown("""
<style>
    .stSuccess { background-color: #d4edda; border-left: 5px solid #28a745; }
    .stError { background-color: #f8d7da; border-left: 5px solid #dc3545; }
    div[data-testid="stForm"] { border: 2px solid #f0f2f6; padding: 20px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 3. FONKSİYONLAR ---

def veritabani_yukle():
    if os.path.exists(VERITABANI_DOSYASI):
        return pd.read_csv(VERITABANI_DOSYASI)
    return pd.DataFrame(columns=["Dosya Adı", "Mahkeme", "Esas No", "Karar No", 
                                 "Davacı", "Davalı", "Sonuç", "Vekalet Ücreti"])

def veritabanina_kaydet(yeni_veri):
    df = veritabani_yukle()
    yeni_satir = pd.DataFrame([yeni_veri])
    df = pd.concat([df, yeni_satir], ignore_index=True)
    df.to_csv(VERITABANI_DOSYASI, index=False)

def metni_temizle(metin):
    """Kelimeleri düzeltir ve bitişik harfleri ayırır."""
    duzeltmeler = {
        r"HAK M": "HAKİM", r"KAT P": "KATİP", r"VEK L": "VEKİL",
        r"T RAZ": "İTİRAZ", r"PTAL": "İPTAL", 
        r"K A B U L": "KABUL", # Ayrı yazılanları birleştir
        r"R E D": "RED"
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

def sonuc_karar_ver(metin):
    """
    Sadece HÜKÜM kısmına odaklanarak sonucu bulur.
    Talep kısmındaki 'kabulünü isteriz' yazılarına kanmaz.
    """
    metin_upper = metin.upper()
    
    # 1. Adım: HÜKÜM bloğunu bulup ayır (Sadece oraya bakacağız)
    # Genelde "HÜKÜM:" veya "GEREĞİ DÜŞÜNÜLDÜ:" ile başlar
    hukum_blok = re.search(r"(HÜKÜM|GEREĞİ DÜŞÜNÜLDÜ)\s*[:;](.*)", metin_upper, re.DOTALL)
    
    # Eğer Hüküm bloğu bulunursa sadece orayı incele, yoksa son 1000 karaktere bak
    inceleme_alani = hukum_blok.group(2) if hukum_blok else metin_upper[-1000:]
    
    # 2. Adım: Öncelik Sırasına Göre Karar Ver
    if "KISMEN KABUL" in inceleme_alani:
        return "⚠️ KISMEN KABUL (Ortak)"
    
    # Sadece "KABUL" kelimesi tehlikeli, "DAVANIN KABULÜNE" kalıbını arıyoruz
    if re.search(r"DAVANIN\s*KABUL", inceleme_alani): 
        return "✅ KABUL (Davacı Kazandı)"
    
    # "İTİRAZIN İPTALİNE" de Davacının kazandığı anlamına gelir (İcra davalarında)
    if re.search(r"İTİRAZIN\s*İPTAL", inceleme_alani):
        return "✅ KABUL (Davacı Kazandı)"
        
    if re.search(r"DAVANIN\s*RED", inceleme_alani):
        return "❌ RED (Davalı Kazandı)"
        
    return "❓ Belirsiz (Manuel Seçiniz)"

def analiz_yap(metin, dosya_adi):
    metin = metni_temizle(metin)
    bilgi = {"Dosya Adı": dosya_adi}
    
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
    
    # Yeni Karar Verme Fonksiyonunu Kullan
    bilgi["Sonuç"] = sonuc_karar_ver(metin)
    bilgi["Vekalet Ücreti"] = para_bul(metin, "vekalet ücreti")
    
    return bilgi

# --- 4. ARAYÜZ ---

st.title("🧠 Öğrenen Hukuk Asistanı v2")
st.markdown("Hüküm algoritması güçlendirildi. Hatalıysa düzeltip kaydederek sistemi eğitin.")

with st.sidebar:
    st.header("💾 Arşiv")
    df_db = veritabani_yukle()
    st.metric("Kaydedilen Dosya", len(df_db))
    if not df_db.empty:
        st.dataframe(df_db[["Esas No", "Sonuç"]].tail(5), hide_index=True)
        st.download_button("İndir", df_db.to_csv(index=False).encode('utf-8'), "arsiv.csv")

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
        yeni_mahkeme = st.text_input("Mahkeme", value=veri["Mahkeme"])
        c1, c2 = st.columns(2)
        yeni_esas = c1.text_input("Esas No", value=veri["Esas No"])
        yeni_karar = c2.text_input("Karar No", value=veri["Karar No"])
        
        st.write("#### 2. Sonuç ve Maliyet")
        c3, c4 = st.columns(2)
        yeni_davaci = c3.text_input("Davacı", value=veri["Davacı"])
        yeni_davali = c4.text_input("Davalı", value=veri["Davalı"])
        
        c5, c6 = st.columns(2)
        
        # Seçenek Listesi
        secenekler = [
            "✅ KABUL (Davacı Kazandı)", 
            "❌ RED (Davalı Kazandı)", 
            "⚠️ KISMEN KABUL (Ortak)", 
            "❓ Belirsiz (Manuel Seçiniz)"
        ]
        
        # Otomatik seçimi yap, listede yoksa 'Belirsiz' seç
        idx = 3
        if veri["Sonuç"] in secenekler:
            idx = secenekler.index(veri["Sonuç"])
            
        yeni_sonuc = c5.selectbox("Karar Sonucu", secenekler, index=idx)
        yeni_vekalet = c6.text_input("Vekalet Ücreti", value=veri["Vekalet Ücreti"])
        
        # Kaydet
        st.write("---")
        if st.form_submit_button("✅ Doğrula ve Kaydet"):
            kayit = {k: v for k, v in veri.items()} # Eskileri kopyala
            # Yenileri üzerine yaz
            kayit.update({
                "Mahkeme": yeni_mahkeme, "Esas No": yeni_esas, "Karar No": yeni_karar,
                "Davacı": yeni_davaci, "Davalı": yeni_davali, 
                "Sonuç": yeni_sonuc, "Vekalet Ücreti": yeni_vekalet
            })
            veritabanina_kaydet(kayit)
            st.success("Kayıt Başarılı!")
            st.dataframe(veritabani_yukle().tail(3))
