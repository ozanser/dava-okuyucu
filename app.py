import streamlit as st
import PyPDF2
import re
import pandas as pd

# --- 1. SAYFA YAPILANDIRMASI ---
st.set_page_config(
    page_title="Hukuk Asistanı Pro", 
    layout="wide", 
    page_icon="⚖️",
    initial_sidebar_state="expanded"
)

# --- 2. ÖZEL CSS (TASARIM) ---
st.markdown("""
<style>
    /* Başlık Stilleri */
    h1 { color: #2c3e50; font-family: 'Helvetica Neue', sans-serif; }
    h3 { color: #34495e; border-bottom: 2px solid #ecf0f1; padding-bottom: 10px; }
    
    /* Mesaj Kutuları */
    .stSuccess { background-color: #d4edda; color: #155724; border-left: 5px solid #28a745; }
    .stError { background-color: #f8d7da; color: #721c24; border-left: 5px solid #dc3545; }
    .stWarning { background-color: #fff3cd; color: #856404; border-left: 5px solid #ffeeba; }
    
    /* Footer Gizle */
    footer {visibility: hidden;}
    
    /* Buton Stili */
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 3. FONKSİYONLAR ---

def metni_temizle_ve_duzelt(metin):
    """OCR hatalarını temizler."""
    duzeltmeler = {
        r"HAK M": "HAKİM", r"KAT P": "KATİP", r"VEK L": "VEKİL",
        r"T RAZ": "İTİRAZ", r"PTAL": "İPTAL", r"TAHL YE": "TAHLİYE",
        r"DAVACI": "DAVACI", r"DAVALI": "DAVALI", r"HÜKÜM": "HÜKÜM",
        r"GEREKÇEL KARAR": "GEREKÇELİ KARAR",
        r"YÜKLET LMES NE": "YÜKLETİLMESİNE",
        r"DAVANIN KABULÜNE": "DAVANIN KABULÜNE",
        r"DAVANIN REDD NE": "DAVANIN REDDİNE"
    }
    # Satır sonlarını ve fazla boşlukları temizle
    temiz_metin = metin.replace("\n", " ").strip()
    temiz_metin = re.sub(r'\s+', ' ', temiz_metin)
    
    for bozuk, duzgun in duzeltmeler.items():
        temiz_metin = re.sub(bozuk, duzgun, temiz_metin, flags=re.IGNORECASE)
    return temiz_metin

def pdf_metin_oku(dosya):
    okuyucu = PyPDF2.PdfReader(dosya)
    metin = ""
    for sayfa in okuyucu.pages:
        metin += sayfa.extract_text() or ""
    return metin

def sonuc_ve_mali_analiz(metin):
    """Kazanma/Kaybetme ve Mali durum analizi."""
    analiz = {
        "Kazanan": "Belirsiz", "Kaybeden": "Belirsiz",
        "Vekalet Ücreti": "-", "Yargılama Gideri": "-",
        "Durum": "⚠️ Belirsiz"
    }
    
    # Regex Kalıpları (Hata veren yer burasıydı, şimdi düzgün)
    kabul_kalibi = r"DAVANIN\s*KABUL"
    red_kalibi = r"DAVANIN\s*RED"
    kismen_kalibi = r"KISMEN\s*KABUL"
    
    if re.search(kismen_kalibi, metin, re.IGNORECASE):
        analiz.update({
            "Durum": "⚠️ KISMEN KABUL", 
            "Kazanan": "Ortak", 
            "Kaybeden": "Ortak", 
            "Vekalet Ücreti": "Oranına Göre", 
            "Yargılama Gideri": "Paylaştırılır"
        })
    elif re.search(kabul_kalibi, metin, re.IGNORECASE):
        analiz.update({
            "Kazanan": "DAVACI (Alacaklı)", 
            "Kaybeden": "DAVALI (Borçlu)", 
            "Durum": "✅ KABUL (Davacı Kazandı)", 
            "Vekalet Ücreti": "Davalı öder ➡️ Davacı Avukatına", 
            "Yargılama Gideri": "Davalı öder"
        })
    elif re.search(red_kalibi, metin, re.IGNORECASE):
        analiz.update({
            "Kazanan": "DAVALI (Borçlu)", 
            "Kaybeden": "DAVACI (Alacaklı)", 
            "Durum": "❌ RED (Davacı Kaybetti)", 
            "Vekalet Ücreti": "Davacı öder ➡️ Davalı Avukatına", 
            "Yargılama Gideri": "Davacı öder"
        })
    return analiz

def detayli_analiz(ham_metin, dosya_adi):
    metin = metni_temizle_ve_duzelt(ham_metin)
    bilgiler = {"Dosya Adı": dosya_adi}
    
    regex_listesi = {
        "Mahkeme": r"(T\.?C\.?.*?MAHKEMES.*?)Esas",
        "Esas No": r"ESAS\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Karar No": r"KARAR\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Davacı": r"DAVACI\s*.*?[:;]\s*(.*?)(?=VEKİL|DAVALI)",
        "Davalı": r"DAVALI\s*.*?[:;]\s*(.*?)(?=VEKİL|DAVA|KONU)"
    }
    
    for baslik, kalip in regex_listesi.items():
        bulunan = re.search(kalip, metin, re.IGNORECASE)
        bilgiler[baslik] = bulunan.group(1).strip() if bulunan else "-"

    hukum_bul = re.search(r"(HÜKÜM|GEREĞİ DÜŞÜNÜLDÜ)\s*[:;](.*?)(?=UYAP|GEREKÇELİ KARAR|$)", metin, re.IGNORECASE | re.DOTALL)
    bilgiler["Hüküm Metni"] = hukum_bul.group(2).strip()[:1500] if hukum_bul else "Ayrıştırılamadı."
    
    bilgiler.update(sonuc_ve_mali_analiz(metin))
    return bilgiler

# --- 4. ARAYÜZ ---

with st.sidebar:
    st.title("⚖️ Hukuk Asistanı")
    st.markdown("---")
    st.info("Bu sistem mahkeme kararlarını ve dava dilekçelerini otomatik analiz eder.")
    st.write("© 2025 Hukuk Teknolojileri")

st.title("⚖️ Akıllı Karar Analiz Paneli")
st.markdown("Mahkeme kararlarını yükleyin, sistem **sonucu, kazananı ve ödemeleri** çıkarsın.")

uploaded_files = st.file_uploader("Dosyaları Buraya Bırakın (PDF)", type="pdf", accept_multiple_files=True)

if uploaded_files:
    tum_veriler = []
    
    with st.spinner('Yapay zeka dosyaları tarıyor...'):
        for dosya in uploaded_files:
            raw_text = pdf_metin_oku(dosya)
            if len(raw_text) > 50:
                veri = detayli_analiz(raw_text, dosya.name)
                tum_veriler.append(veri)
            
    if tum_veriler:
        df = pd.DataFrame(tum_veriler)
        
        # Dosya Seçimi ve Excel İndirme
        st.write("---")
        col_sel1, col_sel2 = st.columns([3, 1])
        with col_sel1:
            secilen = st.selectbox("📂 İncelemek İstediğiniz Dosyayı Seçin:", df["Dosya Adı"].tolist())
        with col_sel2:
            st.write("") 
            st.write("") 
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Excel İndir", csv, "ozet.csv", "text/csv")

        if secilen:
            row = df[df["Dosya Adı"] == secilen].iloc[0]
            
            # SEKME (TAB) YAPISI
            tab1, tab2, tab3 = st.tabs(["📊 Özet & Sonuç", "💰 Mali Tablo", "📜 Orijinal Metin"])
            
            with tab1:
                st.subheader("Karar Özeti")
                c1, c2 = st.columns(2)
                
                # Renkli Sonuç Gösterimi
                if "KABUL" in row["Durum"]:
                    c1.success(f"**SONUÇ:** {row['Durum']}")
                    c2.success(f"**KAZANAN:** {row['Kazanan']}")
                elif "RED" in row["Durum"]:
                    c1.error(f"**SONUÇ:** {row['Durum']}")
                    c2.error(f"**KAZANAN:** {row['Kazanan']}")
                else:
                    c1.warning(f"**SONUÇ:** {row['Durum']}")
                
                st.markdown("---")
                
                # Detay Bilgiler
                col_d1, col_d2, col_d3 = st.columns(3)
                col_d1.text_input("📍 Mahkeme", row["Mahkeme"], disabled=True)
                col_d2.text_input("🔢 Esas No", row["Esas No"], disabled=True)
                col_d3.text_input("🔢 Karar No", row["Karar No"], disabled=True)
                
                col_k1, col_k2 = st.columns(2)
                col_k1.text_input("👤 Davacı", row["Davacı"], disabled=True)
                col_k2.text_input("👤 Davalı", row["Davalı"], disabled=True)

            with tab2:
                st.subheader("Mali Yükümlülükler")
                st.info("Mahkemenin belirlediği ödeme yükümlülükleri:")
                
                # HTML ile Özel Tasarım Kartlar
                st.markdown(f"""
                <div style="display: flex; gap: 20px;">
                    <div style="flex: 1; padding: 20px; background-color: #f1f3f5; border-radius: 10px; border: 1px solid #ced4da;">
                        <h4 style="color: #d63384;">⚖️ Vekalet Ücreti</h4>
                        <p style="font-size: 18px; font-weight: bold;">{row['Vekalet Ücreti']}</p>
                    </div>
                    <div style="flex: 1; padding: 20px; background-color: #f1f3f5; border-radius: 10px; border: 1px solid #ced4da;">
                        <h4 style="color: #0d6efd;">📂 Yargılama Gideri</h4>
                        <p style="font-size: 18px; font-weight: bold;">{row['Yargılama Gideri']}</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
            with tab3:
                st.subheader("Mahkeme Karar Metni")
                st.caption("Aşağıdaki metin PDF'ten otomatik çekilmiştir.")
                st.text_area("Tam Metin", row["Hüküm Metni"], height=400)

    else:
        st.info("Analiz edilecek dosya bekleniyor...")
