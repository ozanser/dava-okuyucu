import streamlit as st
import PyPDF2
import re
import pandas as pd

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Gerekçeli Karar Analizcisi", layout="wide", page_icon="⚖️")

# --- OCR DÜZELTME MOTORU ---
def metni_temizle_ve_duzelt(metin):
    """
    PDF'ten gelen bozuk Türkçe karakterleri ve OCR hatalarını onarır.
    Örn: 'HAK M' -> 'HAKİM', 'T RAZ' -> 'İTİRAZ'
    """
    duzeltmeler = {
        r"HAK M": "HAKİM",
        r"KAT P": "KATİP",
        r"VEK L": "VEKİL",
        r"M LLET": "MİLLET",
        r"T RAZ": "İTİRAZ",
        r"PTAL": "İPTAL",
        r"TAHL YE": "TAHLİYE",
        r"GEREKÇEL KARAR": "GEREKÇELİ KARAR",
        r"DAVACI": "DAVACI",
        r"DAVALI": "DAVALI",
        r"HÜKÜM": "HÜKÜM",
        r"GERE DÜ ÜNÜLDÜ": "GEREĞİ DÜŞÜNÜLDÜ",
        r"ba latılan": "başlatılan",
        r"anla ılmakla": "anlaşılmakla"
    }
    
    # Önce genel boşlukları temizle
    temiz_metin = metin.replace("\n", " ").strip()
    
    # Regex ile kelime düzeltmeleri yap
    for bozuk, duzgun in duzeltmeler.items():
        temiz_metin = re.sub(bozuk, duzgun, temiz_metin, flags=re.IGNORECASE)
        
    return temiz_metin

# --- PDF OKUMA ---
def pdf_metin_oku(dosya):
    okuyucu = PyPDF2.PdfReader(dosya)
    metin = ""
    for sayfa in okuyucu.pages:
        metin += sayfa.extract_text() or ""
    return metin

# --- ANALİZ MOTORU ---
def detayli_analiz(ham_metin, dosya_adi):
    # 1. Önce metni tamir et
    metin = metni_temizle_ve_duzelt(ham_metin)
    
    bilgiler = {"Dosya Adı": dosya_adi}
    
    # --- REGEX TANIMLARI (Senin dosya formatına özel) ---
    regex_listesi = {
        "Mahkeme": r"(T\.?C\.?.*?MAHKEMES.*?)Esas",
        "Esas No": r"ESAS\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Karar No": r"KARAR\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Hakim": r"HAKİM\s*[:;]?\s*['\"]?,?[:]?\s*(.*?)(?=\d|KATİP)",
        "Davacı": r"DAVACI\s*.*?[:;]\s*(.*?)(?=VEKİL|DAVALI)",
        "Davalı": r"DAVALI\s*.*?[:;]\s*(.*?)(?=VEKİL|DAVA|KONU)",
        "Dava Türü": r"DAVA\s*[:;]\s*(.*?)(?=DAVA TARİHİ)",
        "Dava Tarihi": r"DAVA TARİHİ\s*['\"]?,?[:]?\s*(\d{1,2}/\d{1,2}/\d{4})",
        "Karar Tarihi": r"KARAR TARİHİ\s*['\"]?,?[:]?\s*(\d{1,2}/\d{1,2}/\d{4})",
    }
    
    for baslik, kalip in regex_listesi.items():
        bulunan = re.search(kalip, metin, re.IGNORECASE)
        if bulunan:
            # Gereksiz karakterleri temizle (tırnak, virgül vb.)
            temiz_veri = bulunan.group(1).replace('"', '').replace(',', '').strip()
            bilgiler[baslik] = temiz_veri
        else:
            bilgiler[baslik] = "-"

    # --- HÜKÜM / SONUÇ BULMA (En Kritik Yer) ---
    # Hüküm genellikle "HÜKÜM:" kelimesinden sonra gelir ve maddeler halindedir.
    hukum_kalibi = r"HÜKÜM\s*[:;].*?(\d-.*?)(?=UYAP|GEREKÇELİ KARAR YAZILDIĞI TARİH|$)"
    hukum_bul = re.search(hukum_kalibi, metin, re.IGNORECASE)
    
    if hukum_bul:
        bilgiler["Detaylı Hüküm"] = hukum_bul.group(1).strip()
    else:
        # Eğer HÜKÜM bloğu bulunamazsa son sayfalara bak
        bilgiler["Detaylı Hüküm"] = "Hüküm bloğu net ayrıştırılamadı."

    # --- KISA SONUÇ ÇIKARIMI (Kazanıldı mı?) ---
    # Metin içinde "DAVANIN KABULÜNE" veya "REDDİNE" geçiyor mu?
    if "DAVANIN KABULÜNE" in metin.upper():
        bilgiler["Sonuç Özeti"] = "✅ KABUL (Davacı Kazandı)"
    elif "DAVANIN REDDİNE" in metin.upper():
        bilgiler["Sonuç Özeti"] = "❌ RED (Davacı Kaybetti)"
    elif "KISMEN KABUL" in metin.upper():
        bilgiler["Sonuç Özeti"] = "⚠️ KISMEN KABUL"
    else:
        bilgiler["Sonuç Özeti"] = "Belirsiz"

    return bilgiler

