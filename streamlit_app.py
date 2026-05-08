import streamlit as st
import requests
import pandas as pd
import re
import time
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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
PLACEHOLDER_COVER = "https://via.placeholder.com/150x200?text=Cover+Not+Available"

@st.cache_data(show_spinner=False)
def load_data_csv(file_path):
    if not os.path.exists(file_path):
        st.error(f"File not found: {file_path}. Please make sure it's in the same folder.")
        return pd.DataFrame()
    try:
        return pd.read_csv(file_path, sep=None, engine='python', dtype=str)
    except Exception as e:
        st.error(f"Error loading {file_path}: {e}")
        return pd.DataFrame()


@st.cache_resource(show_spinner=False)
def build_book_catalogs(items_df):
    id_to_metadata = {}

    if items_df.empty:
        return id_to_metadata

    items_df.columns = items_df.columns.str.strip()
    
    id_col = 'i' if 'i' in items_df.columns else items_df.columns[0]

    for _, row in items_df.iterrows():
        item_id = str(row[id_col]).strip()
        
        title = row.get('Title', 'Unknown Title')
        if pd.isna(title) or str(title).lower() == 'nan': 
            title = 'Unknown Title'
        else:
            title = str(title).rstrip(' /')

        author = row.get('Author', 'Unknown Author')
        if pd.isna(author) or str(author).lower() == 'nan': 
            author = 'Unknown Author'
        else:
            author = str(author)
            author = re.sub(r'\s*\d.*$', '', author)
            author = author.replace(',', '')
            author = " ".join(author.split())
            author = author.rstrip(' (-.,)')

        raw_isbns = row.get('ISBN Valid')
        valid_isbns = []
        if not pd.isna(raw_isbns) and str(raw_isbns).lower() != 'nan':
            valid_isbns = [re.sub(r'\D', '', isbn) for isbn in str(raw_isbns).split(';') if re.sub(r'\D', '', isbn)]

        id_to_metadata[item_id] = {
            'title': title,
            'author': author,
            'isbns': valid_isbns
        }

    return id_to_metadata


