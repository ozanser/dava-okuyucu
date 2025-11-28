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
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #dee2e6;
        margin-bottom: 10px;
        text-align: center;
    }
    .mali-baslik { font-weight: bold; color: #495057; display: block; margin-bottom: 5px;}
    .mali-tutar { font-size: 1.2rem; font-weight: bold; color: #0d6efd; }
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

def para_bul(metin, kelime_listesi):
    """Verilen kelime listesindeki ifadelerin yanındaki para tutarını bulur."""
    for kelime in kelime_listesi:
        # Regex: Sayı + TL (Örn: 1.500,00 TL)
        regex_str = r"([\d\.,]+\s*TL).*?{0}|{0}.*?([\d\.,]+\s*TL)".format(kelime)
        m = re.search(regex_str, metin, re.IGNORECASE)
        if m:
            return (m.group(1) or m.group(2)).strip()
    return "-"

def kanun_yolu_bul(metin):
    """İstinaf/Temyiz süresini ve yerini bulur."""
    bilgi = {"Yer": "Belirtilmemiş", "Süre": "Belirtilmemiş"}
    metin_lower = metin.lower()
    
    # Süre Tespiti
    if "2 hafta" in metin_lower or "iki hafta" in metin_lower:
        bilgi["Süre"] = "2 Hafta"
    elif "1 hafta" in metin_lower or "bir hafta" in metin_lower or "7 gün" in metin_lower:
        bilgi["Süre"] = "1 Hafta (7 Gün)"
    elif "kesin" in metin_lower and "olmak üzere" in metin_lower:
        bilgi["Süre"] = "KESİN KARAR (İtiraz Yolu Kapalı)"
        bilgi["Yer"] = "-"
        return bilgi

    # Yer Tespiti
    if "bölge adliye" in metin_lower or "istinaf" in metin_lower:
        bilgi["Yer"] = "Bölge Adliye Mahkemesi (İstinaf)"
    elif "yargıtay" in metin_lower or "temyiz" in metin_lower:
        bilgi["Yer"] = "Yargıtay (Temyiz)"
        
    return bilgi

def analiz_yap(metin, dosya_adi):
    metin = metni_temizle(metin)
    bilgi = {"Dosya Adı": dosya_adi}
    
    # 1. Temel Bilgiler
    patterns = {
        "Mahkeme": r"(T\.?C\.?.*?MAHKEMES.*?)Esas",
        "Esas No": r"ESAS\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Davacı": r"DAVACI\s*.*?[:;]\s*(.*?)(?=VEKİL|DAVALI)",
        "Davalı": r"DAVALI\s*.*?[:;]\s*(.*?)(?=VEKİL|DAVA|KONU)"
    }
    for k, v in patterns.items():
        m = re.search(v, metin, re.IGNORECASE)
        bilgi[k] = m.group(1).strip() if m else "-"
        
    # 2. Dava Türü Tespiti
    bilgi["Dava Türü"] = "⚖️ ÖZEL HUKUK"
    if "ceza" in bilgi["Mahkeme"].lower(): bilgi["Dava Türü"] = "🛑 CEZA HUKUKU"
    elif "idare" in bilgi["Mahkeme"].lower(): bilgi["Dava Türü"] = "🏛️ İDARE HUKUKU"

    # 3. Sonuç Analizi (Hüküm Odaklı)
    metin_upper = metin.upper()
    hukum_blok = re.search(r"(HÜKÜM|GEREĞİ DÜŞÜNÜLDÜ)\s*[:;](.*)", metin_upper, re.DOTALL)
    alan = hukum_blok.group(2) if hukum_blok else metin_upper[-1000:]
    
    if "KISMEN KABUL" in alan: bilgi["Sonuç"] = "⚠️ KISMEN KABUL"
    elif re.search(r"DAVANIN\s*KABUL", alan) or re.search(r"İTİRAZIN\s*İPTAL", alan): bilgi["Sonuç"] = "✅ KABUL (Davacı)"
    elif re.search(r"DAVANIN\s*RED", alan) or "BERAAT" in alan: bilgi["Sonuç"] = "❌ RED (Davalı)"
    else: bilgi["Sonuç"] = "❓ Belirsiz"

    # 4. Mali Yükümlülükler (Harç, Tazminat, Vekalet)
    bilgi["Vekalet"] = para_bul(metin, ["vekalet ücreti"])
    bilgi["Harç"] = para_bul(metin, ["harcın", "harç", "bakiye"])
    bilgi["Tazminat"] = para_bul(metin, ["inkar tazminatı", "kötü niyet tazminatı", "tazminat"])
    
    # Tazminat Oranı Bul (%20 veya %40 gibi)
    oran = re.search(r"%(\d+)", alan)
    if oran and bilgi["Tazminat"] == "-":
        bilgi["Tazminat"] = f"%{oran.group(1)} Oranında Tazminat"

    # 5. İtiraz Yolu (Kanun Yolu)
    itiraz = kanun_yolu_bul(alan) # Sadece hüküm kısmında ara
    bilgi["İtiraz Yeri"] = itiraz["Yer"]
    bilgi["İtiraz Süresi"] = itiraz["Süre"]
    
    return bilgi

# --- 4. ARAYÜZ ---

st.title("⚖️ Hukuk Asistanı v3: Tam Kapsamlı Analiz")
st.markdown("Dava sonucu, tüm mali yükümlülükler ve itiraz süreçleri tek ekranda.")

with st.sidebar:
    st.header("💾 Arşiv")
    df_db = veritabani_yukle()
    st.metric("İşlenen Dosya", len(df_db))
    if not df_db.empty:
        st.download_button("Excel İndir", df_db.to_csv(index=False).encode('utf-8'), "dava_arsivi.csv")

uploaded_file = st.file_uploader("Dosya Yükle (PDF)", type="pdf")

if uploaded_file:
    if "analiz_sonucu" not in st.session_state or st.session_state.dosya_adi != uploaded_file.name:
        text = pdf_oku(uploaded_file)
        st.session_state.analiz_sonucu = analiz_yap(text, uploaded_file.name)
        st.session_state.dosya_adi = uploaded_file.name
    
    veri = st.session_state.analiz_sonucu

    # --- ÜST BİLGİ KARTI ---
    renk = "blue"
    if "CEZA" in veri["Dava Türü"]: renk = "red"
    elif "İDARE" in veri["Dava Türü"]: renk = "orange"
    
    st.markdown(f"""
    <div style="background-color:{renk}; padding:10px; border-radius:5px; color:white; text-align:center; margin-bottom:10px;">
        <b>TÜR:</b> {veri["Dava Türü"]} | <b>MAHKEME:</b> {veri["Mahkeme"]}
    </div>
    """, unsafe_allow_html=True)

    # --- SEKME YAPISI ---
    tab1, tab2, tab3 = st.tabs(["📝 Doğrulama & Kayıt", "💰 Mali Tablo", "🚀 İtiraz Yolu"])

    with tab1:
        st.subheader("Analiz Sonuçlarını Doğrula")
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
            if st.form_submit_button("✅ Onayla ve Veritabanına Kaydet"):
                kayit = veri.copy()
                kayit.update({"Esas No": yeni_esas, "Sonuç": yeni_sonuc, "Davacı": yeni_davaci, "Davalı": yeni_davali})
                veritabanina_kaydet(kayit)
                st.success("Kayıt Başarılı!")

    with tab2:
        st.subheader("💸 Kim, Neyi Ödeyecek?")
        st.info("Aşağıdaki tutarlar karardan otomatik çekilmiştir. Kaybeden taraf öder.")
        
        col_m1, col_m2, col_m3 = st.columns(3)
        
        with col_m1:
            st.markdown(f"""
            <div class="mali-kart">
                <span class="mali-baslik">⚖️ Vekalet Ücreti</span>
                <span class="mali-tutar">{veri['Vekalet']}</span>
                <br><small>Avukata ödenir</small>
            </div>
            """, unsafe_allow_html=True)
            
        with col_m2:
            st.markdown(f"""
            <div class="mali-kart">
                <span class="mali-baslik">🏛️ Harç & Giderler</span>
                <span class="mali-tutar">{veri['Harç']}</span>
                <br><small>Devlete/Davacıya ödenir</small>
            </div>
            """, unsafe_allow_html=True)
            
        with col_m3:
            st.markdown(f"""
            <div class="mali-kart">
                <span class="mali-baslik">⚡ Tazminat (İcra İnkar vb.)</span>
                <span class="mali-tutar">{veri['Tazminat']}</span>
                <br><small>Ceza tazminatı</small>
            </div>
            """, unsafe_allow_html=True)

    with tab3:
        st.subheader("📅 Karara İtiraz Rehberi")
        
        if "KESİN" in veri["İtiraz Süresi"]:
            st.error("⛔ BU KARAR KESİNDİR. İtiraz yolu kapalıdır.")
        else:
            c_yol1, c_yol2 = st.columns(2)
            with c_yol1:
                st.warning(f"📍 **Başvuru Yeri:**\n\n{veri['İtiraz Yeri']}")
            with c_yol2:
                st.warning(f"⏳ **Son Başvuru Süresi:**\n\n{veri['İtiraz Süresi']}")
                
            st.markdown("""
            > **Önemli Not:** Süreler, gerekçeli kararın size **tebliğ edildiği** tarihten itibaren başlar. 
            > Süreyi kaçırırsanız karar kesinleşir ve icraya konulabilir.
            """)
