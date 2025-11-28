import streamlit as st
import PyPDF2
import re
import pandas as pd
import os

# --- 1. AYARLAR ---
st.set_page_config(page_title="Hukuk Asistanı Master", layout="wide", page_icon="⚖️")
VERITABANI_DOSYASI = "dogrulanmis_veri.csv"

# --- 2. CSS TASARIMI ---
st.markdown("""
<style>
    .stSuccess { background-color: #d1e7dd; border-left: 5px solid #198754; }
    .stError { background-color: #f8d7da; border-left: 5px solid #dc3545; }
    .mali-kutu {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        margin-bottom: 10px;
        text-align: center;
    }
    .mali-etiket { font-size: 0.9rem; color: #6c757d; display: block; margin-bottom: 5px; font-weight: 600;}
    .mali-deger { font-size: 1.3rem; font-weight: bold; color: #212529; }
    .alacak-tipi { font-size: 0.75rem; padding: 3px 8px; border-radius: 4px; font-weight: bold;}
    .devlet { background-color: #ffecb3; color: #b45309; }
    .sahis { background-color: #d1e7dd; color: #0f5132; }
    div[data-testid="stForm"] { border: 2px solid #f8f9fa; padding: 20px; border-radius: 12px; }
</style>
""", unsafe_allow_html=True)

# --- 3. FONKSİYONLAR ---

def veritabani_yukle():
    if os.path.exists(VERITABANI_DOSYASI):
        return pd.read_csv(VERITABANI_DOSYASI)
    return pd.DataFrame(columns=["Dosya Adı", "Dava Türü", "Mahkeme", "Esas No", 
                                 "Sonuç", "Vekalet", "Bakiye Harç", "Arabuluculuk", "Yargılama Gideri"])

def veritabanina_kaydet(yeni_veri):
    df = veritabani_yukle()
    yeni_satir = pd.DataFrame([yeni_veri])
    df = pd.concat([df, yeni_satir], ignore_index=True)
    df.to_csv(VERITABANI_DOSYASI, index=False)

def metni_temizle(metin):
    """OCR hatalarını, soru işaretlerini ve bitişik kelimeleri temizler."""
    duzeltmeler = {
        r"HAK M": "HAKİM", r"KAT P": "KATİP", r"VEK L": "VEKİL",
        r"T RAZ": "İTİRAZ", r"PTAL": "İPTAL", r"TAHL YE": "TAHLİYE",
        r"K A B U L": "KABUL", r"R E D": "RED"
    }
    # Satırları birleştir
    temiz = metin.replace("\n", " ").strip()
    # Fazla boşlukları sil
    temiz = re.sub(r'\s+', ' ', temiz)
    
    # OCR'dan gelen sayı içindeki hatalı soru işaretlerini (Örn: 2.049,3?0) düzelt
    # Sadece rakamların arasındaki ? işaretini 0 yapar veya siler.
    temiz = re.sub(r'(?<=\d)\?(?=\d)', '0', temiz) # İki rakam arasındaysa 0 yap
    temiz = re.sub(r'(?<=\d)\?', '', temiz)        # Rakam sonundaysa sil
    
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
    """
    Belirli bir kelime grubunun (Örn: Arabuluculuk) yakınındaki parayı bulur.
    """
    for anahtar in anahtar_kelime_grubu:
        # Regex: Anahtar kelimeyi bul, etrafındaki 100 karakter içinde rakam+TL ara
        # Önce Rakam Sonra Kelime
        p1 = fr"([\d\.,]+\s*TL).{{0,100}}?{anahtar}"
        # Önce Kelime Sonra Rakam
        p2 = fr"{anahtar}.{{0,100}}?([\d\.,]+\s*TL)"
        
        m1 = re.search(p1, metin, re.IGNORECASE)
        m2 = re.search(p2, metin, re.IGNORECASE)
        
        if m1: return m1.group(1).strip()
        if m2: return m2.group(1).strip()
    return "0,00 TL"