def get_complete_book_info(item_id, id_to_metadata, http_session):
    item_id = str(item_id).strip()
    
    if item_id not in id_to_metadata:
        return None 

    meta = id_to_metadata[item_id]

    book_data = {
        "title": meta['title'],
        "author": meta['author'],
        "cover": PLACEHOLDER_COVER,
        "summary": "No summary available.",
        "item_id": item_id
    }

    # THE VIP PASS: Check if we have an API key in Streamlit Secrets
    api_key_param = ""
    if "GOOGLE_BOOKS_API_KEY" in st.secrets:
        api_key_param = f"&key={st.secrets['GOOGLE_BOOKS_API_KEY']}"

    # 1. TRY GOOGLE BOOKS FIRST (BY EXACT ISBN)
    for isbn in meta['isbns']:
        try:
            # Attach the API key to the request
            url = f"{GOOGLE_BOOKS_API}{isbn}{api_key_param}"
            response = http_session.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if "items" in data and len(data["items"]) > 0:
                    info = data["items"][0]["volumeInfo"]
                    
                    if book_data["cover"] == PLACEHOLDER_COVER:
                        g_cover = info.get("imageLinks", {}).get("thumbnail")
                        if g_cover:
                            book_data["cover"] = g_cover.replace("http:", "https:")

                    if book_data["summary"] == "No summary available.":
                        g_summary = info.get("description")
                        if g_summary:
                            book_data["summary"] = g_summary
                    
                    if book_data["cover"] != PLACEHOLDER_COVER and book_data["summary"] != "No summary available.":
                        break
        except:
            pass 

    # 2. THE NEW TRICK: TRY GOOGLE BOOKS BY TITLE + AUTHOR
    if book_data["summary"] == "No summary available." or book_data["cover"] == PLACEHOLDER_COVER:
        try:
            import urllib.parse
            safe_title = urllib.parse.quote_plus(book_data['title'])
            safe_author = urllib.parse.quote_plus(book_data['author'])
            
            fallback_url = f"https://www.googleapis.com/books/v1/volumes?q=intitle:{safe_title}+inauthor:{safe_author}{api_key_param}"
            response = http_session.get(fallback_url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if "items" in data and len(data["items"]) > 0:
                    info = data["items"][0]["volumeInfo"]
                    
                    if book_data["cover"] == PLACEHOLDER_COVER:
                        g_cover = info.get("imageLinks", {}).get("thumbnail")
                        if g_cover:
                            book_data["cover"] = g_cover.replace("http:", "https:")

                    if book_data["summary"] == "No summary available.":
                        g_summary = info.get("description")
                        if g_summary:
                            book_data["summary"] = g_summary
        except:
            pass
            
    # 3. SECOND CHANCE: OPEN LIBRARY (For Cover AND Summary)
    if book_data["cover"] == PLACEHOLDER_COVER or book_data["summary"] == "No summary available.":
        for isbn in meta['isbns']:
            if book_data["cover"] == PLACEHOLDER_COVER:
                open_library_cover = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false"
                try:
                    ol_response = http_session.get(open_library_cover, timeout=3, allow_redirects=True, stream=True)
                    if ol_response.status_code == 200:
                        book_data["cover"] = open_library_cover
                except:
                    pass

            if book_data["summary"] == "No summary available.":
                open_library_data = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&jscmd=details&format=json"
                try:
                    ol_desc_response = http_session.get(open_library_data, timeout=4)
                    if ol_desc_response.status_code == 200:
                        ol_json = ol_desc_response.json()
                        key = f"ISBN:{isbn}"
                        if key in ol_json and "details" in ol_json[key]:
                            details = ol_json[key]["details"]
                            if "description" in details:
                                desc = details["description"]
                                if isinstance(desc, dict) and "value" in desc:
                                    book_data["summary"] = desc["value"]
                                elif isinstance(desc, str):
                                    book_data["summary"] = desc
                except:
                    pass
            
            if book_data["cover"] != PLACEHOLDER_COVER and book_data["summary"] != "No summary available.":
                break

    return book_data


def get_user_zero_fallback_blocks(recommendations_df):
    if 'user_id' not in recommendations_df.columns or 'isbn' not in recommendations_df.columns:
        return []
    zero_recs = recommendations_df[recommendations_df['user_id'] == '0']
    if zero_recs.empty:
        return []
    
    raw_id_data = " ".join(zero_recs['isbn'].astype(str).tolist())
    return [block.strip() for block in raw_id_data.split() if block.strip()]


@st.cache_data(show_spinner=False)
def fetch_book_data_v2(item_id_blocks, _id_to_metadata, fallback_blocks=None): 
    books_results = []
    fallback_blocks = fallback_blocks or []
    fallback_index = 0
    seen_ids = set()
    
    # --- THE ULTIMATE CLOUD SESSION ---
    http_session = requests.Session()
    http_session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*"
    })
    
    # If the server drops us, automatically wait and try again 3 times!
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    http_session.mount('http://', adapter)
    http_session.mount('https://', adapter)
    # ----------------------------------

    for block in item_id_blocks:
        ids_for_this_book = [i.strip() for i in block.split(';') if i.strip()]
        details = None
        
        for item_id in ids_for_this_book:
            details = get_complete_book_info(item_id, _id_to_metadata, http_session)
            
            if details is not None:
                if details["item_id"] not in seen_ids:
                    break
                else:
                    details = None
                
        if details is None and fallback_blocks:
            while fallback_index < len(fallback_blocks):
                fallback_block = fallback_blocks[fallback_index]
                fallback_index += 1
                
                fallback_ids_for_this_book = [i.strip() for i in fallback_block.split(';') if i.strip()]
                for f_id in fallback_ids_for_this_book:
                    temp_fallback_details = get_complete_book_info(f_id, _id_to_metadata, http_session)
                    
                    if temp_fallback_details is not None:
                        if temp_fallback_details["item_id"] not in seen_ids:
                            details = temp_fallback_details
                            break
                
                if details is not None:
                    break

        if details is None:
            first_id = ids_for_this_book[0] if ids_for_this_book else "Unknown"
            details = {
                "title": f"Not Found (ID: {first_id})", 
                "author": "Unknown", 
                "cover": PLACEHOLDER_COVER, 
                "summary": "This book ID is missing from items.csv."
            }
            
        books_results.append(details)
        
        if "item_id" in details:
            seen_ids.add(details["item_id"])
            
        time.sleep(0.3) 
        
    return books_results
