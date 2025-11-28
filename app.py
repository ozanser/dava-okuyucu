import streamlit as st
import PyPDF2
import re

st.set_page_config(page_title="Hukuk Okuyucu", layout="centered")
st.title("📄 Web Tabanlı Dava Okuyucu")

uploaded_file = st.file_uploader("PDF Dosyanı Buraya Bırak", type="pdf")

if uploaded_file:
    okuyucu = PyPDF2.PdfReader(uploaded_file)
    metin = ""
    for sayfa in okuyucu.pages:
        metin += sayfa.extract_text() or ""

    bilgiler = {}
    aramalar = {
        "Davacı": r"DAVACI\s*[:;]\s*(.*?)(?=\n)",
        "Davalı": r"DAVALI\s*[:;]\s*(.*?)(?=\n)",
        "Konu": r"KONU\s*[:;]\s*(.*?)(?=\n)",
        "Esas No": r"ESAS\s*NO\s*[:;]?\s*(\d{4}/\d+)",
        "Karar": r"(HÜKÜM|KARAR)\s*[:;]\s*(.*)"
    }

    st.header("🔍 Bulunan Sonuçlar")
    for baslik, kalip in aramalar.items():
        bulunan = re.search(kalip, metin, re.IGNORECASE | re.DOTALL)
        deger = bulunan.group(1).strip()[:100] if bulunan else "Bulunamadı"
        st.text_input(baslik, value=deger)