def analiz_yap(metin, dosya_adi):
    metin = metni_temizle(metin)
    bilgi = {"Dosya Adı": dosya_adi}
    
    # --- 1. KİMLİK BİLGİLERİ ---
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
        
    # Dava Türü
    bilgi["Dava Türü"] = "⚖️ ÖZEL HUKUK"
    if "ceza" in bilgi["Mahkeme"].lower(): bilgi["Dava Türü"] = "🛑 CEZA HUKUKU"
    elif "idare" in bilgi["Mahkeme"].lower(): bilgi["Dava Türü"] = "🏛️ İDARE HUKUKU"

    # --- 2. HÜKÜM ALANI (Odaklanma) ---
    metin_upper = metin.upper()
    hukum_blok = re.search(r"(HÜKÜM|GEREĞİ DÜŞÜNÜLDÜ)\s*[:;](.*)", metin_upper, re.DOTALL)
    # Hüküm varsa onu al, yoksa son 2000 karakteri al
    alan = hukum_blok.group(2) if hukum_blok else metin_upper[-2000:]
    
    # Sonuç
    if "KISMEN KABUL" in alan: bilgi["Sonuç"] = "⚠️ KISMEN KABUL"
    elif re.search(r"DAVANIN\s*KABUL", alan) or re.search(r"İTİRAZIN\s*İPTAL", alan): bilgi["Sonuç"] = "✅ KABUL (Davacı Kazandı)"
    elif re.search(r"DAVANIN\s*RED", alan): bilgi["Sonuç"] = "❌ RED (Davalı Kazandı)"
    else: bilgi["Sonuç"] = "❓ Belirsiz"

    # --- 3. DETAYLI MALİ ANALİZ (Senin metnine özel) ---
    
    # A) Davacıya Ödenecekler (Alacak Kalemleri)
    bilgi["Vekalet"] = para_bul_regex(alan, ["vekalet ücreti", "ücreti vekalet"])
    bilgi["Yargılama Gideri"] = para_bul_regex(alan, ["davacı tarafından karşılanan", "toplam yargılama gideri", "yapılan masraf"])
    
    # B) Devlete Ödenecekler (Hazine Kalemleri)
    bilgi["Arabuluculuk"] = para_bul_regex(alan, ["arabuluculuk gideri", "arabuluculuk ücreti"])
    bilgi["Bakiye Harç"] = para_bul_regex(alan, ["eksik kalan", "bakiye karar", "alınarak hazineye"])

    # C) İade
    bilgi["İade"] = "Var" if "gider avansının" in alan.lower() and "iadesine" in alan.lower() else "Yok"

    return bilgi

# --- 4. ARAYÜZ ---

st.title("⚖️ Hukuk Asistanı: Master Mali Analiz")
st.markdown("Mahkeme kararını yükleyin, **Kimin cebine girecek? Kimin cebinden çıkacak?** anında görün.")

with st.sidebar:
    st.header("Arşiv")
    df = veritabani_yukle()
    st.metric("Kayıtlı Dosya", len(df))
    if not df.empty: 
        st.dataframe(df[["Esas No", "Sonuç"]].tail(5), hide_index=True)
        st.download_button("Excel Olarak İndir", df.to_csv(index=False).encode('utf-8'), "mali_rapor.csv")

dosya = st.file_uploader("Dosya Yükle (PDF)", type="pdf")

