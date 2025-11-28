import streamlit as st
import PyPDF2
import re
import pandas as pd
import os

# --- 1. AYARLAR ---
st.set_page_config(page_title="Hukuk Asistanı Pro", layout="wide", page_icon="⚖️")
VERITABANI_DOSYASI = "dogrulanmis_veri.csv"

# --- 2. CSS TASARIMI ---
st.markdown("""
<style>
    .stSuccess { background-color: #d4edda; border-left: 5px solid #28a745; }
    .stError { background-color: #f8d7da; border-left: 5px solid #dc3545; }
    .stInfo { background-color: #e2e3e5; border-left: 5px solid #383d41; }
    .mali-kart {
        background-color: #fff;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        text-align: center;
    }
    .mali-baslik { font-weight: bold; color: #6c757d; display: block; margin-bottom: 5px; font-size: 0.9rem;}
    .mali-tutar { font-size: 1.5rem; font-weight: bold; color: #2c3e50; }
    div[data-testid="stForm"] { border: 2px solid #f0f2f6; padding: 20px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 3. FONKSİYONLAR ---

def veritabani_yukle():
    if os.path.exists(VERITABANI_DOSYASI):
        return pd.read_csv(VERITABANI_DOSYASI)
    return pd.DataFrame(columns=["Dosya Adı", "Dava Türü", "Mahkeme", "Esas No", 
                                 "Davacı", "Davalı", "Sonuç", "Vekalet", "Harç", "Tazminat", "İtiraz Süresi"])

def veritabanina_kaydet(yeni_veri):
    df = veritabani_yukle()
    yeni_satir = pd.DataFrame([yeni_veri])
    df = pd.concat([df, yeni_satir], ignore_index=True)
    df.to_csv(VERITABANI_DOSYASI, index=False)

def metni_temizle(metin):
    duzeltmeler = {
        r"HAK M": "HAKİM", r"KAT P": "KATİP", r"VEK L": "VEKİL",
        r"T RAZ": "İTİRAZ", r"PTAL": "İPTAL", r"TAZM NAT": "TAZMİNAT",
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

def para_bul_hassas(metin, anahtar_kelimeler):
    """
    Daha akıllı para bulucu. Aranan kelimenin ÇOK YAKININDAKİ rakamı alır.
    Böylece uzaktaki vekalet ücretini harç sanmaz.
    """
    for kelime in anahtar_kelimeler:
        # Regex Açıklaması:
        # 1. ([\d\.,]+\s*TL) -> Rakam ve TL'yi bul
        # 2. .{0,50}? -> En fazla 50 karakter ilerle (Çok uzağa gitme!)
        # 3. {kelime} -> Anahtar kelimeyi bul (Örn: yargılama gideri)
        
        # Seçenek A: Rakam Önce, Kelime Sonra (Örn: "1.200 TL yargılama gideri")
        regex_once = fr"([\d\.,]+\s*TL).{{0,50}}?{kelime}"
        
        # Seçenek B: Kelime Önce, Rakam Sonra (Örn: "Yargılama gideri olan 1.200 TL")
        regex_sonra = fr"{kelime}.{{0,50}}?([\d\.,]+\s*TL)"
        
        m_once = re.search(regex_once, metin, re.IGNORECASE)
        m_sonra = re.search(regex_sonra, metin, re.IGNORECASE)
        
        if m_once: return m_once.group(1).strip()
        if m_sonra: return m_sonra.group(1).strip()
        
    return "-"

def kanun_yolu_bul(metin):
    bilgi = {"Yer": "Belirtilmemiş", "Süre": "Belirtilmemiş"}
    metin_lower = metin.lower()
    if "2 hafta" in metin_lower or "iki hafta" in metin_lower: bilgi["Süre"] = "2 Hafta"
    elif "1 hafta" in metin_lower or "bir hafta" in metin_lower or "7 gün" in metin_lower: bilgi["Süre"] = "1 Hafta (7 Gün)"
    elif "kesin" in metin_lower and "olmak üzere" in metin_lower:
        bilgi["Süre"] = "KESİN KARAR"
        bilgi["Yer"] = "-"
        return bilgi
    if "bölge adliye" in metin_lower or "istinaf" in metin_lower: bilgi["Yer"] = "Bölge Adliye (İstinaf)"
    elif "yargıtay" in metin_lower or "temyiz" in metin_lower: bilgi["Yer"] = "Yargıtay (Temyiz)"
    return bilgi

def analiz_yap(metin, dosya_adi):
    metin = metni_temizle(metin)
    bilgi = {"Dosya Adı": dosya_adi}
    
    # Temel Bilgiler
    patterns = {
        "Mahkeme": r"(T\.?C\.?.*?MAHKEMES.*?)Esas",
        "Esas No": r"ESAS\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Davacı": r"DAVACI\s*.*?[:;]\s*(.*?)(?=VEKİL|DAVALI)",
        "Davalı": r"DAVALI\s*.*?[:;]\s*(.*?)(?=VEKİL|DAVA|KONU)"
    }
    for k, v in patterns.items():
        m = re.search(v, metin, re.IGNORECASE)
        bilgi[k] = m.group(1).strip() if m else "-"
        
    bilgi["Dava Türü"] = "⚖️ ÖZEL HUKUK"
    if "ceza" in bilgi["Mahkeme"].lower(): bilgi["Dava Türü"] = "🛑 CEZA HUKUKU"
    elif "idare" in bilgi["Mahkeme"].lower(): bilgi["Dava Türü"] = "🏛️ İDARE HUKUKU"

    # Hüküm Bloğu
    metin_upper = metin.upper()
    hukum_blok = re.search(r"(HÜKÜM|GEREĞİ DÜŞÜNÜLDÜ)\s*[:;](.*)", metin_upper, re.DOTALL)
    alan = hukum_blok.group(2) if hukum_blok else metin_upper[-1000:]
    
    if "KISMEN KABUL" in alan: bilgi["Sonuç"] = "⚠️ KISMEN KABUL"
    elif re.search(r"DAVANIN\s*KABUL", alan) or re.search(r"İTİRAZIN\s*İPTAL", alan): bilgi["Sonuç"] = "✅ KABUL (Davacı)"
    elif re.search(r"DAVANIN\s*RED", alan) or "BERAAT" in alan: bilgi["Sonuç"] = "❌ RED (Davalı)"
    else: bilgi["Sonuç"] = "❓ Belirsiz"

    # --- MALİ AYRIŞTIRMA (HATA BURADA DÜZELTİLDİ) ---
    # Kelimeleri çok spesifik seçiyoruz ve "para_bul_hassas" kullanıyoruz
    
    # 1. Vekalet Ücreti
    bilgi["Vekalet"] = para_bul_hassas(alan, ["vekalet ücreti", "ücreti vekalet"])
    
    # 2. Harç ve Giderler (Yargılama gideri öncelikli)
    gider = para_bul_hassas(alan, ["yargılama gideri", "yapılan masraf"])
    harc = para_bul_hassas(alan, ["karar ve ilam harcı", "bakiye harç", "harcın tahsili"])
    
    # Eğer Gider bulunduysa onu göster, yoksa Harcı göster
    if gider != "-":
        bilgi["Harç"] = f"{gider} (Gider)"
    elif harc != "-":
        bilgi["Harç"] = f"{harc} (Harç)"
    else:
        bilgi["Harç"] = "-"
        
    # 3. Tazminat
    bilgi["Tazminat"] = para_bul_hassas(alan, ["inkar tazminatı", "kötü niyet tazminatı"])
    
    oran = re.search(r"%(\d+)", alan)
    if oran and bilgi["Tazminat"] == "-":
        bilgi["Tazminat"] = f"%{oran.group(1)} Oranında"

    itiraz = kanun_yolu_bul(alan)
    bilgi["İtiraz Yeri"] = itiraz["Yer"]
    bilgi["İtiraz Süresi"] = itiraz["Süre"]
    
    return bilgi

# --- 4. ARAYÜZ ---

st.title("⚖️ Hukuk Asistanı v3.1")
st.markdown("Hata düzeltmeleri yapıldı: Harç ve Vekalet ücretleri artık karışmıyor.")

with st.sidebar:
    st.header("💾 Arşiv")
    df_db = veritabani_yukle()
    st.metric("İşlenen Dosya", len(df_db))
    if not df_db.empty:
        st.download_button("Excel İndir", df_db.to_csv(index=False).encode('utf-8'), "arsiv.csv")

uploaded_file = st.file_uploader("Dosya Yükle (PDF)", type="pdf")

if uploaded_file:
    if "analiz_sonucu" not in st.session_state or st.session_state.dosya_adi != uploaded_file.name:
        text = pdf_oku(uploaded_file)
        st.session_state.analiz_sonucu = analiz_yap(text, uploaded_file.name)
        st.session_state.dosya_adi = uploaded_file.name
    
    veri = st.session_state.analiz_sonucu

    renk = "blue"
    if "CEZA" in veri["Dava Türü"]: renk = "red"
    elif "İDARE" in veri["Dava Türü"]: renk = "orange"
    
    st.markdown(f"""
    <div style="background-color:{renk}; padding:10px; border-radius:5px; color:white; text-align:center; margin-bottom:10px;">
        <b>TÜR:</b> {veri["Dava Türü"]} | <b>MAHKEME:</b> {veri["Mahkeme"]}
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📝 Kayıt", "💰 Mali Tablo", "🚀 İtiraz"])

    with tab1:
        st.subheader("Doğrulama")
        with st.form("kayit_formu"):
            c1, c2 = st.columns(2)
            yeni_esas = c1.text_input("Esas No", veri["Esas No"])
            secenekler = ["✅ KABUL (Davacı)", "❌ RED (Davalı)", "⚠️ KISMEN KABUL", "❓ Belirsiz"]
            idx = 3
            if veri["Sonuç"] in secenekler: idx = secenekler.index(veri["Sonuç"])
            yeni_sonuc = c2.selectbox("Sonuç", secenekler, index=idx)
            c3, c4 = st.columns(2)
            yeni_davaci = c3.text_input("Davacı", veri["Davacı"])
            yeni_davali = c4.text_input("Davalı", veri["Davalı"])
            st.write("---")
            if st.form_submit_button("✅ Onayla ve Kaydet"):
                kayit = veri.copy()
                kayit.update({"Esas No": yeni_esas, "Sonuç": yeni_sonuc, "Davacı": yeni_davaci, "Davalı": yeni_davali})
                veritabanina_kaydet(kayit)
                st.success("Kayıt Başarılı!")

    with tab2:
        st.subheader("💸 Mali Sorumluluklar")
        col_m1, col_m2, col_m3 = st.columns(3)
        
        with col_m1:
            st.markdown(f"""
            <div class="mali-kart">
                <span class="mali-baslik">⚖️ Vekalet Ücreti</span>
                <span class="mali-tutar" style="color:#e67e22">{veri['Vekalet']}</span>
            </div>
            """, unsafe_allow_html=True)
            
        with col_m2:
            st.markdown(f"""
            <div class="mali-kart">
                <span class="mali-baslik">🏛️ Harç & Giderler</span>
                <span class="mali-tutar" style="color:#2980b9">{veri['Harç']}</span>
            </div>
            """, unsafe_allow_html=True)
            
        with col_m3:
            st.markdown(f"""
            <div class="mali-kart">
                <span class="mali-baslik">⚡ Tazminat</span>
                <span class="mali-tutar" style="color:#c0392b">{veri['Tazminat']}</span>
            </div>
            """, unsafe_allow_html=True)

    with tab3:
        st.subheader("📅 İtiraz Rehberi")
        if "KESİN" in veri["İtiraz Süresi"]: st.error("⛔ BU KARAR KESİNDİR.")
        else:
            c_yol1, c_yol2 = st.columns(2)
            c_yol1.warning(f"📍 **Yer:** {veri['İtiraz Yeri']}")
            c_yol2.warning(f"⏳ **Süre:** {veri['İtiraz Süresi']}")
