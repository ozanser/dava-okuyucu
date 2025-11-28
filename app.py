import streamlit as st
import PyPDF2
import re
import pandas as pd

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Hukuk Asistanı Pro", layout="wide", page_icon="⚖️")

# --- OCR DÜZELTME MOTORU ---
def metni_temizle_ve_duzelt(metin):
    """
    Bozuk karakterleri ve OCR hatalarını düzeltir.
    Türkçe karakter sorunlarını ve yapışık kelimeleri çözer.
    """
    duzeltmeler = {
        r"HAK M": "HAKİM", r"KAT P": "KATİP", r"VEK L": "VEKİL",
        r"T RAZ": "İTİRAZ", r"PTAL": "İPTAL", r"TAHL YE": "TAHLİYE",
        r"DAVACI": "DAVACI", r"DAVALI": "DAVALI", r"HÜKÜM": "HÜKÜM",
        r"GEREKÇEL KARAR": "GEREKÇELİ KARAR",
        r"YÜKLET LMES NE": "YÜKLETİLMESİNE",
        r"DAVANIN KABULÜNE": "DAVANIN KABULÜNE", # Bazen bitişik çıkabilir
        r"DAVANIN REDD NE": "DAVANIN REDDİNE"
    }
    
    # 1. Satır sonlarını boşlukla değiştir
    temiz_metin = metin.replace("\n", " ").strip()
    
    # 2. Çoklu boşlukları teke indir (Önemli!)
    temiz_metin = re.sub(r'\s+', ' ', temiz_metin)
    
    # 3. Kelime düzeltmelerini yap
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
    """
    Kim kazandı, parayı kim ödüyor analizi yapar.
    Regex kullanarak esnek arama yapar (Boşluklara takılmaz).
    """
    analiz = {
        "Kazanan": "Belirsiz",
        "Kaybeden": "Belirsiz",
        "Vekalet Ücreti": "-",
        "Yargılama Gideri": "-",
        "Durum": "⚠️ Sonuç Net Ayrıştırılamadı"
    }
    
    # Regex ile esnek arama (Büyük/Küçük harf duyarsız, boşluk duyarsız)
    # \s* ifadesi "arada boşluk olsa da olmasa da" demektir.
    
    kabul_kalibi = r"DAVANIN\s*KABUL"      # DAVANIN KABULÜNE, DAVANIN KABULUNE vb. yakalar
    red_kalibi = r"DAVANIN\s*RED"          # DAVANIN REDDİNE, DAVANIN REDDINE vb. yakalar
    kismen_kalibi = r"KISMEN\s*KABUL"
    
    # --- MANTIK ZİNCİRİ ---
    
    if re.search(kismen_kalibi, metin, re.IGNORECASE):
        analiz["Durum"] = "⚠️ KISMEN KABUL / KISMEN RED"
        analiz["Kazanan"] = "Ortak (Oranına göre)"
        analiz["Kaybeden"] = "Ortak"
        analiz["Vekalet Ücreti"] = "Taraflar haklılık oranına göre öder"
        analiz["Yargılama Gideri"] = "Paylaştırılır"
        
    elif re.search(kabul_kalibi, metin, re.IGNORECASE):
        analiz["Kazanan"] = "DAVACI (Alacaklı)"
        analiz["Kaybeden"] = "DAVALI (Borçlu)"
        analiz["Durum"] = "✅ KABUL (Davacı Kazandı)"
        
        # Kabul halinde masrafları Davalı öder
        analiz["Vekalet Ücreti"] = "Davalı öder ➡️ Davacı Avukatına"
        analiz["Yargılama Gideri"] = "Davalı öder (Davacıya geri verir)"
        
    elif re.search(red_kalibi, metin, re.IGNORECASE):
        analiz["Kazanan"] = "DAVALI (Borçlu)"
        analiz["Kaybeden"] = "DAVACI (Alacaklı)"
        analiz["Durum"] = "❌ RED (Davacı Kaybetti)"
        
        # Red halinde masrafları Davacı öder
        analiz["Vekalet Ücreti"] = "Davacı öder ➡️ Davalı Avukatına"
        analiz["Yargılama Gideri"] = "Davacı üzerinde kalır"

    return analiz

# --- GENEL ANALİZ MOTORU ---
def detayli_analiz(ham_metin, dosya_adi):
    # 1. Temizlik
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
    # HÜKÜM kelimesinden sonra gelen ve maddeli kısmı almaya çalışır
    hukum_bul = re.search(r"(HÜKÜM|GEREĞİ DÜŞÜNÜLDÜ)\s*[:;](.*?)(?=UYAP|GEREKÇELİ KARAR|$)", metin, re.IGNORECASE | re.DOTALL)
    if hukum_bul:
        # Hüküm çok uzunsa ilk 1000 karakterini al, yoksa sayfayı kaplar
        bilgiler["Hüküm Metni"] = hukum_bul.group(2).strip()[:1500] 
    else:
        bilgiler["Hüküm Metni"] = "Hüküm bloğu net ayrıştırılamadı."

    # Mali Analizi Ekle (Yeni Fonksiyonu Çağırıyoruz)
    mali_durum = sonuc_ve_mali_analiz(metin)
    bilgiler.update(mali_durum) 

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
            row = df[df["Dosya Adı"] == secilen].iloc[0]
            
            # --- 1. KAZANAN / KAYBEDEN KARTLARI ---
            st.subheader("🏆 Karar Sonucu")
            c1, c2, c3 = st.columns(3)
            
            # Renklendirme Mantığı
            if "KABUL" in row["Durum"]:
                c1.success(f"**SONUÇ:**\n\n{row['Durum']}")
                c2.success(f"**KAZANAN:**\n\n{row['Kazanan']}")
                c3.error(f"**KAYBEDEN:**\n\n{row['Kaybeden']}")
            elif "RED" in row["Durum"]:
                c1.error(f"**SONUÇ:**\n\n{row['Durum']}")
                c2.error(f"**KAZANAN:**\n\n{row['Kazanan']}")
                c3.success(f"**KAYBEDEN:**\n\n{row['Kaybeden']}")
            else:
                c1.warning(f"**SONUÇ:**\n\n{row['Durum']}")
                c2.info("Belirsiz")
                c3.info("Belirsiz")

            # --- 2. MALİ YÜKÜMLÜLÜKLER ---
            st.write("---")
            st.subheader("💰 Mali Yükümlülükler (Kim Öder?)")
            
            col_mali1, col_mali2 = st.columns(2)
            with col_mali1:
                st.info("⚖️ **Avukatlık (Vekalet) Ücreti**")
                st.markdown(f"#### {row['Vekalet Ücreti']}")
                
            with col_mali2:
                st.info("📂 **Yargılama Giderleri**")
                st.markdown(f"#### {row['Yargılama Gideri']}")
                
            # --- 3. TEMEL BİLGİLER ---
            st.write("---")
            col_d1, col_d2 = st.columns(2)
            col_d1.text_input("Davacı", row["Davacı"])
            col_d2.text_input("Davalı", row["Davalı"])
            st.text_input("Mahkeme", row["Mahkeme"])
            
            # --- 4. DETAYLI HÜKÜM ---
            with st.expander("📜 Mahkemenin Yazdığı Orijinal Karar (Hüküm)"):
                st.write(row["Hüküm Metni"])
                
        # --- LİSTEYİ İNDİR ---
        st.write("---")
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Tüm Analizi İndir (Excel/CSV)", csv, "analiz_sonucu.csv", "text/csv")

    else:
        st.error("Dosyalardan metin okunamadı veya metin çok kısa.")