# --- ARAYÜZ ---
st.title("⚖️ Gerekçeli Karar Okuyucu")
st.markdown("**Desteklenen Format:** Uyap Mahkeme Kararları ve Dava Dilekçeleri")

# Çoklu Dosya Yükleme
uploaded_files = st.file_uploader("Dosyaları Sürükleyin (PDF)", type="pdf", accept_multiple_files=True)

if uploaded_files:
    tum_veriler = []
    
    for dosya in uploaded_files:
        raw_text = pdf_metin_oku(dosya)
        if len(raw_text) > 50:
            analiz_sonucu = detayli_analiz(raw_text, dosya.name)
            tum_veriler.append(analiz_sonucu)
    
    if tum_veriler:
        df = pd.DataFrame(tum_veriler)
        
        # --- ÜST ÖZET KARTLARI ---
        st.write("---")
        c1, c2, c3 = st.columns(3)
        c1.metric("Yüklenen Dosya", len(df))
        c2.metric("Kabul Kararı", len(df[df["Sonuç Özeti"].str.contains("KABUL")]))
        c3.metric("Red Kararı", len(df[df["Sonuç Özeti"].str.contains("RED")]))
        
        # --- TABLO GÖRÜNÜMÜ ---
        st.subheader("📄 Dosya Listesi")
        # Önemli kolonları öne alalım
        ozet_tablo = df[["Dosya Adı", "Mahkeme", "Esas No", "Karar No", "Sonuç Özeti", "Davacı", "Davalı"]]
        st.dataframe(ozet_tablo, use_container_width=True)
        
        # --- SEÇİLEN DOSYANIN DETAYI ---
        st.write("---")
        secilen_dosya = st.selectbox("Detayını görmek istediğiniz dosyayı seçin:", df["Dosya Adı"].tolist())
        
        if secilen_dosya:
            # Seçilen satırı bul
            detay = df[df["Dosya Adı"] == secilen_dosya].iloc[0]
            
            col_sol, col_sag = st.columns(2)
            
            with col_sol:
                st.info(f"**Mahkeme:** {detay['Mahkeme']}")
                st.write(f"**Hakim:** {detay['Hakim']}")
                st.write(f"**Dava:** {detay['Dava Türü']}")
                st.error(f"**SONUÇ:** {detay['Sonuç Özeti']}")
            
            with col_sag:
                st.text_input("Esas No", value=detay['Esas No'])
                st.text_input("Karar No", value=detay['Karar No'])
                st.text_input("Davacı", value=detay['Davacı'])
                st.text_input("Davalı", value=detay['Davalı'])
            
            # Uzun Hüküm Metni
            with st.expander("📝 Mahkemenin Verdiği Tam Karar Metni (Hüküm)"):
                st.warning(detay['Detaylı Hüküm'])

        # --- EXCEL İNDİR ---
        st.write("---")
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Tüm Listeyi Excel Olarak İndir", csv, "karar_listesi.csv", "text/csv")
        
    else:
        st.error("Dosyalardan metin okunamadı.")