# --- HELPER: UI RENDERING FOR BOOK CARD ---
def render_book_card(book, rank):
    
    t_len = len(book["title"])
    if t_len < 35: fs = "16px"
    elif t_len < 60: fs = "14px"
    elif t_len < 85: fs = "12px"
    else: fs = "11px"
    
    st.markdown(f'<div class="book-title-box" style="font-size: {fs};">{book["title"]}</div>', unsafe_allow_html=True)
    
    badge_html = f'<div style="position: absolute; top: -15px; left: -15px; background-color: #dedbd0; color: {BURGUNDY}; width: 35px; height: 35px; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-weight: 900; font-size: 18px; box-shadow: 0 4px 8px rgba(0,0,0,0.3); z-index: 10; border: 2px solid white;">{rank}</div>'

    if book['cover'] == PLACEHOLDER_COVER:
        html_cover = f"""
<div style="height: 220px; width: 100%; background-color: #9e1041; border-radius: 4px 12px 12px 4px; box-shadow: inset 4px 0 10px rgba(0,0,0,0.2), 0 4px 8px rgba(0,0,0,0.15); display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 15px; margin-bottom: 10px; text-align: center; position: relative; border-left: 5px solid #7a0c32;">
{badge_html}
<div style="color: white; font-weight: bold; font-size: 14px; margin-bottom: 10px; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden;">{book['title']}</div>
<div style="color: #e0e0e0; font-size: 12px; font-style: italic;">{book['author']}</div>
<div style="position: absolute; bottom: 10px; right: 10px; opacity: 0.3;">
<svg width="24" height="24" viewBox="0 0 24 24" fill="white"><path d="M4 19v-14c0-1.1.9-2 2-2h12c1.1 0 2 .9 2 2v14l-4-2-4 2-4-2-4 2zm2-14v11.5l2-1 2 1 2-1 2 1 2-1 2 1v-11.5h-12z"/></svg>
</div>
</div>
"""
        st.markdown(html_cover, unsafe_allow_html=True)
    else:
        html_cover = f"""
<div style="height: 220px; position: relative; display: flex; justify-content: center; align-items: center; margin-bottom: 10px;">
{badge_html}
<img src="{book['cover']}" style="max-height: 100%; max-width: 100%; object-fit: contain; box-shadow: 0 4px 8px rgba(0,0,0,0.15);">
</div>
"""
        st.markdown(html_cover, unsafe_allow_html=True)
        
    st.markdown(f'<div class="book-author-box"> {book.get("author", "Unknown Author")}</div>', unsafe_allow_html=True)
    with st.expander("Book summary"):
        st.write(book['summary'])

# --- HELPER: NETFLIX ROW RENDERER ---
def display_netflix_row(title, books, row_key):
    if not books:
        return
    
    st.markdown(f"""
        <div style="background-color: rgba(158, 16, 65, 0.9); padding: 10px 20px; border-radius: 4px; margin-top: 30px; margin-bottom: 20px; border-left: 6px solid white;">
            <h3 style='color: white; margin: 0;'>{title}</h3>
        </div>
    """, unsafe_allow_html=True)
    
    if f'page_{row_key}' not in st.session_state:
        st.session_state[f'page_{row_key}'] = 0
        
    page = st.session_state[f'page_{row_key}']
    
    start_idx = page * 5
    end_idx = start_idx + 5
    visible_books = books[start_idx:end_idx]
    
    cols = st.columns([1, 1, 1, 1, 1, 0.4])
    
    for col_idx, book in enumerate(visible_books):
        absolute_rank = start_idx + col_idx + 1
        with cols[col_idx]:
            render_book_card(book, absolute_rank)
            
    with cols[5]:
        st.markdown("<div style='height: 140px;'></div>", unsafe_allow_html=True) 
        if page == 0 and len(books) > 5:
            if st.button("➔", key=f"next_{row_key}", use_container_width=True):
                st.session_state[f'page_{row_key}'] = 1
                st.rerun()
        elif page == 1:
            if st.button("⬅", key=f"prev_{row_key}", use_container_width=True):
                st.session_state[f'page_{row_key}'] = 0
                st.rerun()

