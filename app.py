import streamlit as st
import PyPDF2
import re
import pandas as pd

# --- 1. AYARLAR ---
st.set_page_config(page_title="Hukuk Asistanı", layout="wide", page_icon="⚖️")

# --- 2. FONKSİYONLAR ---

def metni_temizle(metin):
    temiz = metin.replace("\n", " ").strip()
    temiz = re.sub(r'\s+', ' ', temiz)
    temiz = re.sub(r'(?<=\d)\?(?=\d)', '0', temiz) 
    temiz = re.sub(r'(?<=\d)\?', '', temiz) 
    
    duzeltmeler = {
        r"HAK M": "HAKİM", r"KAT P": "KATİP", r"VEK L": "VEKİL", 
        r"T RAZ": "İTİRAZ", r"PTAL": "İPTAL"
    }
    for b, d in duzeltmeler.items(): temiz = re.sub(b, d, temiz, flags=re.IGNORECASE)
    return temiz

def pdf_oku(dosya):
    okuyucu = PyPDF2.PdfReader(dosya)
    metin = ""
    for sayfa in okuyucu.pages: metin += sayfa.extract_text() or ""
    return metin

def para_bul(metin, anahtar_kelime_grubu):
    for anahtar in anahtar_kelime_grubu:
        regex = fr"([\d\.,]+\s*TL).{{0,100}}?{anahtar}|{anahtar}.{{0,100}}?([\d\.,]+\s*TL)"
        m = re.search(regex, metin, re.IGNORECASE)
        if m: return (m.group(1) or m.group(2)).strip()
    return "0,00 TL"

def dava_turu_belirle(mahkeme_adi, metin):
    mahkeme_lower = mahkeme_adi.lower()
    metin_lower = metin.lower()
    
    if "icra" in mahkeme_lower: return "⚡ İCRA HUKUKU"
    if "ceza" in mahkeme_lower: return "🛑 CEZA HUKUKU"
    if "idare" in mahkeme_lower: return "🏛️ İDARE HUKUKU"
    
    if "sanık" in metin_lower: return "🛑 CEZA HUKUKU"
    if "yürütme" in metin_lower: return "🏛️ İDARE HUKUKU"
    if "ödeme emri" in metin_lower: return "⚡ İCRA HUKUKU"
    
    return "⚖️ ÖZEL HUKUK"

# --- ÖZET MOTORLARI ---
def dilekce_ozetle(metin):
    ozet = ""
    konu_ara = re.search(r"(?:KONU|DAVA KONUSU|TALEP KONUSU)\s*[:;]\s*(.*?)(?=\n|AÇIKLAMALAR|TEBLİĞ|HUKUKİ SEBEPLER)", metin, re.IGNORECASE | re.DOTALL)
    if konu_ara: ozet += f"📌 KONU: {konu_ara.group(1)[:400].replace('\n', ' ')}...\n"
    
    talep_ara = re.search(r"(?:NETİCE|SONUÇ VE İSTEM|SONUÇ VE TALEP|KARAR VERİLMESİNİ)\s*[:;]?\s*(.*)", metin, re.IGNORECASE | re.DOTALL)
    if talep_ara:
        temiz = re.split(r"(?:Av\.|Avukat|Saygılarımla)", talep_ara.group(1), flags=re.IGNORECASE)[0]
        ozet += f"🎯 TALEP: {temiz.replace('\n', ' ')}"
    return ozet if ozet else "Özet çıkarılamadı."

def gerekce_analiz_et(metin):
    blok = re.search(r"(GEREKÇE|GEREĞİ DÜŞÜNÜLDÜ|TÜRK MİLLETİ ADINA)\s*[:;]?(.*?)(HÜKÜM|KARAR\s*:)", metin, re.IGNORECASE | re.DOTALL)
    if not blok: return "Gerekçe bloğu net ayrıştırılamadı."
    
    icerik = blok.group(2).replace("\n", " ").strip()
    gerekce_ozeti = ""
    
    yasa = re.search(r"(TBK|TMK|HMK|İİK|Madde)\s*\d+", icerik, re.IGNORECASE)
    if yasa: gerekce_ozeti += f"⚖️ DAYANAK: {yasa.group(0)}\n"
    
    sonuc_cumlesi = re.search(r"([^.]*?(?:anlaşılmakla|gerektiği|kanaatine varılarak|sabit görülmekle)[^.]*\.)", icerik, re.IGNORECASE)
    if sonuc_cumlesi:
        gerekce_ozeti += f"👉 TESPİT: {sonuc_cumlesi.group(1).strip()}"
    else:
        gerekce_ozeti += f"📝 ÖZET: ...{icerik[-400:]}"
    
    return gerekce_ozeti

