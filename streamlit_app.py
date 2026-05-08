import streamlit as st
import requests
import pandas as pd
import re
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor
import threading

# --- 1. CONFIG & STATE ---
st.set_page_config(page_title="BCU Lausanne", layout="wide", initial_sidebar_state="collapsed")

if 'view' not in st.session_state:
    st.session_state.view = 'landing'

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
            background-size: cover !important; background-position: center !important; background-attachment: fixed !important;
        }}
        header, [data-testid="stHeader"] {{ background: rgba(0,0,0,0) !important; }}
        .utility-bar {{
            display: flex; justify-content: flex-end; padding: 10px 50px;
            background-color: white !important; color: {BURGUNDY}; font-size: 13px; gap: 20px;
            position: fixed; top: 0; left: 0; right: 0; z-index: 1000;
        }}
        .logo-container {{ position: fixed; top: 0px; left: 60px; z-index: 1001; width: 230px; }}
        .nav-bar {{
            background-color: {BURGUNDY} !important; padding: 15px 60px; display: flex; 
            justify-content: space-between; align-items: center; margin-top: 100px; color: white; 
        }}
        .nav-brand {{ font-size: 20px; font-weight: 700; letter-spacing: 1px; }}
        .nav-links {{ display: flex; gap: 50px; font-weight: 500; font-size: 15px; }}
        .hero-title {{
            font-size: 80px; font-weight: 700; color: white !important; 
            margin: 120px 0 0 60px; text-shadow: 2px 2px 15px rgba(0,0,0,0.6);
        }}
        .styled-box {{
            background-color: rgba(158, 16, 65, 0.9) !important; padding: 40px; border-radius: 4px; 
            color: white !important; margin-top: 50px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); border-left: 6px solid white;
        }}
        div[data-baseweb="input"] {{ background-color: white !important; border-radius: 0px !important; }}
        div.stButton > button {{
            background-color: {BURGUNDY} !important; color: white !important; border: 2px solid white !important; 
            border-radius: 0px !important; padding: 12px 30px !important; font-weight: bold; width: 100%;
        }}
        div.stButton > button:hover {{ background-color: white !important; color: {BURGUNDY} !important; }}
        label[data-testid="stWidgetLabel"] p {{ color: white !important; }}
        div[data-baseweb="input"] input {{ color: black !important; -webkit-text-fill-color: black !important; }}
        div[data-baseweb="input"] {{
            background-color: rgba(255, 255, 255, 0.1) !important; border: 1px solid rgba(255, 255, 255, 0.5) !important; border-radius: 4px !important;
        }}
        </style>
        <div class="utility-bar"><span>Payment</span> | <span>My Account</span> | <span>Contact</span> | <b>en</b></div>
        <div class="logo-container"><img src="{LOGO_URL}" style="width:100%; height:auto;"></div>
        <div class="nav-bar">
            <div class="nav-brand">BCU LAUSANNE</div>
            <div class="nav-links"><span>Sites ⌵</span> <span>Services ⌵</span> <span>Online offers ⌵</span> <span>Collections</span> <span>About ⌵</span></div>
        </div>
    """, unsafe_allow_html=True)

# --- 3. LOGIC & API ---
GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes?q=isbn:"
PLACEHOLDER_COVER = "https://via.placeholder.com/150x200?text=Cover+Not+Available"

@st.cache_data(show_spinner=False)
def load_data_csv(file_path):
    if not os.path.exists(file_path):
        return pd.DataFrame()
    return pd.read_csv(file_path, sep=None, engine='python', dtype=str)

def build_targeted_catalog(items_df, required_ids):
    id_to_metadata = {}
    if items_df.empty or not required_ids: return id_to_metadata

    items_df.columns = items_df.columns.str.strip()
    id_col = 'i' if 'i' in items_df.columns else items_df.columns[0]

    filtered_df = items_df[items_df[id_col].astype(str).str.strip().isin(required_ids)]

    for _, row in filtered_df.iterrows():
        item_id = str(row[id_col]).strip()
        title = row.get('Title', 'Unknown Title')
        title = 'Unknown Title' if pd.isna(title) or str(title).lower() == 'nan' else str(title).rstrip(' /')
        author = row.get('Author', 'Unknown Author')
        if pd.isna(author) or str(author).lower() == 'nan': 
            author = 'Unknown Author'
        else:
            author = str(author)
            author = re.sub(r'\s*\d.*$', '', author).replace(',', '')
            author = " ".join(author.split()).rstrip(' (-.,)')

        raw_isbns = row.get('ISBN Valid')
        valid_isbns = [re.sub(r'\D', '', isbn) for isbn in str(raw_isbns).split(';') if re.sub(r'\D', '', isbn)] if not pd.isna(raw_isbns) else []

        id_to_metadata[item_id] = {'title': title, 'author': author, 'isbns': valid_isbns}
    return id_to_metadata

def get_complete_book_info(item_id, id_to_metadata, http_session):
    item_id = str(item_id).strip()
    if item_id not in id_to_metadata: return None 
    meta = id_to_metadata[item_id]

    book_data = {"title": meta['title'], "author": meta['author'], "cover": PLACEHOLDER_COVER, "summary": "No summary available.", "item_id": item_id}
    api_key_param = f"&key={st.secrets['GOOGLE_BOOKS_API_KEY']}" if "GOOGLE_BOOKS_API_KEY" in st.secrets else ""
    country_param = "&country=CH"

    # Google Exact
    for isbn in meta['isbns']:
        try:
            resp = http_session.get(f"{GOOGLE_BOOKS_API}{isbn}{api_key_param}{country_param}", timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                if "items" in data and len(data["items"]) > 0:
                    info = data["items"][0]["volumeInfo"]
                    g_cover = info.get("imageLinks", {}).get("thumbnail")
                    if g_cover: book_data["cover"] = g_cover.replace("http:", "https:")
                    g_summary = info.get("description")
                    if g_summary: book_data["summary"] = g_summary
                    if book_data["cover"] != PLACEHOLDER_COVER and book_data["summary"] != "No summary available.": break
        except: pass 

    # Google Fallback
    if book_data["summary"] == "No summary available." or book_data["cover"] == PLACEHOLDER_COVER:
        try:
            import urllib.parse
            safe_title = urllib.parse.quote_plus(book_data['title'])
            safe_author = urllib.parse.quote_plus(book_data['author'])
            resp = http_session.get(f"https://www.googleapis.com/books/v1/volumes?q=intitle:{safe_title}+inauthor:{safe_author}{api_key_param}{country_param}", timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                if "items" in data and len(data["items"]) > 0:
                    info = data["items"][0]["volumeInfo"]
                    g_cover = info.get("imageLinks", {}).get("thumbnail")
                    if g_cover and book_data["cover"] == PLACEHOLDER_COVER: book_data["cover"] = g_cover.replace("http:", "https:")
                    g_summary = info.get("description")
                    if g_summary and book_data["summary"] == "No summary available.": book_data["summary"] = g_summary
        except: pass
            
    # OpenLibrary Fallback
    if book_data["cover"] == PLACEHOLDER_COVER or book_data["summary"] == "No summary available.":
        for isbn in meta['isbns']:
            if book_data["cover"] == PLACEHOLDER_COVER:
                try:
                    ol_resp = http_session.get(f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false", timeout=2, allow_redirects=True, stream=True)
                    if ol_resp.status_code == 200: book_data["cover"] = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false"
                except: pass

            if book_data["summary"] == "No summary available.":
                try:
                    ol_desc = http_session.get(f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&jscmd=details&format=json", timeout=2)
                    if ol_desc.status_code == 200:
                        ol_json = ol_desc.json()
                        if f"ISBN:{isbn}" in ol_json:
                            desc = ol_json[f"ISBN:{isbn}"].get("details", {}).get("description")
                            book_data["summary"] = desc["value"] if isinstance(desc, dict) else desc
                except: pass
            if book_data["cover"] != PLACEHOLDER_COVER and book_data["summary"] != "No summary available.": break

    return book_data

def get_user_zero_fallback_blocks(recommendations_df):
    if 'user_id' not in recommendations_df.columns or 'isbn' not in recommendations_df.columns: return []
    zero_recs = recommendations_df[recommendations_df['user_id'] == '0']
    if zero_recs.empty: return []
    return [b.strip() for b in " ".join(zero_recs['isbn'].astype(str).tolist()).split() if b.strip()]

# ====== THE MULTI-THREADING ENGINE ======
@st.cache_data(show_spinner=False)
def fetch_book_data_v2(item_id_blocks, _id_to_metadata, fallback_blocks=None): 
    books_results = []
    fallback_blocks = fallback_blocks or []
    seen_ids = set()
    seen_lock = threading.Lock()
    
    http_session = requests.Session()
    http_session.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    
    # Allow 20 concurrent connections to the APIs to prevent crashing
    retries = Retry(total=2, backoff_factor=0.2)
    adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20)
    http_session.mount('http://', adapter)
    http_session.mount('https://', adapter)

    def process_block(block):
        ids_for_this_book = [i.strip() for i in block.split(';') if i.strip()]
        for item_id in ids_for_this_book:
            details = get_complete_book_info(item_id, _id_to_metadata, http_session)
            if details is not None:
                with seen_lock:
                    if details["item_id"] not in seen_ids:
                        seen_ids.add(details["item_id"])
                        return details
        return None

    # FIRE ALL REQUESTS AT THE SAME TIME
    with ThreadPoolExecutor(max_workers=10) as executor:
        raw_results = list(executor.map(process_block, item_id_blocks))

    # Handle Fallbacks sequentially if any slots are empty
    fallback_index = 0
    for res in raw_results:
        if res is not None:
            books_results.append(res)
        else:
            found_fallback = False
            while fallback_index < len(fallback_blocks) and not found_fallback:
                fb = fallback_blocks[fallback_index]
                fallback_index += 1
                fallback_details = process_block(fb)
                if fallback_details is not None:
                    books_results.append(fallback_details)
                    found_fallback = True
            
            if not found_fallback:
                first_id = item_id_blocks[raw_results.index(res)].split(';')[0] if item_id_blocks[raw_results.index(res)] else "Unknown"
                books_results.append({"title": f"Not Found ({first_id})", "author": "Unknown", "cover": PLACEHOLDER_COVER, "summary": "ID missing."})
                
    return books_results

# --- HELPER: UI RENDERING FOR BOOK CARD ---
def render_book_card(book, rank):
    t_len = len(book["title"])
    fs = "16px" if t_len < 35 else "14px" if t_len < 60 else "12px" if t_len < 85 else "11px"
    st.markdown(f'<div class="book-title-box" style="font-size: {fs};">{book["title"]}</div>', unsafe_allow_html=True)
    badge_html = f'<div style="position: absolute; top: -15px; left: -15px; background-color: #dedbd0; color: {BURGUNDY}; width: 35px; height: 35px; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-weight: 900; font-size: 18px; box-shadow: 0 4px 8px rgba(0,0,0,0.3); z-index: 10; border: 2px solid white;">{rank}</div>'

    if book['cover'] == PLACEHOLDER_COVER:
        html_cover = f"""<div style="height: 220px; width: 100%; background-color: #9e1041; border-radius: 4px 12px 12px 4px; box-shadow: inset 4px 0 10px rgba(0,0,0,0.2), 0 4px 8px rgba(0,0,0,0.15); display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 15px; margin-bottom: 10px; text-align: center; position: relative; border-left: 5px solid #7a0c32;">{badge_html}<div style="color: white; font-weight: bold; font-size: 14px; margin-bottom: 10px; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden;">{book['title']}</div><div style="color: #e0e0e0; font-size: 12px; font-style: italic;">{book['author']}</div></div>"""
        st.markdown(html_cover, unsafe_allow_html=True)
    else:
        html_cover = f"""<div style="height: 220px; position: relative; display: flex; justify-content: center; align-items: center; margin-bottom: 10px;">{badge_html}<img src="{book['cover']}" style="max-height: 100%; max-width: 100%; object-fit: contain; box-shadow: 0 4px 8px rgba(0,0,0,0.15);"></div>"""
        st.markdown(html_cover, unsafe_allow_html=True)
        
    st.markdown(f'<div class="book-author-box"> {book.get("author", "Unknown Author")}</div>', unsafe_allow_html=True)
    with st.expander("Book summary"): st.write(book['summary'])

def display_netflix_row(title, books, row_key):
    if not books: return
    st.markdown(f"<div style='background-color: rgba(158, 16, 65, 0.9); padding: 10px 20px; border-radius: 4px; margin-top: 30px; margin-bottom: 20px; border-left: 6px solid white;'><h3 style='color: white; margin: 0;'>{title}</h3></div>", unsafe_allow_html=True)
    
    if f'page_{row_key}' not in st.session_state: st.session_state[f'page_{row_key}'] = 0
    page = st.session_state[f'page_{row_key}']
    
    visible_books = books[page*5:(page*5)+5]
    cols = st.columns([1, 1, 1, 1, 1, 0.4])
    
    for col_idx, book in enumerate(visible_books):
        with cols[col_idx]: render_book_card(book, (page*5) + col_idx + 1)
            
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
        st.markdown("""<div style='background-color: #dedbd0; padding: 30px 40px; border-radius: 4px; width: 100%; max-width: 450px; margin-top: 20px; margin-left: 60px;'><h2 style='color: #9e1041; margin-top: 0;'>Quick link</h2><div style='color:#9e1041;font-size:18px;'><span>Register to BCUL</span><br><br><span>Q&A service</span><br><br><span>Schedule</span><br><br><span>Online book reservation</span></div></div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("""<div class="styled-box"><h3 style="margin-top:0; color:white;">Smart Recommendations</h3><p>Access the library's smart recommendation system.</p></div>""", unsafe_allow_html=True)
        if st.button("click here"):
            st.session_state.view = 'login'
            st.rerun()

