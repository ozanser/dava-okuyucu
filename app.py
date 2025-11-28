import streamlit as st
import PyPDF2
import re
import pandas as pd
import os

# --- 1. AYARLAR & TASARIM ---
st.set_page_config(page_title="LegalPro Asistan", layout="wide", page_icon="⚖️")
VERITABANI_DOSYASI = "dava_takip_sistemi.csv"

# --- ÖZEL CSS (PREMIUM GÖRÜNÜM) ---
st.markdown("""
<style>
    /* Genel Arkaplan ve Font */
    .main {
        background-color: #f8f9fa;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* Başarı/Hata Mesajları */
    .stSuccess { background-color: #d1e7dd; border-radius: 10px; border: none; color: #0f5132; }
    .stError { background-color: #f8d7da; border-radius: 10px; border: none; color: #842029; }
    
    /* Özel Bilgi Kartları */
    .info-card {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-left: 5px solid #2c3e50;
        margin-bottom: 20px;
    }
    
    .card-title {
        font-size: 0.9rem;
        color: #6c757d;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 8px;
        font-weight: 700;
    }
    
    .card-value {
        font-size: 1.1rem;
        color: #2c3e50;
        font-weight: 600;
        word-wrap: break-word;
    }

    /* Mali Kartlar (Renkli) */
    .money-card {
        text-align: center;
        padding: 15px;
        border-radius: 10px;
        color: white;
        margin-bottom: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Form Alanları */
    div[data-testid="stForm"] {
        background-color: white;
        padding: 30px;
        border-radius: 15px;
        box-shadow: 0 10px 20px rgba(0,0,0,0.05);
        border: 1px solid #e9ecef;
    }
    
    /* Başlıklar */
    h3, h4, h5 { color: #2c3e50 !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. FONKSİYONLAR ---

def veritabani_yukle():
    if os.path.exists(VERITABANI_DOSYASI): return pd.read_csv(VERITABANI_DOSYASI)
    cols = ["Dosya Adı", "Mahkeme", "Esas No", "Karar No", "Davacı", "Davacı Vekili", "Davalı", 
            "Dava Konusu", "Dava Tarihi", "Karar Tarihi", "Yazım Tarihi", 
            "Sonuç", "Vekalet Ücreti", "Yargılama Gideri", "Harç"]
    return pd.DataFrame(columns=cols)

def veritabanina_kaydet(yeni_veri):
    df = veritabani_yukle()
    yeni_satir = pd.DataFrame([yeni_veri])
    df = pd.concat([df, yeni_satir], ignore_index=True)
    df.to_csv(VERITABANI_DOSYASI, index=False)

def metni_temizle(metin):
    temiz = metin.replace("\n", " ").strip()
    temiz = re.sub(r'\s+', ' ', temiz)
    temiz = re.sub(r'(?<=\d)\?(?=\d)', '0', temiz)
    duzeltmeler = {r"HAK M": "HAKİM", r"KAT P": "KATİP", r"VEK L": "VEKİL", r"T RAZ": "İTİRAZ", r"PTAL": "İPTAL"}
    for b, d in duzeltmeler.items(): temiz = re.sub(b, d, temiz, flags=re.IGNORECASE)
    return temiz

def pdf_oku(dosya):
    okuyucu = PyPDF2.PdfReader(dosya)
    metin = ""
    for sayfa in okuyucu.pages: metin += sayfa.extract_text() or ""
    return metin

def para_bul(metin, anahtar_kelime_grubu):
    for anahtar in anahtar_kelime_grubu:
        m = re.search(fr"([\d\.,]+\s*TL).{{0,100}}?{anahtar}|{anahtar}.{{0,100}}?([\d\.,]+\s*TL)", metin, re.IGNORECASE)
        if m: return (m.group(1) or m.group(2)).strip()
    return "0,00 TL"

def analiz_yap(metin, dosya_adi):
    metin = metni_temizle(metin)
    bilgi = {"Dosya Adı": dosya_adi}
    
    # Künye Regex
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
    for k, v in regexler.items():
        m = re.search(v, metin, re.IGNORECASE)
        bilgi[k] = m.group(1).strip().replace(":", "") if m else "-"

    # Sonuç ve Mali
    alan = metin.upper()[-2500:] # Son kısımlara bak
    if "KISMEN KABUL" in alan: bilgi["Sonuç"] = "⚠️ KISMEN KABUL"
    elif re.search(r"DAVANIN\s*KABUL", alan) or re.search(r"İTİRAZIN\s*İPTAL", alan): bilgi["Sonuç"] = "✅ KABUL"
    elif re.search(r"DAVANIN\s*RED", alan): bilgi["Sonuç"] = "❌ RED"
    else: bilgi["Sonuç"] = "❓ Belirsiz"

    bilgi["Vekalet Ücreti"] = para_bul(alan, ["vekalet ücreti", "ücreti vekalet"])
    bilgi["Yargılama Gideri"] = para_bul(alan, ["toplam yargılama gideri", "yapılan masraf"])
    bilgi["Harç"] = para_bul(alan, ["bakiye", "karar harcı", "eksik kalan"])
    return bilgi

# --- 3. ARAYÜZ (LAYOUT) ---

# Sidebar
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2237/2237936.png", width=80)
    st.title("LegalPro v1.0")
    st.markdown("---")
    df = veritabani_yukle()
    st.metric("Arşivlenen Dosya", len(df))
    if not df.empty:
        st.download_button("📂 Excel Raporu İndir", df.to_csv(index=False).encode('utf-8'), "LegalPro_Rapor.csv")

# Header
st.markdown("<h1 style='text-align: center; color: #2c3e50;'>⚖️ Akıllı Dava Analiz Sistemi</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #7f8c8d;'>Mahkeme kararlarını saniyeler içinde analiz edin, doğrulayın ve arşivleyin.</p>", unsafe_allow_html=True)

# Dosya Yükleme (Ortalı ve Şık)
col_upload_1, col_upload_2, col_upload_3 = st.columns([1, 2, 1])
with col_upload_2:
    dosya = st.file_uploader("PDF Dosyasını Buraya Bırakın", type="pdf")

if dosya:
    if "analiz_sonucu" not in st.session_state or st.session_state.dosya_adi != dosya.name:
        text = pdf_oku(dosya)
        st.session_state.analiz_sonucu = analiz_yap(text, dosya.name)
        st.session_state.dosya_adi = dosya.name
    
    veri = st.session_state.analiz_sonucu

    st.markdown("---")

    # --- BÖLÜM 1: DASHBOARD GÖRÜNÜMÜ (Read-Only) ---
    
    # 1. Satır: Sonuç ve Mali Özet
    c_res, c_m1, c_m2, c_m3 = st.columns([1.5, 1, 1, 1])
    
    with c_res:
        renk = "#198754" if "KABUL" in veri["Sonuç"] else "#dc3545"
        st.markdown(f"""
        <div style="background-color:{renk}; padding:25px; border-radius:12px; color:white; text-align:center;">
            <h3 style="margin:0; color:white;">{veri["Sonuç"]}</h3>
            <small>KARAR SONUCU</small>
        </div>
        """, unsafe_allow_html=True)
        
    with c_m1:
        st.markdown(f'<div class="money-card" style="background-color:#0d6efd"><h5>Vekalet</h5><h2>{veri["Vekalet Ücreti"]}</h2></div>', unsafe_allow_html=True)
    with c_m2:
        st.markdown(f'<div class="money-card" style="background-color:#fd7e14"><h5>Giderler</h5><h2>{veri["Yargılama Gideri"]}</h2></div>', unsafe_allow_html=True)
    with c_m3:
        st.markdown(f'<div class="money-card" style="background-color:#6c757d"><h5>Harç</h5><h2>{veri["Harç"]}</h2></div>', unsafe_allow_html=True)

    # 2. Satır: Kimlik Kartları (HTML CSS ile)
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown(f"""
        <div class="info-card">
            <div class="card-title">DOSYA KİMLİĞİ</div>
            <div class="card-value">{veri['Mahkeme']}</div>
            <hr>
            <div style="display:flex; justify-content:space-between;">
                <div><small>ESAS NO</small><br><b>{veri['Esas No']}</b></div>
                <div><small>KARAR NO</small><br><b>{veri['Karar No']}</b></div>
                <div><small>TARİH</small><br><b>{veri['Karar Tarihi']}</b></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="info-card" style="border-left-color: #0d6efd;">
            <div class="card-title">TARAFLAR</div>
            <div style="display:flex; justify-content:space-between;">
                <div style="width:48%">
                    <small>DAVACI</small><br>
                    <div class="card-value" style="font-size:1rem;">{veri['Davacı']}</div>
                    <small style="color:#666">Vekili: {veri['Davacı Vekili']}</small>
                </div>
                <div style="border-left:1px solid #ddd; margin:0 10px;"></div>
                <div style="width:48%">
                    <small>DAVALI</small><br>
                    <div class="card-value" style="font-size:1rem;">{veri['Davalı']}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # --- BÖLÜM 2: DÜZENLEME PANELİ (FORM) ---
    st.subheader("📝 Veri Doğrulama ve Kayıt")
    st.info("Yukarıdaki veriler otomatik çekilmiştir. Hata varsa aşağıdaki panelden düzelterek kaydedebilirsiniz.")
    
    with st.form("master_form"):
        # Gruplandırma için Container kullanıyoruz (Çerçeveli kutu)
        
        # 1. Grup: Künye
        st.markdown("#### 🗂 Dosya Bilgileri")
        k1, k2, k3 = st.columns(3)
        y_mahkeme = k1.text_input("Mahkeme", veri["Mahkeme"])
        y_esas = k2.text_input("Esas No", veri["Esas No"])
        y_karar = k3.text_input("Karar No", veri["Karar No"])
        
        # 2. Grup: Tarihler
        st.markdown("#### 📅 Tarihler")
        t1, t2, t3 = st.columns(3)
        y_dava_t = t1.text_input("Dava Tarihi", veri["Dava Tarihi"])
        y_karar_t = t2.text_input("Karar Tarihi", veri["Karar Tarihi"])
        y_yazim_t = t3.text_input("Yazım Tarihi", veri["Yazım Tarihi"])
        
        # 3. Grup: Taraflar
        st.markdown("#### 👥 Taraflar")
        p1, p2, p3 = st.columns([2, 2, 2])
        y_davaci = p1.text_input("Davacı", veri["Davacı"])
        y_vekil = p2.text_input("Davacı Vekili", veri["Davacı Vekili"])
        y_davali = p3.text_input("Davalı", veri["Davalı"])
        
        # 4. Grup: Mali
        st.markdown("#### 💰 Mali Sonuçlar")
        m1, m2, m3, m4 = st.columns(4)
        y_sonuc = m1.selectbox("Sonuç", ["✅ KABUL", "❌ RED", "⚠️ KISMEN KABUL", "❓ Belirsiz"], index=0)
        y_vekalet = m2.text_input("Vekalet Ücreti", veri["Vekalet Ücreti"])
        y_gider = m3.text_input("Yargılama Gideri", veri["Yargılama Gideri"])
        y_harc = m4.text_input("Harç", veri["Harç"])
        
        # Alt Bilgi (Gizli, Dava Konusu)
        y_konu = st.text_input("Dava Konusu (Opsiyonel)", veri["Dava Konusu"])

        st.markdown("---")
        
        # Kaydet Butonu (Tam Genişlik)
        if st.form_submit_button("✅ VERİLERİ ONAYLA VE ARŞİVLE", use_container_width=True):
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
            st.success(f"Dosya ({y_esas}) başarıyla veritabanına işlendi!")
            st.rerun()
