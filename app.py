import streamlit as st
import PyPDF2
import re
import pandas as pd

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Hukuk Asistanı Pro", layout="wide", page_icon="⚖️")

# --- OCR DÜZELTME MOTORU ---
def metni_temizle_ve_duzelt(metin):
    """Bozuk karakterleri ve OCR hatalarını düzeltir."""
    duzeltmeler = {
        r"HAK M": "HAKİM", r"KAT P": "KATİP", r"VEK L": "VEKİL",
        r"T RAZ": "İTİRAZ", r"PTAL": "İPTAL", r"TAHL YE": "TAHLİYE",
        r"DAVACI": "DAVACI", r"DAVALI": "DAVALI", r"HÜKÜM": "HÜKÜM",
        r"GEREKÇEL KARAR": "GEREKÇELİ KARAR",
        r"YÜKLET LMES NE": "YÜKLETİLMESİNE",
        r"ALINARAK": "ALINARAK", r"VER LMES NE": "VERİLMESİNE"
    }
    temiz_metin = metin.replace("\n", " ").strip()
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

# --- AKILLI SONUÇ VE MALİ ANALİZ ---
def sonuc_ve_mali_analiz(metin):
    """Kim kazandı, parayı kim ödüyor analizi yapar."""
    analiz = {
        "Kazanan": "Belirsiz",
        "Kaybeden": "Belirsiz",
        "Vekalet Ücreti": "Belirtilmemiş",
        "Yargılama Gideri": "Belirtilmemiş",
        "Durum": "Analiz Ediliyor..."
    }
    
    metin_upper = metin.upper()
    
    # 1. KAZANAN / KAYBEDEN TESPİTİ
    if "DAVANIN KABULÜNE" in metin_upper:
        analiz["Kazanan"] = "DAVACI (Alacaklı)"
        analiz["Kaybeden"] = "DAVALI (Borçlu)"
        analiz["Durum"] = "✅ KABUL (Davacı Kazandı)"
        
        # Kabul halinde masrafları Davalı öder
        analiz["Vekalet Ücreti"] = "Davalı öder ➡️ Davacı Avukatına"
        analiz["Yargılama Gideri"] = "Davalı öder (Davacıya geri verir)"
        
    elif "DAVANIN REDDİNE" in metin_upper:
        analiz["Kazanan"] = "DAVALI (Borçlu)"
        analiz["Kaybeden"] = "DAVACI (Alacaklı)"
        analiz["Durum"] = "❌ RED (Davacı Kaybetti)"
        
        # Red halinde masrafları Davacı öder
        analiz["Vekalet Ücreti"] = "Davacı öder ➡️ Davalı Avukatına"
        analiz["Yargılama Gideri"] = "Davacı üzerinde kalır"
        
    elif "KISMEN KABUL" in metin_upper:
        analiz["Durum"] = "⚠️ KISMEN KABUL / KISMEN RED"
        analiz["Kazanan"] = "Ortak (Oranına göre)"
        analiz["Kaybeden"] = "Ortak"
        analiz["Vekalet Ücreti"] = "Taraflar oranına göre birbirine öder"
        analiz["Yargılama Gideri"] = "Haklılık oranına göre paylaştırılır"

    return analiz

# --- GENEL ANALİZ MOTORU ---
def detayli_analiz(ham_metin, dosya_adi):
    metin = metni_temizle_ve_duzelt(ham_metin)
    
    bilgiler = {"Dosya Adı": dosya_adi}
    
    # Regex Tanımları
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

    # Hüküm Metnini Çek
    hukum_bul = re.search(r"HÜKÜM\s*[:;].*?(\d-.*?)(?=UYAP|GEREKÇELİ KARAR|$)", metin, re.IGNORECASE)
    bilgiler["Hüküm Metni"] = hukum_bul.group(1).strip() if hukum_bul else "Tam ayrıştırılamadı."

    # Mali Analizi Ekle
    mali_durum = sonuc_ve_mali_analiz(metin)
    bilgiler.update(mali_durum) # Sözlükleri birleştir

    return bilgiler

# --- ARAYÜZ ---
st.title("⚖️ Hukuk Asistanı: Karar Analiz Modülü")
st.markdown("Mahkeme kararını yükleyin; kim kazandı, kim kime ne ödeyecek anında görün.")

uploaded_files = st.file_uploader("Karar Dosyalarını Yükleyin (PDF)", type="pdf", accept_multiple_files=True)

if uploaded_files:
    tum_veriler = []
    
    for dosya in uploaded_files:
        raw_text = pdf_metin_oku(dosya)
        if len(raw_text) > 50:
            veri = detayli_analiz(raw_text, dosya.name)
            tum_veriler.append(veri)
            
    if tum_veriler:
        df = pd.DataFrame(tum_veriler)
        
        # --- DOSYA SEÇİMİ ---
        st.write("---")
        secilen = st.selectbox("İncelemek istediğiniz dosyayı seçin:", df["Dosya Adı"].tolist())
        
        if secilen:
            # Seçilen dosyanın verilerini çek
            row = df[df["Dosya Adı"] == secilen].iloc[0]
            
            # --- 1. KAZANAN / KAYBEDEN KARTLARI ---
            st.subheader("🏆 Karar Sonucu")
            c1, c2, c3 = st.columns(3)
            
            if "KABUL" in row["Durum"]:
                c1.success(f"**SONUÇ:**\n{row['Durum']}")
                c2.success(f"**KAZANAN:**\n{row['Kazanan']}")
                c3.error(f"**KAYBEDEN:**\n{row['Kaybeden']}")
            elif "RED" in row["Durum"]:
                c1.error(f"**SONUÇ:**\n{row['Durum']}")
                c2.error(f"**KAZANAN:**\n{row['Kazanan']}")
                c3.success(f"**KAYBEDEN:**\n{row['Kaybeden']}")
            else:
                c1.warning(row["Durum"])

            # --- 2. MALİ YÜKÜMLÜLÜKLER (YENİ EKLENEN KISIM) ---
            st.write("---")
            st.subheader("💰 Mali Yükümlülükler (Kim Öder?)")
            
            col_mali1, col_mali2 = st.columns(2)
            with col_mali1:
                st.info("⚖️ **Avukatlık (Vekalet) Ücreti**")
                st.write(f"👉 {row['Vekalet Ücreti']}")
                
            with col_mali2:
                st.info("📂 **Yargılama Giderleri**")
                st.write(f"👉 {row['Yargılama Gideri']}")
                
            # --- 3. TEMEL BİLGİLER ---
            st.write("---")
            st.text_input("Mahkeme", row["Mahkeme"])
            col_d1, col_d2 = st.columns(2)
            col_d1.text_input("Davacı", row["Davacı"])
            col_d2.text_input("Davalı", row["Davalı"])
            
            # --- 4. DETAYLI HÜKÜM ---
            with st.expander("📜 Mahkemenin Yazdığı Orijinal Karar (Hüküm)"):
                st.write(row["Hüküm Metni"])
                
        # --- LİSTEYİ İNDİR ---
        st.write("---")
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Tüm Analizi İndir (Excel/CSV)", csv, "analiz_sonucu.csv", "text/csv")