def analiz_yap(metin, dosya_adı):
    ham_metin = metin
    metin = metni_temizle(metin)
    bilgi = {"Dosya Adı": dosya_adı}
    
    regexler = {
        # Mahkeme Adı: Kapsar ve T.C. hariç her şeyi alır.
        "Mahkeme": r"(?:T\.?C\.?\s*)?(.+?MAHKEMES[İI](?:\s+HAKİMLİĞİ)?)", 
        "Esas No": r"ESAS\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Karar No": r"KARAR\s*NO\s*[:;]?\s*['\"]?,?[:]?\s*(\d{4}/\d+)",
        "Dava Konusu": r"\bDAVA\b\s*[:;]?\s*(.*?)(?=DAVA TARİHİ|KARAR TARİHİ|ESAS)",
        "Davacı": r"DAVACI(?:LAR)?\s*[:;]?\s*(.*?)(?=VEKİL|DAVALI)",
        "Davacı Vekili": r"(?:DAVACI\s*)?VEKİL[İI]\s*[:;]?\s*(.*?)(?=DAVALI|DAVA)",
        "Davalı": r"DAVALI(?:LAR)?\s*[:;]?\s*(.*?)(?=VEKİL|DAVA|KONU)",
        "Davalı Vekili": r"DAVALI.*?VEKİL[İI]\s*[:;]?\s*(.*?)(?=DAVA|KONU)",
        "Dava Tarihi": r"DAVA\s*TARİH[İI]\s*[:;]?\s*(\d{2}[./]\d{2}[./]\d{4})",
        "Karar Tarihi": r"KARAR\s*TARİH[İI]\s*[:;]?\s*(\d{2}[./]\d{2}[./]\d{4})"
    }
    
    for k, v in regexler.items():
        m = re.search(v, metin, re.IGNORECASE | re.DOTALL)
        if m:
            raw_val = m.group(1).replace(":", "").strip()
            bilgi[k] = raw_val[:500]
        else:
            bilgi[k] = ""
    
    # --- ÖZEL TEMİZLİK: MAHKEME ADI ---
    if bilgi["Mahkeme"]:
        temiz_ad = bilgi["Mahkeme"]
        # T.C. ibaresini ve fazlalıkları (GEREKÇELİ, ESAS NO vb.) kesip atar
        temiz_ad = re.split(r"(?:GEREKÇELİ|ESAS|KARAR)\s*(?:NO)?", temiz_ad, flags=re.IGNORECASE)[0]
        bilgi["Mahkeme"] = re.sub(r'\s+', ' ', temiz_ad).strip()
    # -----------------------------------

    bilgi["Dava Türü"] = dava_turu_belirle(bilgi["Mahkeme"], metin)

    # Sonuç Analizi
    alan = metin.upper()[-3000:]
    if "KISMEN KABUL" in alan:
        bilgi["Sonuç"] = "⚠️ KISMEN KABUL"
        bilgi["Kazanan"] = "Ortak"
        bilgi["Ödeme Yönü"] = "Paylaşılır"
    elif re.search(r"DAVANIN\s*KABUL", alan) or re.search(r"İTİRAZIN\s*İPTAL", alan):
        bilgi["Sonuç"] = "✅ KABUL"
        bilgi["Kazanan"] = "DAVACI (Alacaklı)"
        bilgi["Ödeme Yönü"] = "🔴 DAVALI ÖDER -> 🔵 DAVACIYA"
    elif re.search(r"DAVANIN\s*RED", alan):
        bilgi["Sonuç"] = "❌ RED"
        bilgi["Kazanan"] = "DAVALI (Borçlu)"
        bilgi["Ödeme Yönü"] = "🔵 DAVACI ÖDER -> 🔴 DAVALIYA"
    else:
        bilgi["Sonuç"] = "❓ Belirsiz"
        bilgi["Kazanan"] = "-"
        bilgi["Ödeme Yönü"] = "-"

    bilgi["Vekalet Ücreti"] = para_bul(alan, ["vekalet ücreti", "ücreti vekalet"])
    bilgi["Yargılama Gideri"] = para_bul(alan, ["toplam yargılama gideri", "yapılan masraf", "yargılama giderinin"])
    bilgi["Harç"] = para_bul(alan, ["bakiye", "karar harcı", "eksik kalan"])
    
    bilgi["Gerekçe Özeti"] = gerekce_analiz_et(ham_metin)
    bilgi["Dilekçe Özeti"] = dilekce_ozetle(ham_metin)
    
    return bilgi