# --- 4. PAGE ROUTING ---

if st.session_state.view == 'landing':
    apply_full_page_style(LOGIN_BG_URL)
    st.markdown('<h1 class="hero-title">WELCOME</h1>', unsafe_allow_html=True)
    
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
                <h3 style="margin-top:0; color:white;">Smart Recommendations</h3>
                <p>Access the library's smart recommendation system.</p>
            </div>
        """, unsafe_allow_html=True)
        if st.button("click here"):
            st.session_state.view = 'login'
            st.rerun()

elif st.session_state.view == 'login':
    apply_full_page_style(LOGIN_BG_URL)
    st.markdown('<h1 class="hero-title">Welcome</h1>', unsafe_allow_html=True)

    _, col = st.columns([1.5, 1])
    with col:
        st.markdown("""
            <div class="styled-box">
                <h3 style="margin-top:0; color:white;">Identification</h3>
                <p>Please enter your User ID to access your recommendations. If you are a new user, please type "new" to discover what most people liked.</p>
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
        
        /* THE CSS FIX for the Top Margin on Titles */
        .book-title-box {
            background-color: rgba(158, 16, 65, 1) !important; color: white !important;
            padding: 15px 10px 5px 10px; border: 1px solid #e0e0e0; border-radius: 6px; text-align: center;
            font-weight: bold; margin-bottom: 10px; 
            height: 75px; display: flex; align-items: flex-start; justify-content: center;
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
        with st.spinner("Loading library catalogs..."):
            recs_df = load_data_csv("recommendations_2.csv")
            items_df = load_data_csv("items.csv") 
            
            if items_df.empty:
                st.error("Failed to load inventory catalog (items.csv). Please check the file.")
                st.stop()
            
            if recs_df.empty:
                st.warning("No recommendation data loaded.")
                st.stop()
            
            id_to_metadata = build_book_catalogs(items_df)
        
        uid_entered = str(st.session_state.user_id).strip()
        
        user_recs = recs_df[recs_df['user_id'] == uid_entered]
        new_recs = recs_df[recs_df['user_id'] == 'new']
        fallback_blocks = get_user_zero_fallback_blocks(recs_df)

        def extract_top_10_blocks(df_subset):
            if df_subset.empty: return []
            raw_id_data = " ".join(df_subset['isbn'].astype(str).tolist())
            all_blocks = [block.strip() for block in raw_id_data.split() if block.strip()]
            unique_blocks = []
            seen = set()
            for b in all_blocks:
                if b not in seen:
                    seen.add(b)
                    unique_blocks.append(b)
            return unique_blocks[:10]

        user_blocks = extract_top_10_blocks(user_recs)
        new_blocks = extract_top_10_blocks(new_recs)
        
        if not user_blocks and uid_entered != 'new':
            st.warning("Your user ID doesn't exist. Please type 'new' to see our general recommendations.")
        else:
            with st.spinner("Loading your books from the library..."):
                books_user = fetch_book_data_v2(user_blocks, id_to_metadata, fallback_blocks=fallback_blocks) if user_blocks else []
                books_new = fetch_book_data_v2(new_blocks, id_to_metadata, fallback_blocks=fallback_blocks) if new_blocks else []
                
                # --- RENDER ROW 1 (Personal Recommendations) ---
                if books_user:
                    row_title = "Trending Picks" if uid_entered == 'new' else f"Recommended for You"
                    display_netflix_row(row_title, books_user, "user_row")
                
                # --- RENDER ROW 2 (Top 10 / 'new' user recommendations) ---
                if books_new and uid_entered != 'new':
                    display_netflix_row("Top 10 Library Recommendations", books_new, "new_row")