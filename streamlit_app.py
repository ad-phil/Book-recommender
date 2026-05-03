import streamlit as st
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import re
import time

# --- 1. CONFIG & STATE ---
st.set_page_config(page_title="BCU Lausanne", layout="wide", initial_sidebar_state="collapsed")

if 'view' not in st.session_state:
    st.session_state.view = 'landing'

# --- THEME COLORS & URLS ---
BURGUNDY = "#9e1041"
LOGO_URL = "https://www.bcu-lausanne.ch/wp-content/themes/bcu/assets/images/logo-bcul.svg"
LOGIN_BG_URL = "https://images.unsplash.com/photo-1529154166925-574a0236a4f4?q=80&w=1548&auto=format&fit=crop"

# --- 2. CSS STYLING FUNCTIONS ---

def apply_full_page_style(background_url):
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');

        .stApp {{
            background-image: linear-gradient(rgba(0, 0, 0, 0.3), rgba(0, 0, 0, 0.3)), url("{background_url}") !important;
            background-size: cover !important;
            background-position: center !important;
            background-attachment: fixed !important;
        }}

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
            padding: 15px 60px; 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            margin-top: 100px; 
            color: white; 
        }}
        
        .nav-brand {{
            font-size: 20px; font-weight: 700; letter-spacing: 1px;
        }}

        .nav-links {{
            display: flex; gap: 50px; font-weight: 500; font-size: 15px;
        }}

        .hero-title {{
            font-size: 80px; font-weight: 700; color: white !important; 
            margin: 120px 0 0 60px; text-shadow: 2px 2px 15px rgba(0,0,0,0.6);
        }}

        .styled-box {{
            background-color: rgba(158, 16, 65, 0.9) !important; 
            padding: 40px; border-radius: 4px; color: white !important; 
            margin-top: 50px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            border-left: 6px solid white;
        }}

        div[data-baseweb="input"] {{
            background-color: white !important; border-radius: 0px !important;
        }}
        
        div.stButton > button {{
            background-color: {BURGUNDY} !important; color: white !important;
            border: 2px solid white !important; border-radius: 0px !important;
            padding: 12px 30px !important; font-weight: bold; width: 100%;
        }}
        div.stButton > button:hover {{
            background-color: white !important; color: {BURGUNDY} !important;
        }}

        label[data-testid="stWidgetLabel"] p {{ color: white !important; }}

        div[data-baseweb="input"] input {{
            color: black !important; -webkit-text-fill-color: black !important;
        }}

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
            <div class="nav-brand">BCU LAUSANNE</div>
            <div class="nav-links">
                <span>Sites ⌵</span> <span>Services ⌵</span> <span>Online offers ⌵</span> 
                <span>Collections</span> <span>About ⌵</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

# --- 3. LOGIC & API ---

GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes?q=isbn:"

def get_book_details(isbn):
    # 1. CLEAN THE ISBN: Split off any hidden decimals, then remove weird characters
    clean_isbn = str(isbn).split('.')[0]
    clean_isbn = re.sub(r'\D', '', clean_isbn)
    
    if not clean_isbn:
        return {"title": "Invalid ISBN", "author": "Unknown", "cover": "https://via.placeholder.com/150x200", "summary": ""}

    try:
        response = requests.get(f"{GOOGLE_BOOKS_API}{clean_isbn}", timeout=5)
        
        # 2. Check if Google is blocking us for going too fast
        if response.status_code == 429:
            return {"title": "API Blocked", "author": "Too Many Requests", "cover": "https://via.placeholder.com/150x200", "summary": "Google rate-limited the connection."}
            
        if response.status_code == 200:
            data = response.json()
            if "items" in data and len(data["items"]) > 0:
                info = data["items"][0]["volumeInfo"]
                return {
                    "title": info.get("title", "Unknown Title"),
                    "author": ", ".join(info.get("authors", ["Unknown Author"])),
                    "cover": info.get("imageLinks", {}).get("thumbnail", "https://via.placeholder.com/150x200"),
                    "summary": info.get("description", "No summary available.")
                }
    except:
        pass
    
    # If the book truly isn't in Google's database, return None and allow fallback logic to take over
    return None


def parse_isbn_list(isbn_string, unique=False):
    if not isinstance(isbn_string, str):
        return []
    items = [item for item in isbn_string.split() if item.strip()]
    if not unique:
        return items
    seen = set()
    unique_items = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique_items.append(item)
    return unique_items


