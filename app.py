import streamlit as st
import PyPDF2
import re
import pandas as pd
import os

# --- 1. AYARLAR ---
st.set_page_config(page_title="Hukuk Asistanı - Tam Künye", layout="wide", page_icon="⚖️")
VERITABANI_DOSYASI = "dava_takip_sistemi.csv"

# --- 2. CSS TASARIMI ---
st.markdown("""
<style>
    .stSuccess { background-color: #d1e7dd; border-left: 5px solid #198754; }
    .kunye-kutu {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #dee2e6;
        margin-bottom: 10px;
    }
    .kunye-etiket { font-weight: bold; color: #495057; }
    .kunye-deger { color: #000; font-weight: 500; margin-left: 5px; }
    div[data-testid="stForm"] { border: 2px solid #2c3e50; padding: 20px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 3. FONKSİYONLAR ---

def veritabani_yukle():
    if os.path.exists(VERITABANI_DOSYASI):
        return pd.read_csv(VERITABANI_DOSYASI)
    # İSTEDİĞİN TÜM SÜTUNLAR BURADA
    cols = ["Dosya Adı", "Mahkeme", "Esas No", "Karar No", 
            "Davacı", "Davacı Vekili", "Davalı", "Dava Konusu", 
            "Dava Tarihi", "Karar Tarihi", "Yazım Tarihi", 
            "Sonuç", "Vekalet Ücreti", "Yargılama Gideri", "Harç"]
    return pd.DataFrame(columns=cols)

def veritabanina_kaydet(yeni_veri):
    df = veritabani_yukle()
    yeni_satir = pd.DataFrame([yeni_veri])
    df = pd.concat([df, yeni_satir], ignore_index=True)
    df.to_csv(VERITABANI_DOSYASI, index=False)

def metni_temizle(metin):
    duzeltmeler = {
        r"HAK M": "HAKİM", r"KAT P": "KATİP", r"VEK L": "VEKİL",
        r"T RAZ": "İTİRAZ", r"PTAL": "İPTAL", r"TAHL YE": "TAHLİYE",
        r"GEREKÇEL KARAR": "GEREKÇELİ KARAR",
        r"YAZILDI I": "YAZILDIĞI"
    }
    temiz = metin.replace("\n", " ").strip()
    temiz = re.sub(r'\s+', ' ', temiz)
    # OCR Soru işareti düzeltme
    temiz = re.sub(r'(?<=\d)\?(?=\d)', '0', temiz) 
    
    for bozuk, duzgun in duzeltmeler.items():
        temiz = re.sub(bozuk, duzgun, temiz, flags=re.IGNORECASE)
    return temiz

def pdf_oku(dosya):
    okuyucu = PyPDF2.PdfReader(dosya)
    metin = ""
    for sayfa in okuyucu.pages:
        metin += sayfa.extract_text() or ""
    return metin

def para_bul_regex(metin, anahtar_kelime_grubu):
    for anahtar in anahtar_kelime_grubu:
        p1 = fr"([\d\.,]+\s*TL).{{0,100}}?{anahtar}"
        p2 = fr"{anahtar}.{{0,100}}?([\d\.,]+\s*TL)"
        m1 = re.search(p1, metin, re.IGNORECASE)
        m2 = re.search(p2, metin, re.IGNORECASE)
        if m1: return m1.group(1).strip()
        if m2: return m2.group(1).strip()
    return "0,00 TL"

def analiz_yap(metin, dosya_adi):
    metin = metni_temizle(metin)
    bilgi = {"Dosya Adı": dosya_adi}
    
    # --- 1. DOSYA KÜNYESİ (İstediğin Tüm Alanlar) ---
    regexler = {
        "Mahkeme": r"(T\.?C\.?.*?MAHKEMES.*?)Esas",
        "Esas No": r"ESAS\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Karar No": r"KARAR\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Davacı": r"DAVACI\s*[:;]?\s*(.*?)(?=VEKİL|DAVALI)",
        "Davacı Vekili": r"(?:DAVACI\s*)?VEKİL[İI]\s*[:;]?\s*(.*?)(?=DAVALI|DAVA)",
        "Davalı": r"DAVALI\s*[:;]?\s*(.*?)(?=VEKİL|DAVA|KONU)",
        "Dava Konusu": r"DAVA\s*[:;]?\s*(.*?)(?=DAVA TARİHİ|KARAR TARİHİ)",
        "Dava Tarihi": r"DAVA\s*TARİH[İI]\s*[:;]?\s*(\d{2}[./]\d{2}[./]\d{4})",
        "Karar Tarihi": r"KARAR\s*TARİH[İI]\s*[:;]?\s*(\d{2}[./]\d{2}[./]\d{4})",
        "Yazım Tarihi": r"YAZILDIĞI\s*TARİH\s*[:;]?\s*(\d{2}[./]\d{2}[./]\d{4})"
    }
    
    for baslik, kalip in regexler.items():
        m = re.search(kalip, metin, re.IGNORECASE)
        if m:
            # Grup 1'i al, gereksiz karakterleri temizle
            bilgi[baslik] = m.group(1).strip().replace(":", "")
        else:
            bilgi[baslik] = "-"

    # --- 2. HÜKÜM VE MALİ ANALİZ ---
    metin_upper = metin.upper()
    hukum_blok = re.search(r"(HÜKÜM|GEREĞİ DÜŞÜNÜLDÜ)\s*[:;](.*)", metin_upper, re.DOTALL)
    alan = hukum_blok.group(2) if hukum_blok else metin_upper[-2000:]
    
    if "KISMEN KABUL" in alan: bilgi["Sonuç"] = "⚠️ KISMEN KABUL"
    elif re.search(r"DAVANIN\s*KABUL", alan) or re.search(r"İTİRAZIN\s*İPTAL", alan): bilgi["Sonuç"] = "✅ KABUL"
    elif re.search(r"DAVANIN\s*RED", alan): bilgi["Sonuç"] = "❌ RED"
    else: bilgi["Sonuç"] = "❓ Belirsiz"

    # Mali Kalemler
    bilgi["Vekalet Ücreti"] = para_bul_regex(alan, ["vekalet ücreti", "ücreti vekalet"])
    bilgi["Yargılama Gideri"] = para_bul_regex(alan, ["toplam yargılama gideri", "yapılan masraf"])
    bilgi["Harç"] = para_bul_regex(alan, ["bakiye", "karar harcı", "eksik kalan"])

    return bilgi

# --- 4. ARAYÜZ ---

st.title("⚖️ Hukuk Asistanı: Tam Künye & Analiz")

with st.sidebar:
    st.header("🗄️ Dava Arşivi")
    df = veritabani_yukle()
    st.metric("Kayıtlı Dosya", len(df))
    if not df.empty:
        st.dataframe(df[["Esas No", "Davacı", "Sonuç"]].tail(10), hide_index=True)
        st.download_button("Tüm Listeyi İndir (Excel)", df.to_csv(index=False).encode('utf-8'), "dava_listesi.csv")

dosya = st.file_uploader("Dosya Yükle (PDF)", type="pdf")

if dosya:
    if "analiz_sonucu" not in st.session_state or st.session_state.dosya_adi != dosya.name:
        text = pdf_oku(dosya)
        st.session_state.analiz_sonucu = analiz_yap(text, dosya.name)
        st.session_state.dosya_adi = dosya.name
    
    veri = st.session_state.analiz_sonucu

    # --- 1. KÜNYE BÖLÜMÜ (GÖZÜNÜN ÖNÜNDE) ---
    st.subheader("📋 Dosya Künyesi")
    
    # 3 Kolonlu Düzen
    k1, k2, k3 = st.columns(3)
    
    with k1:
        st.markdown(f"**Mahkeme:** {veri['Mahkeme']}")
        st.markdown(f"**Esas No:** `{veri['Esas No']}`")
        st.markdown(f"**Karar No:** `{veri['Karar No']}`")
        
    with k2:
        st.markdown(f"**Davacı:** {veri['Davacı']}")
        st.markdown(f"**Vekili:** {veri['Davacı Vekili']}")
        st.markdown(f"**Davalı:** {veri['Davalı']}")
        
    with k3:
        st.markdown(f"**Dava:** {veri['Dava Konusu']}")
        st.markdown(f"**Dava Tarihi:** {veri['Dava Tarihi']}")
        st.markdown(f"**Karar Tarihi:** {veri['Karar Tarihi']}")
        st.markdown(f"**Yazım Tarihi:** {veri['Yazım Tarihi']}")

    st.divider()

    # --- 2. MALİ VE SONUÇ BÖLÜMÜ ---
    c_sonuc, c_mali = st.columns([1, 2])
    
    with c_sonuc:
        st.info(f"**KARAR SONUCU:**\n\n# {veri['Sonuç']}")
        
    with c_mali:
        m1, m2, m3 = st.columns(3)
        m1.metric("Vekalet Ücreti", veri["Vekalet Ücreti"])
        m2.metric("Yargılama Gideri", veri["Yargılama Gideri"])
        m3.metric("Bakiye Harç", veri["Harç"])

    # --- 3. DÜZENLEME VE KAYIT FORMU (HİÇBİR VERİ KAÇMAZ) ---
    with st.expander("📝 Detaylı Kayıt Formu (Hataları Buradan Düzelt)", expanded=True):
        with st.form("tam_kayit"):
            st.write("###### 1. Temel Bilgiler")
            col_a, col_b, col_c = st.columns(3)
            y_esas = col_a.text_input("Esas No", veri["Esas No"])
            y_karar = col_b.text_input("Karar No", veri["Karar No"])
            y_mahkeme = col_c.text_input("Mahkeme", veri["Mahkeme"])
            
            st.write("###### 2. Taraflar")
            col_d, col_e, col_f = st.columns(3)
            y_davaci = col_d.text_input("Davacı", veri["Davacı"])
            y_vekil = col_e.text_input("Davacı Vekili", veri["Davacı Vekili"])
            y_davali = col_f.text_input("Davalı", veri["Davalı"])
            
            st.write("###### 3. Tarihler ve Konu")
            col_g, col_h, col_i, col_j = st.columns(4)
            y_konu = col_g.text_input("Dava Konusu", veri["Dava Konusu"])
            y_dava_t = col_h.text_input("Dava Tarihi", veri["Dava Tarihi"])
            y_karar_t = col_i.text_input("Karar Tarihi", veri["Karar Tarihi"])
            y_yazim_t = col_j.text_input("Yazım Tarihi", veri["Yazım Tarihi"])
            
            st.write("###### 4. Mali Veriler")
            col_k, col_l, col_m = st.columns(3)
            y_vekalet = col_k.text_input("Vekalet Ücreti", veri["Vekalet Ücreti"])
            y_gider = col_l.text_input("Yargılama Gideri", veri["Yargılama Gideri"])
            y_harc = col_m.text_input("Harç", veri["Harç"])
            
            # SONUÇ SEÇİMİ
            y_sonuc = st.selectbox("Sonuç", ["✅ KABUL", "❌ RED", "⚠️ KISMEN KABUL", "❓ Belirsiz"], 
                                   index=["✅ KABUL", "❌ RED", "⚠️ KISMEN KABUL", "❓ Belirsiz"].index(veri["Sonuç"]) if veri["Sonuç"] in ["✅ KABUL", "❌ RED", "⚠️ KISMEN KABUL"] else 3)
            
            st.write("---")
            if st.form_submit_button("💾 TÜM BİLGİLERİ KAYDET"):
                kayit = {
                    "Dosya Adı": veri["Dosya Adı"], "Mahkeme": y_mahkeme,
                    "Esas No": y_esas, "Karar No": y_karar,
                    "Davacı": y_davaci, "Davacı Vekili": y_vekil, "Davalı": y_davali,
                    "Dava Konusu": y_konu, 
                    "Dava Tarihi": y_dava_t, "Karar Tarihi": y_karar_t, "Yazım Tarihi": y_yazim_t,
                    "Sonuç": y_sonuc, 
                    "Vekalet Ücreti": y_vekalet, "Yargılama Gideri": y_gider, "Harç": y_harc
                }
                veritabanina_kaydet(kayit)
                st.success(f"{y_esas} sayılı dosya eksiksiz arşivlendi!")
                st.rerun() # Tabloyu güncellemek için sayfayı yenile