# --- 3. ARAYÜZ ---

st.title("⚖️ Hukuk Asistanı")
st.markdown("---")

dosya = st.file_uploader("Analiz Edilecek PDF Dosyasını Yükleyin", type="pdf")

if dosya:
    if "analiz_sonucu" not in st.session_state or st.session_state.dosya_adi != dosya.name:
        with st.spinner("Yapay zeka analiz ediyor..."):
            text = pdf_oku(dosya)
            st.session_state.analiz_sonucu = analiz_yap(text, dosya.name)
            st.session_state.dosya_adi = dosya.name
    
    veri = st.session_state.analiz_sonucu

    st.subheader("📝 Analiz Raporu")
    
    # 1. DOSYA KÜNYESİ
    st.write("###### 🗂 Dosya Künyesi")
    c1, c2, c3, c4 = st.columns(4)
    c1.text_input("Hukuk Türü", value=veri["Dava Türü"], disabled=True)
    c2.text_input("Mahkeme", veri["Mahkeme"]) # ARTIK TERTEMİZ
    c3.text_input("Esas No", veri["Esas No"])
    c4.text_input("Karar No", veri["Karar No"])
    
    # KONU VE TARİHLER
    c_konu, c_t1, c_t2 = st.columns([2, 1, 1])
    c_konu.text_input("Dava Konusu", veri["Dava Konusu"]) 
    c_t1.text_input("Dava Tarihi", veri["Dava Tarihi"])
    c_t2.text_input("Karar Tarihi", veri["Karar Tarihi"])

    st.markdown("---")

    # 2. TARAFLAR
    st.write("###### 👥 Taraflar")
    c4, c5 = st.columns(2)
    c4.text_area("Davacı Taraf", veri["Davacı"], height=68)
    c5.text_area("Davacı Vekili", veri["Davacı Vekili"], height=68)
    
    c6, c7 = st.columns(2)
    c6.text_area("Davalı Taraf", veri["Davalı"], height=68)
    c7.text_area("Davalı Vekili", veri["Davalı Vekili"], height=68)

    st.markdown("---")

    # 3. SONUÇ VE MALİ TABLO
    st.write("###### 🏆 Sonuç ve Mali Tablo")
    res1, res2, res3 = st.columns([1, 1, 2])
    res1.text_input("KARAR SONUCU", value=veri["Sonuç"], disabled=True)
    res2.text_input("KAZANAN", value=veri["Kazanan"], disabled=True)
    res3.text_input("ÖDEME YÖNÜ", value=veri["Ödeme Yönü"], disabled=True)
    
    m1, m2, m3 = st.columns(3)
    m1.text_input("Vekalet Ücreti", veri["Vekalet Ücreti"])
    m2.text_input("Giderler", veri["Yargılama Gideri"])
    m3.text_input("Harç", veri["Harç"])
    
    # 4. YAPAY ZEKÂ ÖZETİ
    st.markdown("---")
    st.write("###### 🧠 Yapay Zeka Özeti")
    
    if "KARAR" in veri["Karar No"] or "HÜKÜM" in text:
        st.info("💡 Mahkeme Gerekçesi Analizi:")
        st.text_area("Gerekçe", value=veri["Gerekçe Özeti"], height=120)
    else:
        st.info("💡 Dilekçe Talebi Analizi:")
        st.text_area("Talep", value=veri["Dilekçe Özeti"], height=120)
