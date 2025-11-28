import streamlit as st
import PyPDF2
import re
import pandas as pd
import os
from collections import Counter

# --- 1. AYARLAR ---
st.set_page_config(page_title="Hukuk Asistanı Pro", layout="wide", page_icon="⚖️")
VERITABANI_DOSYASI = "dogrulanmis_veri.csv"

# --- 2. CSS TASARIMI ---
st.markdown("""
<style>
    .stSuccess { background-color: #d4edda; border-left: 5px solid #28a745; }
    .stError { background-color: #f8d7da; border-left: 5px solid #dc3545; }
    .stInfo { background-color: #cce5ff; border-left: 5px solid #004085; }
    div[data-testid="stForm"] { border: 2px solid #f0f2f6; padding: 20px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 3. FONKSİYONLAR ---

def veritabani_yukle():
    if os.path.exists(VERITABANI_DOSYASI):
        return pd.read_csv(VERITABANI_DOSYASI)
    # Yeni sütun ekledik: "Dava Türü"
    return pd.DataFrame(columns=["Dosya Adı", "Dava Türü", "Mahkeme", "Esas No", 
                                 "Karar No", "Davacı", "Davalı", "Sonuç", "Vekalet Ücreti"])

def veritabanina_kaydet(yeni_veri):
    df = veritabani_yukle()
    yeni_satir = pd.DataFrame([yeni_veri])
    df = pd.concat([df, yeni_satir], ignore_index=True)
    df.to_csv(VERITABANI_DOSYASI, index=False)

def metni_temizle(metin):
    duzeltmeler = {
        r"HAK M": "HAKİM", r"KAT P": "KATİP", r"VEK L": "VEKİL",
        r"T RAZ": "İTİRAZ", r"PTAL": "İPTAL", 
        r"K A B U L": "KABUL", r"R E D": "RED"
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
    metin_upper = metin.upper()
    hukum_blok = re.search(r"(HÜKÜM|GEREĞİ DÜŞÜNÜLDÜ)\s*[:;](.*)", metin_upper, re.DOTALL)
    alan = hukum_blok.group(2) if hukum_blok else metin_upper[-1000:]
    
    if "KISMEN KABUL" in alan: return "⚠️ KISMEN KABUL"
    if re.search(r"DAVANIN\s*KABUL", alan) or re.search(r"İTİRAZIN\s*İPTAL", alan): return "✅ KABUL (Davacı)"
    if re.search(r"DAVANIN\s*RED", alan) or re.search(r"BERAAT", alan): return "❌ RED (Davalı/Sanık)"
    return "❓ Belirsiz"

# --- 🔥 YENİ DEDEKTİF: DAVA TÜRÜ BELİRLEME ---
def dava_turu_bul(metin, mahkeme_adi):
    metin_lower = metin.lower()
    mahkeme_lower = mahkeme_adi.lower()
    
    # 1. Adım: Mahkeme Adı Bonusu (En Güçlü Kanıt)
    if "ceza" in mahkeme_lower or "ağır" in mahkeme_lower:
        return "🛑 CEZA HUKUKU"
    if "idare" in mahkeme_lower or "vergi" in mahkeme_lower or "danıştay" in mahkeme_lower:
        return "🏛️ İDARE HUKUKU"
    if "aile" in mahkeme_lower or "iş" in mahkeme_lower or "tüketici" in mahkeme_lower or "sulh hukuk" in mahkeme_lower:
        return "⚖️ ÖZEL HUKUK (Medeni)"

    # 2. Adım: Kelime Puanlama Sistemi
    puanlar = {"Ceza": 0, "İdare": 0, "Hukuk": 0}
    
    # Ceza Kelimeleri
    ceza_kelimeleri = ["sanık", "suç", "hapis", "beraat", "mahkumiyet", "hagb", "c.savcısı", "müşteki", "iddianame"]
    # İdare Kelimeleri
    idare_kelimeleri = ["yürütmenin durdurulması", "işlemin iptali", "tam yargı", "kurum işlemi", "valilik", "kaymakamlık"]
    # Hukuk Kelimeleri
    hukuk_kelimeleri = ["davacı", "davalı", "alacak", "boşanma", "tazminat", "tapu", "itirazın iptali", "tahliye", "kira"]

    for k in ceza_kelimeleri: puanlar["Ceza"] += metin_lower.count(k)
    for k in idare_kelimeleri: puanlar["İdare"] += metin_lower.count(k)
    for k in hukuk_kelimeleri: puanlar["Hukuk"] += metin_lower.count(k)

    # En yüksek puanı alanı seç
    en_yuksek = max(puanlar, key=puanlar.get)
    
    if puanlar[en_yuksek] == 0: return "❓ Tespit Edilemedi"
    
    mapping = {
        "Ceza": "🛑 CEZA HUKUKU",
        "İdare": "🏛️ İDARE HUKUKU",
        "Hukuk": "⚖️ ÖZEL HUKUK (Medeni)"
    }
    return mapping[en_yuksek]

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
    
    bilgi["Sonuç"] = sonuc_karar_ver(metin)
    bilgi["Vekalet Ücreti"] = para_bul(metin, "vekalet ücreti")
    
    # Yeni fonksiyonu çağır
    bilgi["Dava Türü"] = dava_turu_bul(metin, bilgi["Mahkeme"])
    
    return bilgi

# --- 4. ARAYÜZ ---

st.title("🧠 Öğrenen Hukuk Asistanı Pro")
st.markdown("Otomatik **Dava Türü Ayrımı (Ceza/Hukuk/İdare)** özelliği eklendi.")

with st.sidebar:
    st.header("💾 Arşiv")
    df_db = veritabani_yukle()
    st.metric("Kaydedilen Dosya", len(df_db))
    if not df_db.empty:
        # Hangi türden kaç dava var grafiği
        st.write("Dava Türü Dağılımı:")
        st.bar_chart(df_db["Dava Türü"].value_counts())
        st.download_button("İndir", df_db.to_csv(index=False).encode('utf-8'), "arsiv.csv")

uploaded_file = st.file_uploader("Karar Dosyası (PDF)", type="pdf")

if uploaded_file:
    if "analiz_sonucu" not in st.session_state or st.session_state.dosya_adi != uploaded_file.name:
        text = pdf_oku(uploaded_file)
        st.session_state.analiz_sonucu = analiz_yap(text, uploaded_file.name)
        st.session_state.dosya_adi = uploaded_file.name
    
    veri = st.session_state.analiz_sonucu

    # --- DÜZENLEME FORMU ---
    st.subheader("📝 Analiz Paneli")
    
    # DAVA TÜRÜ GÖSTERGESİ (Büyük Renkli Kutu)
    tur_renk = "blue"
    if "CEZA" in veri["Dava Türü"]: tur_renk = "red"
    elif "İDARE" in veri["Dava Türü"]: tur_renk = "orange"
    
    st.markdown(f"""
    <div style="background-color:{tur_renk}; padding:10px; border-radius:5px; color:white; text-align:center; font-weight:bold; margin-bottom:15px;">
        TESPİT EDİLEN TÜR: {veri["Dava Türü"]}
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("dogrulama_formu"):
        st.write("#### 1. Künye Bilgileri")
        # Dava Türünü Düzeltme İmkanı
        turu_duzelt = st.selectbox("Dava Türü", 
                                   ["⚖️ ÖZEL HUKUK (Medeni)", "🛑 CEZA HUKUKU", "🏛️ İDARE HUKUKU", "❓ Tespit Edilemedi"],
                                   index=["⚖️ ÖZEL HUKUK (Medeni)", "🛑 CEZA HUKUKU", "🏛️ İDARE HUKUKU", "❓ Tespit Edilemedi"].index(veri["Dava Türü"]) if veri["Dava Türü"] in ["⚖️ ÖZEL HUKUK (Medeni)", "🛑 CEZA HUKUKU", "🏛️ İDARE HUKUKU"] else 3)
        
        yeni_mahkeme = st.text_input("Mahkeme", value=veri["Mahkeme"])
        c1, c2 = st.columns(2)
        yeni_esas = c1.text_input("Esas No", value=veri["Esas No"])
        yeni_karar = c2.text_input("Karar No", value=veri["Karar No"])
        
        st.write("#### 2. İçerik ve Sonuç")
        c3, c4 = st.columns(2)
        yeni_davaci = c3.text_input("Davacı / Müşteki", value=veri["Davacı"])
        yeni_davali = c4.text_input("Davalı / Sanık", value=veri["Davalı"])
        
        c5, c6 = st.columns(2)
        secenekler = ["✅ KABUL (Davacı)", "❌ RED (Davalı/Sanık)", "⚠️ KISMEN KABUL", "❓ Belirsiz"]
        idx = 3
        if veri["Sonuç"] in secenekler: idx = secenekler.index(veri["Sonuç"])
        yeni_sonuc = c5.selectbox("Sonuç", secenekler, index=idx)
        yeni_vekalet = c6.text_input("Vekalet Ücreti", value=veri["Vekalet Ücreti"])
        
        st.write("---")
        if st.form_submit_button("✅ Onayla ve Arşivle"):
            kayit = {
                "Dosya Adı": veri["Dosya Adı"],
                "Dava Türü": turu_duzelt, # Düzeltilmiş türü kaydet
                "Mahkeme": yeni_mahkeme, "Esas No": yeni_esas, "Karar No": yeni_karar,
                "Davacı": yeni_davaci, "Davalı": yeni_davali, 
                "Sonuç": yeni_sonuc, "Vekalet Ücreti": yeni_vekalet
            }
            veritabanina_kaydet(kayit)
            st.success("Kayıt Başarılı!")
            st.rerun()
