import streamlit as st
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

# --- 1. CONFIG & STATE ---
st.set_page_config(page_title="BCU Lausanne", layout="wide", initial_sidebar_state="collapsed")

if 'view' not in st.session_state:
    st.session_state.view = 'landing'

# --- THEME COLORS & URLS ---
BURGUNDY = "#9e1041"
LOGO_URL = "https://www.bcu-lausanne.ch/wp-content/themes/bcu/assets/images/logo-bcul.svg"
# Replace this URL with your manual background image URL
LOGIN_BG_URL = "https://images.unsplash.com/photo-1529154166925-574a0236a4f4?q=80&w=1548&auto=format&fit=crop"

# --- 2. CSS STYLING FUNCTIONS ---

def apply_full_page_style(background_url):
    """Applies the BCU header, nav, and background image."""
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');

        .stApp {{
            background-image: linear-gradient(rgba(0, 0, 0, 0.3), rgba(0, 0, 0, 0.3)), url("{background_url}") !important;
            background-size: cover !important;
            background-position: center !important;
            background-attachment: fixed !important;
        }}

        /* Header & Nav */
        header, [data-testid="stHeader"] {{ background: rgba(0,0,0,0) !important; }}
        
        .utility-bar {{
            display: flex; justify-content: flex-end; padding: 10px 50px;
            background-color: white !important; color: {BURGUNDY}; font-size: 13px; gap: 20px;
            position: fixed; top: 0; left: 0; right: 0; z-index: 1000;
        }}

        .logo-container {{
            position: fixed; top: 0px; left: 60px; z-index: 1001; width: 230px;
        }}

        .nav-bar {{
            background-color: {BURGUNDY} !important; 
            padding: 15px 60px 15px 20px;
            display: flex; justify-content: flex-end;
            gap: 50px; margin-top: 100px; 
            color: white; font-weight: 500; font-size: 15px;
        }}

        .hero-title {{
            font-size: 80px; font-weight: 700; color: white !important; 
            margin: 120px 0 0 60px; text-shadow: 2px 2px 15px rgba(0,0,0,0.6);
        }}

        /* The Burgundy Login/Info Box */
        .styled-box {{
            background-color: rgba(158, 16, 65, 0.9) !important; 
            padding: 40px;
            border-radius: 4px; 
            color: white !important; 
            margin-top: 50px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            border-left: 6px solid white;
        }}

        /* Style the Streamlit Input specifically for the burgundy box */
        div[data-baseweb="input"] {{
            background-color: white !important;
            border-radius: 0px !important;
        }}
        
        /* Button Styling */
        div.stButton > button {{
            background-color: {BURGUNDY} !important; color: white !important;
            border: 2px solid white !important; border-radius: 0px !important;
            padding: 12px 30px !important; font-weight: bold; width: 100%;
        }}
        div.stButton > button:hover {{
            background-color: white !important; color: {BURGUNDY} !important;
        }}

        /* Target the label text */
        label[data-testid="stWidgetLabel"] p {{
            color: white !important;
        }}

        /* Target the input text and placeholder */
        div[data-baseweb="input"] input {{
            color: black !important;
            -webkit-text-fill-color: black !important;
        }}

        /* Adjust the box background so white text is visible */
        div[data-baseweb="input"] {{
            background-color: rgba(255, 255, 255, 0.1) !important;
            border: 1px solid rgba(255, 255, 255, 0.5) !important;
            border-radius: 4px !important;
        }}
        </style>

        <div class="utility-bar">
            <span>Payment</span> | <span>My Account</span> | <span>Contact</span> | <b>en</b>
        </div>
        <div class="logo-container">
            <img src="{LOGO_URL}" style="width:100%; height:auto;">
        </div>
        <div class="nav-bar">
            <span>Sites ⌵</span> <span>Services ⌵</span> <span>Online offers ⌵</span> 
            <span>Collections</span> <span>About ⌵</span>
        </div>
    """, unsafe_allow_html=True)

# --- 3. LOGIC & API ---

GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes?q=isbn:"

def get_book_details(isbn):
    try:
        response = requests.get(f"{GOOGLE_BOOKS_API}{isbn}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if "items" in data:
                info = data["items"][0]["volumeInfo"]
                return {
                    "title": info.get("title", "Unknown"),
                    "cover": info.get("imageLinks", {}).get("thumbnail", "https://via.placeholder.com/150x200"),
                    "summary": info.get("description", "No summary available.")
                }
    except: pass
    return {"title": "Book not found", "cover": "https://via.placeholder.com/150x200", "summary": ""}

@st.cache_data
def fetch_all_book_data(isbn_list):
    with ThreadPoolExecutor(max_workers=10) as executor:
        return list(executor.map(get_book_details, isbn_list))

# --- 4. PAGE ROUTING ---

# PAGE A: WELCOME
if st.session_state.view == 'landing':
    apply_full_page_style(LOGIN_BG_URL)
    st.markdown('<h1 class="hero-title">BCU Lausanne</h1>', unsafe_allow_html=True)
    
    _, col = st.columns([1.5, 1])
    with col:
        st.markdown("""
            <div class="styled-box">
                <h3 style="margin-top:0; color:white;">Welcome</h3>
                <p>Access the library's smart recommendation system.</p>
            </div>
        """, unsafe_allow_html=True)
        if st.button("ACCESS MY RECOMMENDATIONS"):
            st.session_state.view = 'login'
            st.rerun()

# PAGE B: THE BEAUTIFUL LOGIN (The one you asked for)
elif st.session_state.view == 'login':
    apply_full_page_style(LOGIN_BG_URL)
    st.markdown('<h1 class="hero-title">BCU Lausanne</h1>', unsafe_allow_html=True)
    
    _, col = st.columns([1.5, 1])
    with col:
        st.markdown("""
            <div class="styled-box">
                <h3 style="margin-top:0; color:white;">Identification</h3>
                <p>Please enter your User ID to access your recommendations.</p>
            </div>
        """, unsafe_allow_html=True)
        user_id = st.text_input("User ID", key="user_id_input")
        st.markdown('</div>', unsafe_allow_html=True)
        
        if user_id:
            
                st.session_state.user_id = user_id
                st.session_state.view = 'recs'
                st.rerun()
        
        if st.button("← Back"):
            st.session_state.view = 'landing'
            st.rerun()

# PAGE C: THE RESULTS GRID

else:
    # 1. Apply your initial background and nav bar (logo/wallpaper/burgundy menu)
    apply_full_page_style(LOGIN_BG_URL)

    # 2. THE CSS: This is where you put the new code to make the box solid white
    st.markdown("""
        <style>
        /* This targets the container to make it a SOLID white card */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #FFFFFF !important; /* Solid White */
            opacity: 1 !important;                 /* No transparency */
            backdrop-filter: none !important;      /* No blur effect */
            
            padding: 3rem !important;
            border-radius: 12px !important;
            box-shadow: 0 15px 45px rgba(0,0,0,0.4) !important;
            border: none !important;
            
            /* Positioning to see the wallpaper around the edges */
            margin-top: 20px !important;
            margin-bottom: 50px !important;
            margin-left: 5% !important;
            margin-right: 5% !important;
        }

        /* Ensure all text inside the white box is dark/black */
        div[data-testid="stVerticalBlockBorderWrapper"] h1, 
        div[data-testid="stVerticalBlockBorderWrapper"] p,
        div[data-testid="stVerticalBlockBorderWrapper"] span,
        div[data-testid="stVerticalBlockBorderWrapper"] label,
        div[data-testid="stVerticalBlockBorderWrapper"] div {
            color: #1a1a1a !important;
        }

        /* Styling for the book synopsis expanders */
        .stExpander {
            background-color: #ffffff !important;
            border: 1px solid #eeeeee !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # 3. THE UI CONTENT
    if st.button("← Back to Welcome Page"):
        st.session_state.view = 'landing'
        st.rerun()

    # This 'with' block ensures everything below is inside the solid white box
    with st.container(border=True):
        st.markdown(f'<h1 style="margin-top:0;">📚 Recommendations for ID: {st.session_state.user_id}</h1>', unsafe_allow_html=True)
        st.write("Based on your library activity, here are your top 10 picks:")
        
        # --- DATA & GRID LOGIC ---
        # (Assuming your dataframe 'df' and 'fetch_all_book_data' are defined above)
        data = {"user_id": [101]*10, "isbn": ["9780141439518", "9780451524935", "9780307474278", "9780062315007", "9780743273565", "9780316769488", "9780446310789", "9780618260300", "9780553213119", "9780142437230"]}
        df = pd.DataFrame(data)
        
        try:
            uid = int(st.session_state.user_id)
            user_recs = df[df['user_id'] == uid].head(10)
            
            if not user_recs.empty:
                with st.spinner("Loading your books..."):
                    books = fetch_all_book_data(user_recs['isbn'].tolist())
                
                cols = st.columns(5)
                for i, book in enumerate(books):
                    with cols[i % 5]:
                        st.image(book['cover'], use_container_width=True)
                        with st.expander("📖 Synopsis"):
                            st.write(f"**{book['title']}**")
                            st.write(book['summary'])
            else:
                st.warning("No recommendations found.")
        except ValueError:
            st.error("Invalid ID.")