elif st.session_state.view == 'login':
    apply_full_page_style(LOGIN_BG_URL)
    st.markdown('<h1 class="hero-title">Welcome</h1>', unsafe_allow_html=True)
    _, col = st.columns([1.5, 1])
    with col:
        st.markdown("""<div class="styled-box"><h3 style="margin-top:0; color:white;">Identification</h3><p>Please enter your User ID to access your recommendations. If you are a new user, please type "new".</p></div>""", unsafe_allow_html=True)
        user_id = st.text_input("User ID", key="user_id_input")
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
        div[data-testid="stVerticalBlockBorderWrapper"] { background-color: #FFFFFF !important; opacity: 1 !important; backdrop-filter: none !important; padding: 3rem !important; border-radius: 12px !important; box-shadow: 0 15px 45px rgba(0,0,0,0.4) !important; border: none !important; margin-top: 20px !important; margin-bottom: 50px !important; margin-left: 5% !important; margin-right: 5% !important; }
        div[data-testid="stVerticalBlockBorderWrapper"] h1, div[data-testid="stVerticalBlockBorderWrapper"] p, div[data-testid="stVerticalBlockBorderWrapper"] span, div[data-testid="stVerticalBlockBorderWrapper"] label { color: #1a1a1a !important; }
        .stExpander { background-color: #ffffff !important; border: 1px solid #cccccc !important; }
        .book-title-box { background-color: rgba(158, 16, 65, 1) !important; color: white !important; padding: 15px 10px 5px 10px; border: 1px solid #e0e0e0; border-radius: 6px; text-align: center; font-weight: bold; margin-bottom: 10px; height: 75px; display: flex; align-items: flex-start; justify-content: center; box-shadow: 0 2px 5px rgba(0,0,0,0.05); overflow: hidden; }
        .book-author-box { background-color: rgba(255, 255, 255, 1) !important; color: #555555 !important; padding: 8px; border: 1px solid #e0e0e0; border-radius: 6px; text-align: center; font-weight: bold; font-size: 14px; margin-top: 6px; margin-bottom: 6px; height: 55px; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 5px rgba(0,0,0,0.05); overflow: hidden; }
        .history-container::-webkit-scrollbar { width: 6px; } .history-container::-webkit-scrollbar-track { background: #f1f1f1; border-radius: 4px; } .history-container::-webkit-scrollbar-thumb { background: #c1c1c1; border-radius: 4px; } .history-container::-webkit-scrollbar-thumb:hover { background: #9e1041; }
        </style>
    """, unsafe_allow_html=True)

    if st.button("← Back to Welcome Page"):
        st.session_state.view = 'landing'
        st.rerun()

    with st.container(border=False):
        with st.spinner("Connecting to Library Database..."):
            recs_df = load_data_csv("recommendations_2.csv")
            items_df = load_data_csv("items.csv") 
            interactions_df = load_data_csv("interactions_train.csv")
            
            if items_df.empty:
                st.error("Failed to load inventory catalog (items.csv).")
                st.stop()
            
            uid_entered = str(st.session_state.user_id).strip()
            required_ids = set()
            
            user_recs = recs_df[recs_df['user_id'] == uid_entered] if not recs_df.empty else pd.DataFrame()
            new_recs = recs_df[recs_df['user_id'] == 'new'] if not recs_df.empty else pd.DataFrame()
            fallback_blocks = get_user_zero_fallback_blocks(recs_df)

            def extract_blocks(df_subset):
                if df_subset.empty: return []
                all_blocks = [b.strip() for b in " ".join(df_subset['isbn'].astype(str).tolist()).split() if b.strip()]
                unique_blocks = []
                seen = set()
                for b in all_blocks:
                    if b not in seen:
                        seen.add(b)
                        unique_blocks.append(b)
                return unique_blocks[:10]

            def add_ids(blocks):
                for block in blocks:
                    for i in block.split(';'):
                        if i.strip(): required_ids.add(i.strip())

            user_blocks = extract_blocks(user_recs)
            new_blocks = extract_blocks(new_recs)
            
            add_ids(user_blocks)
            add_ids(new_blocks)
            add_ids(fallback_blocks)

            user_hist_df = pd.DataFrame()
            if not interactions_df.empty and 'u' in interactions_df.columns and uid_entered != 'new':
                user_hist_df = interactions_df[interactions_df['u'] == uid_entered]
                if not user_hist_df.empty: required_ids.update(user_hist_df['i'].astype(str).str.strip().tolist())

            id_to_metadata = build_targeted_catalog(items_df, required_ids)
            
        history_html = ""
        if not user_hist_df.empty:
            hist_items = []
            for _, row in user_hist_df.iterrows():
                meta = id_to_metadata.get(str(row.get('i', '')).strip(), {'title': 'Unknown Title', 'author': 'Unknown Author'})
                hist_items.append(f"""<div style="background-color: #f8f9fa; border-left: 4px solid #9e1041; padding: 12px; margin-bottom: 10px; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);"><div style="font-size: 11px; color: #888; font-weight: bold; margin-bottom: 4px;">{str(row.get('t', '')).strip()}</div><div style="font-size: 13px; font-weight: bold; color: #222; line-height: 1.2; margin-bottom: 4px;">{meta['title']}</div><div style="font-size: 12px; font-style: italic; color: #555;">{meta['author']}</div></div>""")
            if hist_items: history_html = f"""<div style="padding-right: 15px; margin-top: 30px;"><h3 style="color: #9e1041; border-bottom: 2px solid #9e1041; padding-bottom: 8px; margin-top: 0; font-size: 20px;">Borrowing History</h3><div class="history-container" style="max-height: 520px; overflow-y: auto; padding-right: 8px;">{''.join(hist_items)}</div></div>"""
        
        if not user_blocks and uid_entered != 'new':
            st.warning("Your user ID doesn't exist. Please type 'new' to see our general recommendations.")
        else:
            with st.spinner("Downloading Book Covers..."):
                books_user = fetch_book_data_v2(user_blocks, id_to_metadata, fallback_blocks) if user_blocks else []
                books_new = fetch_book_data_v2(new_blocks, id_to_metadata, fallback_blocks) if new_blocks else []
                
                if history_html and uid_entered != 'new':
                    col_hist, col_main = st.columns([1, 2.8])
                    with col_hist: st.markdown(history_html, unsafe_allow_html=True)
                    with col_main:
                        if books_user: display_netflix_row("Recommended for You", books_user, "user_row")
                        if books_new and uid_entered != 'new': display_netflix_row("Top 10 Library Recommendations", books_new, "new_row")
                else:
                    if books_user: display_netflix_row("Trending Picks" if uid_entered == 'new' else "Recommended for You", books_user, "user_row")
                    if books_new and uid_entered != 'new': display_netflix_row("Top 10 Library Recommendations", books_new, "new_row")