@st.cache_data
def fetch_book_data_v2(isbn_list, fallback_isbns=None): 
    # THE FIX: We stop using ThreadPoolExecutor. 
    # We ask for books one by one and pause for 0.2 seconds to keep Google happy.
    books = []
    fallback_isbns = fallback_isbns or []
    used_fallbacks = set()

    for isbn in isbn_list:
        details = get_book_details(isbn)
        if details is None and fallback_isbns:
            for fallback_isbn in fallback_isbns:
                if fallback_isbn in used_fallbacks:
                    continue
                fallback_details = get_book_details(fallback_isbn)
                if fallback_details is not None:
                    details = fallback_details
                    used_fallbacks.add(fallback_isbn)
                    break
        if details is None:
            clean_isbn = str(isbn).split('.')[0]
            clean_isbn = re.sub(r'\D', '', clean_isbn)
            details = {"title": f"Not Found ({clean_isbn})", "author": "Unknown", "cover": "https://via.placeholder.com/150x200", "summary": "This book is not in the Google Books database."}
        books.append(details)
        time.sleep(0.2)
    return books


def get_user_zero_fallback_isbns(df):
    if 'user_id' not in df.columns or 'isbn' not in df.columns:
        return []
    zero_recs = df[df['user_id'] == '0']
    if zero_recs.empty:
        return []
    raw_isbn_data = " ".join(zero_recs['isbn'].astype(str).tolist())
    return parse_isbn_list(raw_isbn_data, unique=True)


# --- NEW DATA LOADING FUNCTION ---
@st.cache_data
def load_recommendations(file_path):
    try:
        # THE FIX: Added dtype=str so Pandas treats everything as pure text
        df = pd.read_csv(file_path, sep=None, engine='python', dtype=str)
        
        df.columns = df.columns.str.strip().str.lower()
        
        if 'user_id' in df.columns:
            df['user_id'] = df['user_id'].str.strip()
        if 'isbn' in df.columns:
            # Extra safety: Chop off the ".0" if Python accidentally added it
            df['isbn'] = df['isbn'].str.replace(r'\.0$', '', regex=True).str.strip()
            
        return df
        
    except FileNotFoundError:
        st.error(f"File not found: {file_path}. Please make sure it's in the same folder as this script.")
        return pd.DataFrame()

# --- 4. PAGE ROUTING ---

