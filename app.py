import streamlit as st
import io
import json
import re
from PIL import Image
from pdf2image import convert_from_bytes
from streamlit_drawable_canvas import st_canvas
from google import genai

# ---------------------------------------------------------
# Page Config & Apple Design System CSS
# ---------------------------------------------------------
st.set_page_config(page_title="MatheBW Tutor | J1 Oberstufe", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp {
        background-color: #F5F5F7;
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", sans-serif;
        color: #1D1D1F;
    }
    .apple-card {
        background: rgba(255, 255, 255, 0.85);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-radius: 18px;
        padding: 24px;
        margin-bottom: 24px;
        border: 1px solid rgba(0, 0, 0, 0.06);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
    }
    .apple-badge {
        background-color: #0071E3;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 8px;
    }
    .stButton>button {
        background: #0071E3 !important;
        color: white !important;
        border-radius: 980px !important;
        border: none !important;
        padding: 10px 24px !important;
        font-weight: 500 !important;
        box-shadow: 0 2px 8px rgba(0, 113, 227, 0.3) !important;
        transition: all 0.2s ease !important;
    }
    .stButton>button:hover {
        background: #0077ED !important;
        transform: scale(1.02);
    }
    h1, h2, h3 {
        color: #1D1D1F !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em !important;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Sidebar & Gemini Client Init
# ---------------------------------------------------------
with st.sidebar:
    st.title(" MatheBW Tutor")
    st.caption("J1 Oberstufe Baden-Württemberg")
    st.markdown("---")
    user_api_key = st.text_input("Google Gemini API-Key", type="password", help="Kostenlosen Key auf aistudio.google.com holen")

# Fallback: API Key aus Streamlit Secrets (wenn gehostet)
api_key = None
if user_api_key:
    api_key = user_api_key
elif "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]

# ---------------------------------------------------------
# Helper Functions: KI-Aufrufe mit Fehlerbehandlung
# ---------------------------------------------------------
def prepare_pil_image(image_bytes):
    """Konvertiert Byte-Daten sicher in ein PIL RGB Image."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'RGB':
        img = img.convert('RGB')
    return img

def analyze_goodnotes_page(client, image_bytes):
    image = prepare_pil_image(image_bytes)
    prompt = (
        "Du bist ein Mathematik-Tutor für das Gymnasium in Baden-Württemberg (Jahrgangsstufe J1 Oberstufe).\n"
        "Analysiere diese Seite einer GoodNotes-Mitschrift.\n"
        "1. Welches mathe-spezifische Thema der J1 (z. B. Analysis: Differentialrechnung/Kurvendiskussion, "
        "Vektorgeometrie/Ebenen oder Stochastik/Bedingte Wahrscheinlichkeit) wird behandelt?\n"
        "2. Erkläre das Thema verständlich und anschaulich mit einem strukturierten Text.\n"
        "3. Gib am Ende eine Zusammenfassung der wichtigsten Formeln und Regeln in Stichpunkten.\n\n"
        "Formatiere deine Antwort in klar strukturiertem Markdown."
    )
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[image, prompt]
    )
    return response.text

def generate_exam_quiz(client, topic_context):
    prompt = f"""
    Basierend auf folgendem Thema aus der J1 Oberstufe BW:
    {topic_context}
    
    Erstelle eine prüfungsnahe Mathe-Aufgabe im Stil des Abiturs Baden-Württemberg (Pflichtteil ohne WTR oder Wahlteil mit WTR).
    Gib das Ergebnis zwingend im folgenden JSON-Format zurück:
    {{
        "aufgabe": "Die detaillierte Aufgabenstellung mit konkreten Zahlenwerten und Funktionen.",
        "musterloesung": "Schritt-für-Schritt Musterlösung inklusive Endergebnis."
    }}
    Gib NUR das valide JSON zurück, keinerlei zusätzlichen Text.
    """
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    try:
        clean_content = re.search(r'\{.*\}', response.text, re.DOTALL).group(0)
        return json.loads(clean_content)
    except Exception:
        return {
            "aufgabe": "Bestimme die erste Ableitung der Funktion f(x) = x^3 - 4x + 2 und berechne die Steigung an der Stelle x = 2.",
            "musterloesung": "f'(x) = 3x^2 - 4. Setze x = 2 ein: f'(2) = 3(2)^2 - 4 = 12 - 4 = 8."
        }

def evaluate_handwritten_answer(client, question, solution, drawing_bytes):
    image = prepare_pil_image(drawing_bytes)
    prompt = (
        f"Aufgabenstellung: {question}\n"
        f"Musterlösung: {solution}\n\n"
        "Der Schüler hat seine Lösung mit dem Apple Pencil aufgeschrieben (siehe Bild).\n"
        "Analysiere den Rechenweg und das Endergebnis Schritt für Schritt.\n"
        "Falls ein Fehler gemacht wurde, markiere genau, in welcher Zeile/an welcher Stelle der Denk- oder Rechenfehler liegt, "
        "und erkläre direkt am Fehler, wie es richtig geht."
    )
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[image, prompt]
    )
    return response.text

def get_youtube_links(topic_text):
    keywords = ["Kurvendiskussion", "Vektorgeometrie", "Ableitung", "Integral", "Stochastik", "Ebenen", "Skalarprodukt"]
    found_topic = "Mathe Oberstufe"
    for kw in keywords:
        if kw.lower() in topic_text.lower():
            found_topic = kw
            break
            
    query_schmidt = f"Lehrer Schmidt {found_topic} Oberstufe".replace(" ", "+")
    query_mathematrix = f"Mathematrix {found_topic} J1".replace(" ", "+")
    
    return found_topic, f"https://www.youtube.com/results?search_query={query_schmidt}", f"https://www.youtube.com/results?search_query={query_mathematrix}"

# ---------------------------------------------------------
# State Management & Main App Flow
# ---------------------------------------------------------
if 'analysis' not in st.session_state:
    st.session_state.analysis = None
if 'quiz' not in st.session_state:
    st.session_state.quiz = None

st.title("GoodNotes Mathe-Tutor BW")
st.write("Lade deine Notizen hoch. Die KI analysiert den Inhalt, erklärt das Thema, schlägt passende Videos vor und prüft dich mit einer Abi-nahen Aufgabe.")

if not api_key:
    st.warning("⚠️ Bitte trage links in der Seitenleiste deinen **Google Gemini API Key** ein oder hinterlege ihn in den Streamlit Secrets.")
else:
    try:
        client = genai.Client(api_key=api_key)

        uploaded_file = st.file_uploader("GoodNotes Export (PDF / PNG / JPG) hochladen", type=["pdf", "png", "jpg", "jpeg"])

        if uploaded_file and not st.session_state.analysis:
            with st.spinner("GoodNotes-Mitschrift wird analysiert..."):
                try:
                    if uploaded_file.name.lower().endswith('.pdf'):
                        images = convert_from_bytes(uploaded_file.read())
                        img_byte_arr = io.BytesIO()
                        images[0].save(img_byte_arr, format='PNG')
                        image_bytes = img_byte_arr.getvalue()
                    else:
                        image_bytes = uploaded_file.read()
                    
                    st.session_state.analysis = analyze_goodnotes_page(client, image_bytes)
                    st.session_state.quiz = generate_exam_quiz(client, st.session_state.analysis)
                    st.rerun()
                except Exception as e:
                    st.error(f"Fehler bei der Analyse der Datei: {e}")

        if st.session_state.analysis:
            topic_name, link_schmidt, link_mathematrix = get_youtube_links(st.session_state.analysis)
            
            st.markdown('<div class="apple-card">', unsafe_allow_html=True)
            st.markdown('<span class="apple-badge">Themen-Erklärung</span>', unsafe_allow_html=True)
            st.markdown(st.session_state.analysis)
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="apple-card">', unsafe_allow_html=True)
            st.markdown('<span class="apple-badge">Empfohlene Lern-Videos</span>', unsafe_allow_html=True)
            st.write(f"Passende Videos zum Thema **{topic_name}**:")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"📺 **Lehrer Schmidt**\n\n[{topic_name} bei Lehrer Schmidt suchen]({link_schmidt})")
            with col2:
                st.markdown(f"📐 **Mathematrix**\n\n[{topic_name} bei Mathematrix suchen]({link_mathematrix})")
            st.markdown('</div>', unsafe_allow_html=True)
            
            if st.session_state.quiz:
                st.markdown('<div class="apple-card">', unsafe_allow_html=True)
                st.markdown('<span class="apple-badge">Prüfungsnahe Testaufgabe (J1 BW)</span>', unsafe_allow_html=True)
                st.write("### " + st.session_state.quiz["aufgabe"])
                st.write("Löse die Aufgabe direkt mit dem **Apple Pencil**:")
                
                canvas_result = st_canvas(
                    fill_color="rgba(255, 255, 255, 0)",
                    stroke_width=2,
                    stroke_color="#000000",
                    background_color="#FFFFFF",
                    height=320,
                    width=700,
                    drawing_mode="freedraw",
                    key="apple_pencil_canvas",
                )
                
                if st.button("Lösung prüfen lassen"):
                    if canvas_result.image_data is not None:
                        with st.spinner("Analysiere deine Handschrift und korrigiere den Rechenweg..."):
                            try:
                                img = Image.fromarray(canvas_result.image_data.astype('uint8'))
                                buffered = io.BytesIO()
                                img.save(buffered, format="PNG")
                                
                                feedback = evaluate_handwritten_answer(
                                    client,
                                    st.session_state.quiz["aufgabe"],
                                    st.session_state.quiz["musterloesung"],
                                    buffered.getvalue()
                                )
                                
                                st.markdown("### KI-Feedback & Fehleranalyse")
                                st.info(feedback)
                            except Exception as e:
                                st.error(f"Fehler bei der Auswertung der Lösung: {e}")
                    else:
                        st.warning("Bitte schreibe zuerst deine Lösung auf das Zeichenfeld.")
                st.markdown('</div>', unsafe_allow_html=True)

            if st.button("Neue Notiz analysieren"):
                st.session_state.analysis = None
                st.session_state.quiz = None
                st.rerun()

    except Exception as e:
        st.error(f"Verbindungsfehler zur Gemini API: {e}")