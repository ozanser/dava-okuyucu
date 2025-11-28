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

# --- 2. CSS TASARIMI ---
st.markdown("""
<style>
    h1 { color: #2c3e50; font-family: 'Helvetica Neue', sans-serif; }
    .stSuccess { background-color: #d4edda; border-left: 5px solid #28a745; }
    .stError { background-color: #f8d7da; border-left: 5px solid #dc3545; }
    .stWarning { background-color: #fff3cd; border-left: 5px solid #ffc107; }
    footer {visibility: hidden;}
    .mali-kutu {
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        border: 1px solid #e0e0e0;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# --- 3. FONKSİYONLAR ---

def metni_temizle_ve_duzelt(metin):
    """OCR hatalarını ve Türkçe karakterleri düzeltir."""
    duzeltmeler = {
        r"HAK M": "HAKİM", r"KAT P": "KATİP", r"VEK L": "VEKİL",
        r"T RAZ": "İTİRAZ", r"PTAL": "İPTAL", r"TAHL YE": "TAHLİYE",
        r"DAVACI": "DAVACI", r"DAVALI": "DAVALI", r"HÜKÜM": "HÜKÜM",
        r"TL": "TL", r"TL'nin": "TL",
        r"DAVANIN KABULÜNE": "DAVANIN KABULÜNE"
    }
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

def para_bul(metin, anahtar_kelime):
    """
    Belirli bir kelimenin yanındaki para tutarını çeker.
    Örn: "1.500,00 TL harç" -> 1.500,00 TL
    """
    # Regex: Sayı (noktalı/virgüllü) + TL kelimesini arar
    kalip = fr"([\d\.,]+\s*TL).*?{anahtar_kelime}|{anahtar_kelime}.*?([\d\.,]+\s*TL)"
    bulunan = re.search(kalip, metin, re.IGNORECASE)
    
    if bulunan:
        # Grup 1 (önceki sayı) veya Grup 2 (sonraki sayı) döner
        tutar = bulunan.group(1) if bulunan.group(1) else bulunan.group(2)
        return tutar
    return "-"

def sonuc_ve_mali_analiz(metin):
    """Kazanma durumu ve mali detay analizi."""
    analiz = {
        "Kazanan": "Belirsiz", "Kaybeden": "Belirsiz",
        "Vekalet Yönü": "-", "Gider Yönü": "-",
        "Vekalet Tutar": "-", "Harç Tutar": "-",
        "Faiz": "Yok",
        "Durum": "⚠️ Belirsiz"
    }
    
    # 1. Durum Analizi (Kabul/Red)
    if re.search(r"KISMEN\s*KABUL", metin, re.IGNORECASE):
        analiz["Durum"] = "⚠️ KISMEN KABUL"
        analiz["Kazanan"] = "Ortak"
        analiz["Vekalet Yönü"] = "Karşılıklı"
        
    elif re.search(r"DAVANIN\s*KABUL", metin, re.IGNORECASE):
        analiz.update({"Kazanan": "DAVACI", "Kaybeden": "DAVALI", "Durum": "✅ KABUL"})
        analiz["Vekalet Yönü"] = "Davalı ➡️ Davacı Avukatına"
        analiz["Gider Yönü"] = "Davalı Öder"
        
    elif re.search(r"DAVANIN\s*RED", metin, re.IGNORECASE):
        analiz.update({"Kazanan": "DAVALI", "Kaybeden": "DAVACI", "Durum": "❌ RED"})
        analiz["Vekalet Yönü"] = "Davacı ➡️ Davalı Avukatına"
        analiz["Gider Yönü"] = "Davacı Öder"

    # 2. Rakam Avcısı
    analiz["Vekalet Tutar"] = para_bul(metin, "vekalet ücreti")
    analiz["Harç Tutar"] = para_bul(metin, "harc")

    # 3. Faiz Dedektifi
    if re.search(r"(yasal|ticari|avans)\s*faiz", metin, re.IGNORECASE):
        analiz["Faiz"] = "⚠️ Kararda FAİZ Var!"
    else:
        analiz["Faiz"] = "Faiz belirtilmemiş."

    return analiz

def detayli_analiz(ham_metin, dosya_adi):
    metin = metni_temizle_ve_duzelt(ham_metin)
    bilgiler = {"Dosya Adı": dosya_adi}
    
    # REGEX LİSTESİ (Hata burada çıkıyordu, şimdi düzgün)
    regex_listesi = {
        "Mahkeme": r"(T\.?C\.?.*?MAHKEMES.*?)Esas",
        "Esas No": r"ESAS\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Karar No": r"KARAR\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Davacı": r"DAVACI\s*.*?[:;]\s*(.*?)(?=VEKİL|DAVALI)",
        "Davalı": r"DAVALI\s*.*?[:;]\s*(.*?)(?=VEKİL|DAVA|KONU)"
    }
    
    for k, v in regex_listesi.items():
        m = re.search(v, metin, re.IGNORECASE)
        bilgiler[k] = m.group(1).strip() if m else "-"

    hukum = re.search(r"(HÜKÜM|GEREĞİ DÜŞÜNÜLDÜ)\s*[:;](.*?)(?=UYAP|GEREKÇELİ KARAR|$)", metin, re.IGNORECASE | re.DOTALL)
    bilgiler["Hüküm Metni"] = hukum.group(2).strip()[:1500] if hukum else "Ayrıştırılamadı."
    
    bilgiler.update(sonuc_ve_mali_analiz(metin))
    return bilgiler

# --- 4. ARAYÜZ ---

st.title("⚖️ Hukuk Asistanı: Mali Analiz Pro")
st.markdown("Mahkeme kararlarındaki **tutar, harç ve faiz** detaylarını otomatik analiz eder.")

uploaded_files = st.file_uploader("Karar Dosyası (PDF)", type="pdf", accept_multiple_files=True)

if uploaded_files:
    tum_veriler = []
    with st.spinner('Analiz yapılıyor...'):
        for dosya in uploaded_files:
            txt = pdf_metin_oku(dosya)
            if len(txt) > 50:
                tum_veriler.append(detayli_analiz(txt, dosya.name))
            
    if tum_veriler:
        df = pd.DataFrame(tum_veriler)
        
        # Seçim Kutusu
        st.write("---")
        col_sel1, col_sel2 = st.columns([3, 1])
        with col_sel1:
            secilen = st.selectbox("📂 İncelemek İstediğiniz Dosyayı Seçin:", df["Dosya Adı"].tolist())
        with col_sel2:
            st.write("")
            st.write("")
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Excel İndir", csv, "mali_analiz.csv", "text/csv")
        
        if secilen:
            row = df[df["Dosya Adı"] == secilen].iloc[0]
            
            # --- SEKME YAPISI ---
            tab1, tab2, tab3 = st.tabs(["📊 Özet", "💸 Mali Tablo", "📜 Metin"])
            
            with tab1:
                st.subheader("Karar Özeti")
                c1, c2 = st.columns(2)
                if "KABUL" in row["Durum"]:
                    c1.success(f"**SONUÇ:** {row['Durum']}")
                elif "RED" in row["Durum"]:
                    c1.error(f"**SONUÇ:** {row['Durum']}")
                else:
                    c1.warning(f"**SONUÇ:** {row['Durum']}")
                
                c2.info(f"**Mahkeme:** {row['Mahkeme']}")
                
                col_d1, col_d2 = st.columns(2)
                col_d1.text_input("Davacı", row["Davacı"], disabled=True)
                col_d2.text_input("Davalı", row["Davalı"], disabled=True)
                
                col_no1, col_no2 = st.columns(2)
                col_no1.text_input("Esas No", row["Esas No"], disabled=True)
                col_no2.text_input("Karar No", row["Karar No"], disabled=True)

            with tab2:
                st.subheader("💰 Para Akışı ve Yükümlülükler")
                
                # Özel HTML Kart Tasarımı
                col_m1, col_m2, col_m3 = st.columns(3)
                
                with col_m1:
                    st.markdown(f"""
                    <div class="mali-kutu" style="background-color:#e8f4fd;">
                        <h4 style="color:#007bff;">⚖️ Vekalet Ücreti</h4>
                        <p><b>Yön:</b> {row['Vekalet Yönü']}</p>
                        <p style="font-size:22px; color:#0056b3;"><b>{row['Vekalet Tutar']}</b></p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_m2:
                    st.markdown(f"""
                    <div class="mali-kutu" style="background-color:#fff3cd;">
                        <h4 style="color:#856404;">🏛️ Harç & Gider</h4>
                        <p><b>Yön:</b> {row['Gider Yönü']}</p>
                        <p style="font-size:22px; color:#856404;"><b>{row['Harç Tutar']}</b></p>
                    </div>
                    """, unsafe_allow_html=True)

                with col_m3:
                    faiz_renk = "#d4edda" if "Yok" in row['Faiz'] else "#f8d7da"
                    faiz_text = "#155724" if "Yok" in row['Faiz'] else "#721c24"
                    st.markdown(f"""
                    <div class="mali-kutu" style="background-color:{faiz_renk};">
                        <h4 style="color:{faiz_text};">📈 Faiz Durumu</h4>
                        <p>Faiz işletiliyor mu?</p>
                        <p style="font-size:18px; font-weight:bold; color:{faiz_text};">{row['Faiz']}</p>
                    </div>
                    """, unsafe_allow_html=True)

            with tab3:
                st.subheader("Orijinal Karar Metni")
                st.text_area("Hüküm", row["Hüküm Metni"], height=400)
                
    else:
        st.info("Analiz edilecek dosya bekleniyor...")