# PAGE A: WELCOME
if st.session_state.view == 'landing':
    apply_full_page_style(LOGIN_BG_URL)
    st.markdown('<h1 class="hero-title">BCU Lausanne</h1>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([1.5, 1])
    
    with col1:
        st.markdown("""
            <style>
            .acces-directs-box {
                background-color: #dedbd0; padding: 30px 40px; border-radius: 4px;
                width: 100%; max-width: 450px; margin-top: 20px; margin-left: 60px; 
                font-family: 'Inter', sans-serif;
            }
            .acces-directs-title { color: #9e1041; font-size: 32px; font-weight: 700; margin-top: 0; margin-bottom: 20px; }
            .acces-directs-list { display: flex; flex-direction: column; }
            .acces-directs-item {
                display: flex; justify-content: space-between; align-items: center;
                padding: 15px 0; border-bottom: 1px solid rgba(158, 16, 65, 0.2); color: #9e1041; font-size: 18px;
            }
            .acces-directs-item:last-child { border-bottom: none; }
            .arrow-icon { width: 24px; height: 24px; fill: none; stroke: #9e1041; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }
            </style>

            <div class="acces-directs-box">
                <h2 class="acces-directs-title">Quick link</h2>
                <div class="acces-directs-list">
                    <div class="acces-directs-item"><span>Register to BCUL</span><svg class="arrow-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><polyline points="10 8 14 12 10 16"></polyline></svg></div>
                    <div class="acces-directs-item"><span>Q&A service</span><svg class="arrow-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><polyline points="10 8 14 12 10 16"></polyline></svg></div>
                    <div class="acces-directs-item"><span>Schedule </span><svg class="arrow-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><polyline points="10 8 14 12 10 16"></polyline></svg></div>
                    <div class="acces-directs-item"><span>Online book reservation</span><svg class="arrow-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><polyline points="10 8 14 12 10 16"></polyline></svg></div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
            <div class="styled-box">
                <h3 style="margin-top:0; color:white;">Welcome</h3>
                <p>Access the library's smart recommendation system.</p>
            </div>
        """, unsafe_allow_html=True)
        if st.button("ACCESS MY RECOMMENDATIONS"):
            st.session_state.view = 'login'
            st.rerun()

# PAGE B: LOGIN
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

# PAGE C: RESULTS GRID
else:
    apply_full_page_style(LOGIN_BG_URL)

    st.markdown("""
        <style>
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #FFFFFF !important; opacity: 1 !important; backdrop-filter: none !important;
            padding: 3rem !important; border-radius: 12px !important; box-shadow: 0 15px 45px rgba(0,0,0,0.4) !important;
            border: none !important; margin-top: 20px !important; margin-bottom: 50px !important;
            margin-left: 5% !important; margin-right: 5% !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] h1, 
        div[data-testid="stVerticalBlockBorderWrapper"] p,
        div[data-testid="stVerticalBlockBorderWrapper"] span,
        div[data-testid="stVerticalBlockBorderWrapper"] label { color: #1a1a1a !important; }

        .stExpander { background-color: #ffffff !important; border: 1px solid #cccccc !important; }
        
        .book-title-box {
            background-color: rgba(158, 16, 65, 1) !important; color: white !important;
            padding: 10px; border: 1px solid #e0e0e0; border-radius: 6px; text-align: center;
            font-weight: bold; font-size: 16px; margin-bottom: 10px; 
            height: 70px; display: flex; align-items: center; justify-content: center;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05); overflow: hidden;
        }
        
        .book-author-box {
            background-color: rgba(255, 255, 255, 1) !important; color: #555555 !important;
            padding: 8px; border: 1px solid #e0e0e0; border-radius: 6px; text-align: center;
            font-weight: bold; font-size: 14px; margin-top: 6px; margin-bottom: 6px;
            height: 55px; display: flex; align-items: center; justify-content: center;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05); overflow: hidden;
        }
        </style>
    """, unsafe_allow_html=True)

    if st.button("← Back to Welcome Page"):
        st.session_state.view = 'landing'
        st.rerun()

    with st.container(border=False):
        st.markdown(f"""
            <div style="
                background-color: #dedbd0; padding: 25px; border-radius: 4px;
                margin-bottom: 20px; font-family: 'Inter', sans-serif;
            ">
                <h1 style="margin-top:0; color:#9e1041;"> Recommendations for ID: {st.session_state.user_id}</h1>
                <p style="color: #555555; font-size:18px; margin-bottom:0;">Based on your library activity, here are your top picks:</p>
            </div>
        """, unsafe_allow_html=True)
        
        # --- DYNAMIC DATA LOADING ---
        # Change 'recommendations.csv' to the exact name of your CSV file!
        df = load_recommendations("recommendations.csv")
        
        if df.empty:
            st.warning("No data loaded. Check your CSV file.")
        else:
            if 'user_id' not in df.columns or 'isbn' not in df.columns:
                st.error("Your CSV must contain 'user_id' and 'isbn' columns.")
            else:
                uid_entered = str(st.session_state.user_id).strip()
                # Find the user's row(s)
                user_recs = df[df['user_id'] == uid_entered]
                
                if not user_recs.empty:
                    with st.spinner("Loading your books from the library..."):
                        
                        # THE FIX: Combine all ISBN data for this user into one string, 
                        # then .split() chops it into a clean list wherever there is a space.
                        raw_isbn_data = " ".join(user_recs['isbn'].astype(str).tolist())
                        isbn_list = raw_isbn_data.split()
                        
                        # Keep only the first 10 books so we don't overload the page
                        isbn_list = isbn_list[:10]
                        
                        fallback_isbns = get_user_zero_fallback_isbns(df)
                        books = fetch_book_data_v2(isbn_list, fallback_isbns=fallback_isbns) 
                    
                        for row_idx in range(0, len(books), 5):
                            row_books = books[row_idx:row_idx+5]
                            cols = st.columns(5) 
                            
                            for col_idx, book in enumerate(row_books):
                                with cols[col_idx]:
                                    st.markdown(f'<div class="book-title-box">{book["title"]}</div>', unsafe_allow_html=True)
                                    
                                    st.markdown(f"""
                                        <div style="height: 220px; display: flex; justify-content: center; align-items: center; margin-bottom: 10px;">
                                            <img src="{book['cover']}" style="max-height: 100%; max-width: 100%; object-fit: contain; box-shadow: 0 4px 8px rgba(0,0,0,0.15);">
                                        </div>
                                    """, unsafe_allow_html=True)
                                    
                                    st.markdown(f'<div class="book-author-box"> {book.get("author", "Unknown Author")}</div>', unsafe_allow_html=True)
                                    
                                    with st.expander("Book summary"):
                                        st.write(book['summary'])
                else:
                    st.warning(f"Your user ID don't exist, if you are a new user please type 0 to see our general recommendations")