if dosya:
    if "analiz_sonucu" not in st.session_state or st.session_state.dosya_adi != dosya.name:
        text = pdf_oku(dosya)
        st.session_state.analiz_sonucu = analiz_yap(text, dosya.name)
        st.session_state.dosya_adi = dosya.name
    
    veri = st.session_state.analiz_sonucu
    
    # SONUÇ BAŞLIĞI
    renk = "green" if "KABUL" in veri["Sonuç"] else "red"
    st.markdown(f'<div style="background-color:{renk}; color:white; padding:15px; border-radius:8px; text-align:center; font-size:1.2rem; font-weight:bold;">{veri["Sonuç"]}</div>', unsafe_allow_html=True)
    st.write("")

    # --- MALİ TABLO (ÖZEL TASARIM) ---
    st.subheader("💰 Tahsilat ve Ödeme Tablosu")
    
    col1, col2 = st.columns(2)
    
    # 1. DAVACIYA ÖDENECEKLER (Yeşil Kutu)
    with col1:
        st.markdown("""
        <div style="background-color:#f0fff4; padding:10px; border-radius:5px; border-left:5px solid #198754; margin-bottom:10px;">
            <h4 style="color:#198754; margin:0;">🟢 Davacıya Ödenecekler</h4>
            <small>(Davalı -> Davacıya)</small>
        </div>
        """, unsafe_allow_html=True)
        
        c1a, c1b = st.columns(2)
        with c1a:
            st.markdown(f'<div class="mali-kutu"><span class="mali-etiket">Vekalet Ücreti</span><span class="mali-deger" style="color:#198754">{veri["Vekalet"]}</span></div>', unsafe_allow_html=True)
        with c1b:
            st.markdown(f'<div class="mali-kutu"><span class="mali-etiket">Yargılama Gideri</span><span class="mali-deger" style="color:#198754">{veri["Yargılama Gideri"]}</span></div>', unsafe_allow_html=True)
            
        if veri["İade"] == "Var":
            st.info("ℹ️ Artan gider avansı Davacıya iade edilecektir.")

    # 2. DEVLETE ÖDENECEKLER (Sarı Kutu)
    with col2:
        st.markdown("""
        <div style="background-color:#fff9db; padding:10px; border-radius:5px; border-left:5px solid #f59f00; margin-bottom:10px;">
            <h4 style="color:#f59f00; margin:0;">🏛️ Devlete (Hazineye) Ödenecekler</h4>
            <small>(Davalı -> Maliyeye)</small>
        </div>
        """, unsafe_allow_html=True)
        
        c2a, c2b = st.columns(2)
        with c2a:
            st.markdown(f'<div class="mali-kutu"><span class="mali-etiket">Arabuluculuk</span><span class="mali-deger" style="color:#d63384">{veri["Arabuluculuk"]}</span></div>', unsafe_allow_html=True)
        with c2b:
            st.markdown(f'<div class="mali-kutu"><span class="mali-etiket">Eksik Harç</span><span class="mali-deger" style="color:#fd7e14">{veri["Bakiye Harç"]}</span></div>', unsafe_allow_html=True)

    # KAYIT FORMU
    with st.expander("📝 Kayıt ve Düzeltme Formu", expanded=True):
        with st.form("kayit"):
            c_main1, c_main2 = st.columns(2)
            c_main1.text_input("Esas No", veri["Esas No"])
            c_main2.text_input("Davalı Adı", veri["Davalı"])
            
            st.write("---")
            st.write("**Mali Kontrol**")
            m1, m2, m3, m4 = st.columns(4)
            yeni_vekalet = m1.text_input("Vekalet", veri["Vekalet"])
            yeni_gider = m2.text_input("Yarg. Gideri", veri["Yargılama Gideri"])
            yeni_arabulucu = m3.text_input("Arabuluculuk", veri["Arabuluculuk"])
            yeni_harc = m4.text_input("Eksik Harç", veri["Bakiye Harç"])
            
            if st.form_submit_button("✅ Onayla ve Veritabanına Ekle"):
                kayit = {
                    "Dosya Adı": veri["Dosya Adı"], "Dava Türü": veri["Dava Türü"],
                    "Mahkeme": veri["Mahkeme"], "Esas No": veri["Esas No"],
                    "Sonuç": veri["Sonuç"], 
                    "Vekalet": yeni_vekalet, "Yargılama Gideri": yeni_gider,
                    "Arabuluculuk": yeni_arabulucu, "Bakiye Harç": yeni_harc
                }
                veritabanina_kaydet(kayit)
                st.success("Mali tablo başarıyla arşivlendi.")
