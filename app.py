import streamlit as st
import sys
import subprocess
import os
import time
from pathlib import Path

# Force-Link: This ensures the library is in the path even if installed mid-run
try:
    from google.cloud import vision
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "google-cloud-vision"])
    # Force a path refresh
    import site
    from importlib import reload
    reload(site)
    from google.cloud import vision

from news_api import fetch_crime_news
from blender_generator import generate_blender_script
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import io
import hashlib
import random

# Import fpdf2 for PDF generation (with auto-install)
try:
    from fpdf import FPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "fpdf2"])
        import site
        from importlib import reload
        reload(site)
        from fpdf import FPDF
        PDF_AVAILABLE = True
    except:
        PDF_AVAILABLE = False

# Load environment variables from .env file
load_dotenv()

# Get the base directory (normalized absolute path)
BASE_DIR = Path(os.path.abspath(os.getcwd()))

# Set Google Cloud Vision credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(BASE_DIR / 'cloud_key.json')

# Vision is now available (auto-installed if needed)
VISION_AVAILABLE = True

# Import PyDrive2 for Google Drive integration
try:
    from pydrive2.auth import GoogleAuth
    from pydrive2.drive import GoogleDrive
    from google.oauth2 import service_account
    DRIVE_AVAILABLE = True
except ImportError:
    DRIVE_AVAILABLE = False

# Ensure evidence_renders folder exists
EVIDENCE_RENDERS_DIR = BASE_DIR / "evidence_renders"
EVIDENCE_RENDERS_DIR.mkdir(exist_ok=True)

# Ensure Forensic_Archive folder exists for local archiving
FORENSIC_ARCHIVE_DIR = BASE_DIR / "Forensic_Archive"
FORENSIC_ARCHIVE_DIR.mkdir(exist_ok=True)

# Initialize session state for threat_level if it doesn't exist
if 'threat_level' not in st.session_state:
    st.session_state['threat_level'] = 'Normal'

# Initialize session state for crime_category if it doesn't exist (before any UI calls)
if 'crime_category' not in st.session_state:
    st.session_state['crime_category'] = 'Domestic'

# Initialize session state for active_case (Terminal Boot logic)
if 'active_case' not in st.session_state:
    st.session_state['active_case'] = False

# Initialize session state for System Health tracking
if 'gcp_credits' not in st.session_state:
    st.session_state['gcp_credits'] = 300.0  # Start with $300
    
if 'process_states' not in st.session_state:
    st.session_state['process_states'] = {
        'scraper': True,      # Always on
        'vision_ai': False,   # Active when scanning
        'blender': False      # Active when rendering
    }

# Page configuration
st.set_page_config(
    page_title="Digital Detective - Crime News Evidence Room",
    page_icon="🔍",
    layout="wide"
)

# Inject custom CSS for dark mode UI
st.markdown("""
    <style>
    /* Main background */
    .stApp {
        background-color: #0E1117;
    }
    
    /* Header background */
    header[data-testid="stHeader"] {
        background-color: #0E1117;
    }
    
    /* Main container */
    .main .block-container {
        background-color: #0E1117;
        padding-top: 2rem;
    }
    
    /* Text colors */
    h1, h2, h3, h4, h5, h6, p, div, span, label {
        color: #FFFFFF !important;
    }
    
    /* Widget borders - neon blue */
    .stTextInput>div>div>input,
    .stSelectbox>div>div>select {
        border: 1px solid #00D4FF !important;
        background-color: #1E1E1E !important;
        color: #00D4FF !important;
    }
    
    .stTextInput>div>div>input:focus,
    .stSelectbox>div>div>select:focus {
        border: 2px solid #00D4FF !important;
        box-shadow: 0 0 10px rgba(0, 212, 255, 0.5) !important;
        background-color: #1E1E1E !important;
        color: #00D4FF !important;
    }
    
    /* Dropdown menu items - dark background (native select) */
    .stSelectbox>div>div>select option {
        background-color: #1E1E1E !important;
        color: #00D4FF !important;
    }
    
    /* Target the dropdown popover menu specifically */
    div[data-baseweb="popover"], div[data-baseweb="menu"], ul[role="listbox"] {
        background-color: #1E1E1E !important;
        border: 1px solid #00D4FF !important;
    }
    
    /* Force text inside the dropdown to be neon blue */
    div[data-baseweb="popover"] span, 
    div[data-baseweb="popover"] div, 
    li[role="option"] {
        color: #00D4FF !important;
        background-color: transparent !important;
    }
    
    /* Hover state for dropdown items */
    li[role="option"]:hover {
        background-color: #2A2A2A !important;
        color: #00D4FF !important;
    }
    
    /* Ensure dropdown options have correct colors */
    li[role="option"] {
        background-color: #1E1E1E !important;
        color: #00D4FF !important;
    }
    
    /* Selectbox placeholder and selected text */
    .stSelectbox>div>div>select::-webkit-input-placeholder {
        color: #00D4FF !important;
    }
    
    .stSelectbox>div>div>select::placeholder {
        color: #00D4FF !important;
    }
    
    /* Input placeholder text */
    .stTextInput>div>div>input::placeholder {
        color: #00D4FF !important;
        opacity: 0.6;
    }
    
    .stTextInput>div>div>input::-webkit-input-placeholder {
        color: #00D4FF !important;
        opacity: 0.6;
    }
    
    /* Other widget borders - neon blue */
    .stTextArea>div>div>textarea,
    .stNumberInput>div>div>input,
    .stDateInput>div>div>input {
        border: 1px solid #00D4FF !important;
        background-color: rgba(14, 17, 23, 0.8) !important;
        color: #FFFFFF !important;
    }
    
    .stTextArea>div>div>textarea:focus,
    .stNumberInput>div>div>input:focus,
    .stDateInput>div>div>input:focus {
        border: 2px solid #00D4FF !important;
        box-shadow: 0 0 10px rgba(0, 212, 255, 0.5) !important;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background-color: rgba(0, 212, 255, 0.1) !important;
        border: 1px solid #00D4FF !important;
        color: #FFFFFF !important;
    }
    
    /* Tactical Switch Buttons */
    .stButton>button {
        background: linear-gradient(135deg, rgba(0, 212, 255, 0.1), rgba(0, 212, 255, 0.05));
        border: 2px solid #00D4FF;
        color: #00D4FF;
        font-weight: 600;
        padding: 0.5rem 1.5rem;
        border-radius: 8px;
        transition: all 0.3s ease;
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.2);
        text-transform: uppercase;
        letter-spacing: 1px;
        font-size: 0.9rem;
    }
    
    .stButton>button:hover {
        background: linear-gradient(135deg, rgba(0, 212, 255, 0.3), rgba(0, 212, 255, 0.15));
        border-color: #00D4FF;
        box-shadow: 0 0 25px rgba(0, 212, 255, 0.6), inset 0 0 20px rgba(0, 212, 255, 0.1);
        transform: translateY(-2px);
        color: #FFFFFF;
    }
    
    .stButton>button:active {
        transform: translateY(0);
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.4);
    }
    
    /* Primary button (different style) */
    .stButton>button[kind="primary"] {
        background: linear-gradient(135deg, #00D4FF, #0099CC);
        color: #0E1117;
        font-weight: 700;
        border: 2px solid #00D4FF;
        box-shadow: 0 0 20px rgba(0, 212, 255, 0.5);
    }
    
    .stButton>button[kind="primary"]:hover {
        background: linear-gradient(135deg, #00E5FF, #00B8E6);
        box-shadow: 0 0 30px rgba(0, 212, 255, 0.8);
        transform: translateY(-2px);
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #0E1117;
        border-right: 1px solid #00D4FF;
    }
    
    [data-testid="stSidebar"] .stTextInput>div>div>input,
    [data-testid="stSidebar"] .stSelectbox>div>div>select {
        border: 1px solid #00D4FF !important;
        background-color: #1E1E1E !important;
        color: #00D4FF !important;
    }
    
    [data-testid="stSidebar"] .stSelectbox>div>div>select option {
        background-color: #1E1E1E !important;
        color: #00D4FF !important;
    }
    
    /* Noir Neon Alert Styling */
    .stAlert,
    div[data-baseweb="notification"] {
        background-color: #0F141E !important;
        border: 2px solid #00D4FF !important;
        box-shadow: 0 0 10px #00D4FF, inset 0 0 5px #00D4FF !important;
        color: #FFFFFF !important;
    }
    
    .stAlert *,
    div[data-baseweb="notification"] * {
        color: #FFFFFF !important;
        text-shadow: 0 0 5px #00D4FF !important;
    }
    
    /* Success Message Special - Pulse Animation */
    @keyframes pulse_verified {
        0% {
            border-color: #00D4FF;
            box-shadow: 0 0 10px #00D4FF, inset 0 0 5px #00D4FF;
        }
        50% {
            border-color: #00E5FF;
            box-shadow: 0 0 15px #00D4FF, 0 0 20px rgba(0, 212, 255, 0.5), inset 0 0 8px #00D4FF;
        }
        100% {
            border-color: #00D4FF;
            box-shadow: 0 0 10px #00D4FF, inset 0 0 5px #00D4FF;
        }
    }
    
    .stSuccess,
    div[data-baseweb="notification"][data-kind="success"] {
        background-color: #0F141E !important;
        border: 2px solid #00D4FF !important;
        box-shadow: 0 0 10px #00D4FF, inset 0 0 5px #00D4FF !important;
        animation: pulse_verified 2s ease-in-out infinite !important;
        color: #FFFFFF !important;
    }
    
    .stSuccess *,
    div[data-baseweb="notification"][data-kind="success"] * {
        color: #FFFFFF !important;
        text-shadow: 0 0 5px #00D4FF !important;
    }
    
    /* Divider */
    hr {
        border-color: #00D4FF;
        opacity: 0.3;
    }
    
    /* Analysis Desk container */
    .analysis-desk {
        background: linear-gradient(135deg, rgba(0, 212, 255, 0.05), rgba(0, 212, 255, 0.02));
        border: 1px solid #00D4FF;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
    
    /* Viewfinder effect for render container */
    .render-container {
        background: linear-gradient(135deg, rgba(0, 212, 255, 0.05), rgba(0, 212, 255, 0.02));
        border: 2px dashed #00D4FF;
        border-radius: 10px;
        padding: 1.5rem;
        min-height: 600px;
        position: relative;
        box-shadow: 0 0 20px rgba(0, 212, 255, 0.3), inset 0 0 20px rgba(0, 212, 255, 0.1);
    }
    
    /* Scanline overlay effect */
    .render-container::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: repeating-linear-gradient(
            0deg,
            rgba(0, 212, 255, 0.03) 0px,
            rgba(0, 212, 255, 0.03) 1px,
            transparent 1px,
            transparent 2px
        );
        pointer-events: none;
        border-radius: 10px;
        z-index: 1;
    }
    
    .render-container > * {
        position: relative;
        z-index: 2;
    }
    
    /* Status Dashboard */
    .status-dashboard {
        background: linear-gradient(135deg, rgba(0, 212, 255, 0.08), rgba(0, 212, 255, 0.03));
        border: 1px solid #00D4FF;
        border-radius: 10px;
        padding: 2rem;
    }
    
    .status-card {
        background: rgba(30, 30, 30, 0.6);
        border: 1px solid #00D4FF;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    .status-indicator {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 8px;
    }
    
    .status-online {
        background-color: #00D4FF;
        box-shadow: 0 0 10px rgba(0, 212, 255, 0.8);
    }
    
    .status-offline {
        background-color: #FF4444;
        box-shadow: 0 0 10px rgba(255, 68, 68, 0.8);
    }
    
    .status-warning {
        background-color: #FFA500;
        box-shadow: 0 0 10px rgba(255, 165, 0, 0.8);
    }
    
    .status-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.5rem 0;
        border-bottom: 1px solid rgba(0, 212, 255, 0.2);
    }
    
    .status-item:last-child {
        border-bottom: none;
    }
    
    .status-label {
        color: #B0B0B0;
        font-size: 0.9rem;
    }
    
    .status-value {
        color: #00D4FF;
        font-weight: 600;
        font-size: 0.9rem;
    }
    
    /* Case Report Dashboard */
    .case-report {
        background: linear-gradient(135deg, rgba(0, 212, 255, 0.08), rgba(0, 212, 255, 0.03));
        border: 1px solid #00D4FF;
        border-radius: 10px;
        padding: 2rem;
    }
    
    .case-section {
        background: rgba(30, 30, 30, 0.6);
        border: 1px solid #00D4FF;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
    
    .kill-chain-stage {
        background: rgba(0, 212, 255, 0.1);
        border-left: 4px solid #00D4FF;
        padding: 0.75rem;
        margin: 0.5rem 0;
        border-radius: 4px;
    }
    
    .kill-chain-active {
        background: rgba(0, 212, 255, 0.2);
        border-left: 4px solid #00D4FF;
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.4);
    }
    
    /* Pulsing Red Alert System */
    @keyframes pulse_red {
        0% {
            box-shadow: 0 0 5px #FF3131;
        }
        50% {
            box-shadow: 0 0 20px #FF3131, 0 0 30px #FF3131;
        }
        100% {
            box-shadow: 0 0 5px #FF3131;
        }
    }
    
    .critical-pulse {
        border: 2px solid #FF3131 !important;
        animation: pulse_red 2s ease-in-out infinite;
    }
    
    /* Critical mode - red accents */
    .critical-mode .render-container {
        border-color: #FF3131 !important;
        background: linear-gradient(135deg, rgba(255, 49, 49, 0.1), rgba(255, 49, 49, 0.05)) !important;
    }
    
    .critical-mode h3,
    .critical-mode .status-value,
    .critical-mode .kill-chain-active {
        color: #FF3131 !important;
    }
    
    /* Selectbox label styling - fix white text issue */
    label {
        color: #00D4FF !important;
        font-weight: bold !important;
    }
    
    /* Vintage Terminal Selectbox Styling */
    .stSelectbox [data-baseweb="select"] {
        background-color: #0F141E !important;
        color: #00D4FF !important;
        border: 1px solid #00D4FF !important;
        font-family: 'Courier New', monospace !important;
    }
    
    .stSelectbox [data-baseweb="select"]:focus {
        background-color: #0F141E !important;
        color: #00D4FF !important;
        border: 1px solid #00D4FF !important;
        outline: none !important;
        box-shadow: 0 0 5px rgba(0, 212, 255, 0.3) !important;
    }
    
    /* System Health LED Indicators */
    @keyframes pulse_led_blue {
        0% {
            opacity: 1;
            box-shadow: 0 0 5px #00D4FF, 0 0 10px #00D4FF;
        }
        50% {
            opacity: 0.6;
            box-shadow: 0 0 10px #00D4FF, 0 0 20px #00D4FF, 0 0 30px #00D4FF;
        }
        100% {
            opacity: 1;
            box-shadow: 0 0 5px #00D4FF, 0 0 10px #00D4FF;
        }
    }
    
    @keyframes pulse_led_orange {
        0% {
            opacity: 1;
            box-shadow: 0 0 5px #FF8800, 0 0 10px #FF8800;
        }
        50% {
            opacity: 0.6;
            box-shadow: 0 0 10px #FF8800, 0 0 20px #FF8800, 0 0 30px #FF8800;
        }
        100% {
            opacity: 1;
            box-shadow: 0 0 5px #FF8800, 0 0 10px #FF8800;
        }
    }
    
    @keyframes blink_led_green {
        0%, 100% {
            opacity: 1;
            box-shadow: 0 0 5px #00FF00, 0 0 10px #00FF00;
        }
        50% {
            opacity: 0.7;
            box-shadow: 0 0 3px #00FF00, 0 0 6px #00FF00;
        }
    }
    
    .led-indicator {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 8px;
        vertical-align: middle;
    }
    
    .led-green {
        background-color: #00FF00;
        animation: blink_led_green 2s ease-in-out infinite;
    }
    
    .led-blue-pulse {
        background-color: #00D4FF;
        animation: pulse_led_blue 1.5s ease-in-out infinite;
    }
    
    .led-orange-pulse {
        background-color: #FF8800;
        animation: pulse_led_orange 1.5s ease-in-out infinite;
    }
    
    .led-off {
        background-color: #444444;
        box-shadow: none;
    }
    
    .process-status-item {
        display: flex;
        align-items: center;
        padding: 0.5rem 0;
        border-bottom: 1px solid rgba(0, 212, 255, 0.2);
    }
    
    .process-status-item:last-child {
        border-bottom: none;
    }
    
    .credit-meter {
        background: linear-gradient(135deg, rgba(0, 212, 255, 0.1), rgba(0, 212, 255, 0.05));
        border: 1px solid #00D4FF;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    .credit-amount {
        font-size: 1.5rem;
        font-weight: 700;
        color: #00D4FF;
        text-shadow: 0 0 10px rgba(0, 212, 255, 0.5);
    }
    </style>
""", unsafe_allow_html=True)

# Helper functions
def run_forensic_scan(image_path):
    """
    Run Google Vision API Label Detection on the forensic render image.
    Returns a list of labels with descriptions and confidence scores.
    """
    if not VISION_AVAILABLE:
        return None, "Google Cloud Vision API is not available. Please install google-cloud-vision."
    
    try:
        # Initialize the Vision API client
        client = vision.ImageAnnotatorClient()
        
        # Read the image file
        with open(image_path, 'rb') as image_file:
            content = image_file.read()
        
        # Create an image object
        image = vision.Image(content=content)
        
        # Perform label detection
        response = client.label_detection(image=image)
        labels = response.label_annotations
        
        # Extract label data
        results = []
        for label in labels:
            results.append({
                'description': label.description,
                'score': label.score,
                'mid': label.mid
            })
        
        # Check for errors
        if response.error.message:
            return None, f"Error: {response.error.message}"
        
        return results, None
        
    except Exception as e:
        return None, f"Error running forensic scan: {str(e)}"

def get_or_create_folder(drive, folder_name):
    """
    Find or create a folder in Google Drive.
    Returns the folder ID.
    """
    try:
        # Search for existing folder
        file_list = drive.ListFile({
            'q': f"title='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        }).GetList()
        
        if file_list:
            # Folder exists, return its ID
            return file_list[0]['id']
        else:
            # Create new folder
            folder = drive.CreateFile({
                'title': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            })
            folder.Upload()
            return folder['id']
    except Exception as e:
        raise Exception(f"Error getting/creating folder: {str(e)}")

def archive_case_to_cloud(render_image_path, case_id, headline, forensic_labels=None):
    """
    Archive case files to Google Drive Forensic_Archive folder.
    Uploads latest_render.png and forensic_findings.txt.
    Returns dict with file IDs and links.
    """
    if not DRIVE_AVAILABLE:
        return None, "PyDrive2 is not available. Please install pydrive2."
    
    try:
        # Initialize Google Drive with Service Account
        gauth = GoogleAuth()
        gauth.auth_method = 'service'
        
        # Load service account credentials from cloud_key.json
        credentials_path = BASE_DIR / 'cloud_key.json'
        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=['https://www.googleapis.com/auth/drive']
        )
        
        # Set credentials
        gauth.credentials = credentials
        drive = GoogleDrive(gauth)
        
        # Get or create Forensic_Archive folder
        folder_id = get_or_create_folder(drive, 'Forensic_Archive')
        
        results = {}
        
        # Upload render image
        if render_image_path.exists():
            render_file = drive.CreateFile({
                'title': f"{case_id}_render.png",
                'parents': [{'id': folder_id}],
                'properties': {'Case ID': case_id, 'Headline': headline[:100]}
            })
            render_file.SetContentFile(str(render_image_path))
            render_file.Upload()
            results['render'] = {
                'id': render_file['id'],
                'link': f"https://drive.google.com/file/d/{render_file['id']}/view"
            }
        
        # Upload forensic findings text file
        findings_text = f"Case ID: {case_id}\n"
        findings_text += f"Headline: {headline}\n"
        findings_text += f"Archived: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        findings_text += "=" * 50 + "\n"
        findings_text += "AI FORENSIC FINDINGS\n"
        findings_text += "=" * 50 + "\n\n"
        
        if forensic_labels:
            findings_text += "Label Detections:\n"
            findings_text += "-" * 50 + "\n"
            for label in forensic_labels[:10]:
                description = label.get('description', 'Unknown')
                score = label.get('score', 0)
                relevance_score, category = get_relevance_score(description)
                confidence_pct = int(score * 100)
                findings_text += f"\n• {description}\n"
                findings_text += f"  Confidence: {confidence_pct}%\n"
                findings_text += f"  Relevance: {relevance_score}/100 ({category})\n"
            
            # Check for darkness warning
            has_darkness = any(
                'dark' in label.get('description', '').lower() or 
                'black' in label.get('description', '').lower()
                for label in forensic_labels
            )
            if has_darkness:
                findings_text += "\n⚠️ WARNING: Scene underexposed. Checking 3D lighting...\n"
        else:
            findings_text += "No forensic scan data available.\n"
        
        # Create temporary text file
        findings_file_path = EVIDENCE_RENDERS_DIR / f"{case_id}_findings.txt"
        with open(findings_file_path, 'w', encoding='utf-8') as f:
            f.write(findings_text)
        
        # Upload findings file
        findings_file = drive.CreateFile({
            'title': f"{case_id}_findings.txt",
            'parents': [{'id': folder_id}],
            'properties': {'Case ID': case_id, 'Headline': headline[:100]}
        })
        findings_file.SetContentFile(str(findings_file_path))
        findings_file.Upload()
        results['findings'] = {
            'id': findings_file['id'],
            'link': f"https://drive.google.com/file/d/{findings_file['id']}/view"
        }
        
        # Clean up temporary file
        if findings_file_path.exists():
            findings_file_path.unlink()
        
        return results, None
        
    except Exception as e:
        return None, f"Error archiving to cloud: {str(e)}"

def get_relevance_score(label_description):
    """
    Map Vision API labels to relevance scores for forensic cases.
    Returns a relevance score (0-100) and category.
    """
    label_lower = label_description.lower()
    
    # High relevance categories
    if any(term in label_lower for term in ['technology', 'computer', 'electronics', 'device', 'phone', 'laptop']):
        return 85, "Technology Evidence"
    if any(term in label_lower for term in ['room', 'interior', 'building', 'architecture', 'structure']):
        return 75, "Scene Analysis"
    if any(term in label_lower for term in ['light', 'illumination', 'bright', 'dark', 'shadow']):
        return 70, "Lighting Analysis"
    if any(term in label_lower for term in ['floor', 'wall', 'ceiling', 'surface']):
        return 65, "Surface Analysis"
    if any(term in label_lower for term in ['sphere', 'circle', 'object', 'marker']):
        return 80, "Evidence Marker"
    
    # Medium relevance
    if any(term in label_lower for term in ['furniture', 'table', 'chair', 'desk']):
        return 60, "Furniture"
    if any(term in label_lower for term in ['color', 'gray', 'grey', 'blue', 'red']):
        return 50, "Color Analysis"
    
    # Default medium relevance
    return 40, "General Detection"

class NoirPDF(FPDF):
    """Custom PDF class with Noir/Retro 1980s police report styling"""
    def __init__(self):
        super().__init__()
        # Courier is a built-in font in fpdf2 - no need to add it
        # Use Courier (typewriter font) for that retro police report look
        self.set_font('Courier', '', 10)
        # Page margins
        self.set_margins(20, 20, 20)
        self.set_auto_page_break(auto=True, margin=15)
    
    def sanitize_text(self, text):
        """
        NUCLEAR: Sanitize text to remove ALL Unicode characters that cause issues in PDF.
        Fast and aggressive approach: replace common culprits, then strip non-ASCII.
        """
        if not text:
            return ""
        
        # Convert to string if needed
        text = str(text)
        
        # Step 1: Replace common problematic characters with ASCII equivalents
        text = text.replace(''', "'")  # Right single quotation mark
        text = text.replace(''', "'")  # Left single quotation mark
        text = text.replace('"', '"')  # Left double quotation mark
        text = text.replace('"', '"')  # Right double quotation mark
        text = text.replace('—', '-')  # Em-dash
        text = text.replace('–', '-')  # En-dash
        
        # Step 2: NUCLEAR - Strip every single non-ASCII character
        # This is the fastest way to ensure PDF compatibility
        text = text.encode('ascii', 'ignore').decode('ascii')
        
        return text
    
    def header(self):
        # Header with CONFIDENTIAL stamp
        self.set_font('Courier', 'B', 14)
        self.set_text_color(0, 0, 0)  # Black text
        self.cell(0, 10, 'CONFIDENTIAL: DIGITAL FORENSIC REPORT', 0, 1, 'C')
        self.ln(3)
    
    def footer(self):
        # Page number at bottom
        self.set_y(-15)
        self.set_font('Courier', '', 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
    
    def section_title(self, title):
        """Add a section title with underline"""
        self.set_font('Courier', 'B', 12)
        self.set_text_color(0, 0, 0)
        self.ln(5)
        self.cell(0, 8, title, 0, 1)
        self.line(20, self.get_y(), 190, self.get_y())
        self.ln(3)
    
    def add_text_block(self, text, font_size=10, bold=False):
        """Add a block of text with wrapping"""
        self.set_font('Courier', 'B' if bold else '', font_size)
        self.set_text_color(0, 0, 0)
        # Replace multiple spaces and newlines for cleaner text
        text = ' '.join(text.split())
        self.multi_cell(0, 5, text)
        self.ln(2)

def generate_case_pdf(case_id, article, pixel_art_bytes=None, render_image_path=None, forensic_labels=None):
    """
    Generate a Noir/Retro style PDF case file.
    
    Args:
        case_id: The case identifier
        article: Dictionary with article data (title, description, source, url, publishedAt)
        pixel_art_bytes: BytesIO object containing the pixel art image
        render_image_path: Path to the 3D render image (if exists)
        forensic_labels: List of AI Vision labels with scores
    
    Returns:
        BytesIO object containing the PDF bytes
    """
    if not PDF_AVAILABLE:
        return None, "PDF generation library (fpdf2) is not available."
    
    try:
        pdf = NoirPDF()
        pdf.add_page()
        
        # Case ID header
        pdf.set_font('Courier', 'B', 16)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 10, f'CASE ID: {case_id}', 0, 1, 'C')
        pdf.ln(5)
        
        # Date stamp
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pdf.set_font('Courier', '', 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, f'Report Generated: {current_date}', 0, 1, 'C')
        pdf.ln(5)
        
        # Section 1: News Article Intelligence
        pdf.section_title('SOURCE INTELLIGENCE: NEWS ARTICLE')
        
        title = article.get('title', 'No Title Available')
        description = article.get('description', 'No description available.')
        source = article.get('source', {}).get('name', 'Unknown Source') if article.get('source') else 'Unknown Source'
        published = article.get('publishedAt', 'Unknown Date')[:10] if article.get('publishedAt') else 'Unknown Date'
        url = article.get('url', 'N/A')
        
        # Sanitize text for PDF compatibility (fix Unicode issues)
        title = pdf.sanitize_text(title)
        description = pdf.sanitize_text(description)
        source = pdf.sanitize_text(source)
        
        pdf.set_font('Courier', 'B', 10)
        pdf.cell(0, 5, 'Headline:', 0, 1)
        pdf.set_font('Courier', '', 10)
        pdf.multi_cell(0, 5, title)
        pdf.ln(2)
        
        pdf.set_font('Courier', 'B', 10)
        pdf.cell(0, 5, 'Source:', 0, 1)
        pdf.set_font('Courier', '', 10)
        pdf.cell(0, 5, source, 0, 1)
        pdf.ln(2)
        
        pdf.set_font('Courier', 'B', 10)
        pdf.cell(0, 5, 'Published:', 0, 1)
        pdf.set_font('Courier', '', 10)
        pdf.cell(0, 5, published, 0, 1)
        pdf.ln(2)
        
        pdf.set_font('Courier', 'B', 10)
        pdf.cell(0, 5, 'Article Description:', 0, 1)
        pdf.set_font('Courier', '', 10)
        # Clean description for PDF (remove HTML tags if any, limit length)
        desc_clean = description[:500] + '...' if len(description) > 500 else description
        pdf.multi_cell(0, 5, desc_clean)
        pdf.ln(2)
        
        pdf.set_font('Courier', 'B', 10)
        pdf.cell(0, 5, 'Source URL:', 0, 1)
        pdf.set_font('Courier', '', 8)
        pdf.cell(0, 5, url, 0, 1)
        pdf.ln(5)
        
        # Section 2: Visual Evidence - Pixel Art (Composite Sketch)
        if pixel_art_bytes:
            pdf.section_title('VISUAL EVIDENCE: COMPOSITE SKETCH (PIXEL ART)')
            try:
                # Convert BytesIO to temporary file path for fpdf2
                pixel_art_bytes.seek(0)
                temp_pixel_path = EVIDENCE_RENDERS_DIR / f"{case_id}_pixel_temp.png"
                with open(temp_pixel_path, 'wb') as f:
                    f.write(pixel_art_bytes.read())
                
                # Add image (max width 170mm, height auto)
                pdf.image(str(temp_pixel_path), x=25, w=160, h=0)
                pdf.ln(3)
                pdf.set_font('Courier', '', 8)
                pdf.set_text_color(100, 100, 100)
                pdf.cell(0, 5, 'Procedural Pixel Art - Preliminary Visual Evidence', 0, 1, 'C')
                
                # Clean up temp file
                if temp_pixel_path.exists():
                    temp_pixel_path.unlink()
                    
            except Exception as e:
                pdf.set_font('Courier', '', 9)
                pdf.set_text_color(200, 0, 0)
                pdf.cell(0, 5, f'[ERROR: Could not embed pixel art: {str(e)}]', 0, 1)
            pdf.ln(5)
        
        # Section 3: Visual Evidence - 3D Render (Crime Scene Reconstruction)
        if render_image_path and os.path.exists(render_image_path):
            pdf.section_title('VISUAL EVIDENCE: CRIME SCENE RECONSTRUCTION (3D RENDER)')
            try:
                # Add 3D render image
                pdf.image(str(render_image_path), x=25, w=160, h=0)
                pdf.ln(3)
                pdf.set_font('Courier', '', 8)
                pdf.set_text_color(100, 100, 100)
                pdf.cell(0, 5, '3D Evidence Room Render - Forensic Scene Reconstruction', 0, 1, 'C')
            except Exception as e:
                pdf.set_font('Courier', '', 9)
                pdf.set_text_color(200, 0, 0)
                pdf.cell(0, 5, f'[ERROR: Could not embed 3D render: {str(e)}]', 0, 1)
            pdf.ln(5)
        else:
            pdf.section_title('VISUAL EVIDENCE: CRIME SCENE RECONSTRUCTION (3D RENDER)')
            pdf.set_font('Courier', '', 9)
            pdf.set_text_color(150, 150, 150)
            pdf.cell(0, 5, '[STATUS: 3D Render not available]', 0, 1)
            pdf.ln(5)
        
        # Section 4: AI Forensic Analysis
        pdf.section_title('AI FORENSIC ANALYSIS: VISION DETECTION LABELS')
        
        if forensic_labels and len(forensic_labels) > 0:
            pdf.set_font('Courier', 'B', 10)
            pdf.cell(0, 5, 'AI Vision Detections:', 0, 1)
            pdf.ln(2)
            
            # Check for darkness warning
            has_darkness = any(
                'dark' in label.get('description', '').lower() or 
                'black' in label.get('description', '').lower()
                for label in forensic_labels
            )
            if has_darkness:
                pdf.set_font('Courier', 'B', 9)
                pdf.set_text_color(200, 100, 0)
                pdf.cell(0, 5, '⚠️ WARNING: Scene underexposed. Checking 3D lighting...', 0, 1)
                pdf.set_text_color(0, 0, 0)
                pdf.ln(2)
            
            # Display top 15 labels
            for i, label in enumerate(forensic_labels[:15], 1):
                description = label.get('description', 'Unknown')
                score = label.get('score', 0)
                confidence_pct = int(score * 100)
                relevance_score, category = get_relevance_score(description)
                
                pdf.set_font('Courier', 'B', 9)
                pdf.cell(0, 5, f'{i}. {description}', 0, 1)
                pdf.set_font('Courier', '', 8)
                pdf.set_text_color(80, 80, 80)
                pdf.cell(0, 4, f'   Confidence: {confidence_pct}% | Relevance: {relevance_score}/100 ({category})', 0, 1)
                pdf.set_text_color(0, 0, 0)
                pdf.ln(1)
        else:
            pdf.set_font('Courier', '', 9)
            pdf.set_text_color(150, 150, 150)
            pdf.cell(0, 5, '[STATUS: No AI Forensic scan data available]', 0, 1)
            pdf.cell(0, 4, 'Generate a render and run AI Forensic Scan to populate this section.', 0, 1)
        
        pdf.ln(5)
        
        # Footer section
        pdf.section_title('END OF REPORT')
        pdf.set_font('Courier', '', 8)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, f'This report was automatically generated by Digital Detective Evidence Room Generator.', 0, 1, 'C')
        pdf.cell(0, 4, f'Case ID: {case_id} | Report Date: {current_date}', 0, 1, 'C')
        
        # Convert PDF to bytes
        pdf_bytes = io.BytesIO()
        pdf.output(pdf_bytes)
        pdf_bytes.seek(0)
        
        return pdf_bytes, None
        
    except Exception as e:
        return None, f"Error generating PDF: {str(e)}"

def generate_procedural_pixel_art(article_text, case_id="", category="Domestic"):
    """
    Generate unique procedural pixel art using a Layered Composition approach.
    VISUAL FIDELITY OVERHAUL: Fixed 512x512 dimensions with centered 256x256 drawing zone.
    Includes symmetry engine, icon stamps, and soft CRT overlay.
    
    Args:
        article_text: Text content of the article (used for keyword analysis)
        case_id: Case identifier (used as seed for consistency - ensures same case looks same)
        category: Crime department category ('International', 'Domestic', or 'White Collar')
    """
    # Seed Logic: Use case_id as seed to ensure consistency - same case looks same across runs
    if case_id:
        seed = hash(case_id) % (2**32)
    else:
        seed = hash(article_text) % (2**32)
    random.seed(seed)
    
    # SIZE & CLARITY: Internal drawing canvas is 256x256 (scaled to 512x512) for sharp pixel DNA
    final_size = 512
    canvas_size = 256  # Direct 256x256 canvas - sharp and high-quality, not blurry
    img = Image.new('RGBA', (canvas_size, canvas_size), color=(0, 0, 0, 0))  # Transparent background
    pixels = img.load()
    
    # Symmetry Engine: Helper function to mirror pixels horizontally
    def mirror_pixel(x, y, color):
        """Draw pixel and its horizontal mirror for Rorschach-style forensic symbols"""
        if 0 <= x < canvas_size and 0 <= y < canvas_size:
            pixels[x, y] = color
        # Mirror pixel horizontally
        mirror_x = canvas_size - 1 - x
        if 0 <= mirror_x < canvas_size and 0 <= y < canvas_size:
            pixels[mirror_x, y] = color
    
    # Icon Stamps: 8x8 pixel stamp functions
    def stamp_badge(center_x, center_y, color):
        """Draw an 8x8 badge icon stamp"""
        stamp_size = 8
        start_x = center_x - stamp_size // 2
        start_y = center_y - stamp_size // 2
        
        # Badge shape: star/pentagon outline
        for dy in range(stamp_size):
            for dx in range(stamp_size):
                x = start_x + dx
                y = start_y + dy
                # Create star shape
                dist_from_center = abs(dx - stamp_size//2) + abs(dy - stamp_size//2)
                if dist_from_center == 2 or dist_from_center == 3:
                    if 0 <= x < canvas_size and 0 <= y < canvas_size:
                        pixels[x, y] = color
    
    def stamp_impact(center_x, center_y, color):
        """Draw an 8x8 impact/crash icon stamp"""
        stamp_size = 8
        start_x = center_x - stamp_size // 2
        start_y = center_y - stamp_size // 2
        
        # Impact shape: radiating lines from center
        center_offset = stamp_size // 2
        for dy in range(stamp_size):
            for dx in range(stamp_size):
                x = start_x + dx
                y = start_y + dy
                # Create radiating pattern
                angle = ((dx - center_offset)**2 + (dy - center_offset)**2) ** 0.5
                if 2 <= angle <= 3.5:
                    if 0 <= x < canvas_size and 0 <= y < canvas_size:
                        pixels[x, y] = color
    
    def stamp_digital_vault(center_x, center_y, color):
        """Draw an 8x8 digital vault icon stamp"""
        stamp_size = 8
        start_x = center_x - stamp_size // 2
        start_y = center_y - stamp_size // 2
        
        # Vault shape: rounded rectangle with lock
        for dy in range(stamp_size):
            for dx in range(stamp_size):
                x = start_x + dx
                y = start_y + dy
                # Border
                on_border = (dx == 0 or dx == stamp_size - 1 or dy == 0 or dy == stamp_size - 1)
                # Lock center
                lock_center = (dx >= 2 and dx <= 5 and dy >= 3 and dy <= 6)
                if on_border or lock_center:
                    if 0 <= x < canvas_size and 0 <= y < canvas_size:
                        pixels[x, y] = color
    
    # Category-specific color palettes - Initialize at the very start of the function
    category_colors = {
        'International': {
            # Deep Indigo/Shadow
            'bg_top': (30, 20, 50),      # Deep indigo
            'bg_bottom': (15, 10, 30),   # Shadow indigo
            'primary': (60, 40, 100),    # Indigo accent
            'secondary': (40, 30, 70),   # Darker indigo
            'accent': (100, 80, 150),    # Lighter indigo highlight
        },
        'Domestic': {
            # Law Enforcement Blue/Yellow
            'bg_top': (20, 40, 80),      # Law enforcement blue
            'bg_bottom': (10, 20, 50),   # Darker blue
            'primary': (0, 100, 200),    # Bright blue
            'secondary': (255, 200, 0),  # Yellow/gold accent
            'accent': (150, 200, 255),   # Light blue highlight
        },
        'White Collar': {
            # High-Finance Emerald/Neon-Gold
            'bg_top': (10, 40, 30),      # Dark emerald
            'bg_bottom': (5, 20, 15),    # Shadow emerald
            'primary': (0, 200, 150),    # Emerald green
            'secondary': (200, 180, 80), # Neon gold
            'accent': (100, 255, 200),   # Bright emerald highlight
        }
    }
    
    # Default Palette fallback: Ensure cat_colors is always defined
    # If category is somehow missing, use Domestic palette as fallback
    cat_colors = category_colors.get(category, category_colors['Domestic'])
    
    # LAYER 1: Background Gradient - Use category-specific colors
    top_color = cat_colors['bg_top']
    bottom_color = cat_colors['bg_bottom']
    
    # Draw vertical gradient background
    for y in range(canvas_size):
        t = y / canvas_size  # 0 at top, 1 at bottom
        r = int(top_color[0] * (1 - t) + bottom_color[0] * t)
        g = int(top_color[1] * (1 - t) + bottom_color[1] * t)
        b = int(top_color[2] * (1 - t) + bottom_color[2] * t)
        bg_color = (r, g, b, 255)  # Fully opaque
        for x in range(canvas_size):
            pixels[x, y] = bg_color
    
    # LAYER 2: Subject Layer - Category-Specific Asset Mapping
    asset_variant = seed % 2  # Use seed to determine which asset variant (0 or 1)
    
    if category == 'International':
        # International: Globe Silhouette or Cargo Container
        if asset_variant == 0:
            # Globe Silhouette
            center_x = canvas_size // 2
            center_y = canvas_size // 2
            radius = 18 + (seed % 5)  # Vary size slightly based on seed
            
            # Draw globe circle with SYMMETRY ENGINE
            for y in range(canvas_size):
                for x in range(canvas_size // 2 + 1):  # Only draw left half, mirror will handle right
                    dist = ((x - center_x)**2 + (y - center_y)**2) ** 0.5
                    if abs(dist - radius) <= 2:  # Globe outline
                        mirror_pixel(x, y, cat_colors['primary'])
                    elif dist < radius - 2:  # Globe fill
                        # Add latitude/longitude lines
                        angle = ((x - center_x)**2 + (y - center_y)**2) ** 0.5
                        if int(angle) % 4 == 0 or int((x - center_x) / 2) % 6 == 0:
                            mirror_pixel(x, y, cat_colors['secondary'])
                        else:
                            mirror_pixel(x, y, cat_colors['accent'])
            
            # Add stand/base
            stand_y = center_y + radius - 2
            for x in range(center_x - 8, center_x + 8):
                for y in range(stand_y, stand_y + 3):
                    if 0 <= x < canvas_size and 0 <= y < canvas_size:
                        pixels[x, y] = cat_colors['primary']
        elif asset_variant == 1:
            # Cargo Container
            container_width = 30 + (seed % 8)
            container_height = 20 + (seed % 6)
            container_x = canvas_size // 2 - container_width // 2
            container_y = canvas_size // 2 - container_height // 2
            
            # Draw container rectangle
            for y in range(container_y, container_y + container_height):
                for x in range(container_x, container_x + container_width):
                    if 0 <= x < canvas_size and 0 <= y < canvas_size:
                        pixels[x, y] = cat_colors['primary']
            
            # Add container door lines (vertical)
            door_line_x = container_x + container_width // 3
            for y in range(container_y, container_y + container_height):
                if 0 <= door_line_x < canvas_size and 0 <= y < canvas_size:
                    pixels[door_line_x, y] = cat_colors['secondary']
            
            # Add cargo label/hazard symbol (simple cross)
            label_x = container_x + container_width // 2
            label_y = container_y + container_height // 2
            for dx in range(-3, 4):
                if 0 <= label_x + dx < canvas_size and 0 <= label_y < canvas_size:
                    pixels[label_x + dx, label_y] = cat_colors['accent']
            for dy in range(-3, 4):
                if 0 <= label_x < canvas_size and 0 <= label_y + dy < canvas_size:
                    pixels[label_x, label_y + dy] = cat_colors['accent']
        else:
            # Fallback: Evidence Box (safety net for unexpected asset_variant values)
            evidence_box_size = 24
            box_x = canvas_size // 2 - evidence_box_size // 2
            box_y = canvas_size // 2 - evidence_box_size // 2
            for y in range(box_y, box_y + evidence_box_size):
                for x in range(box_x, box_x + evidence_box_size):
                    if 0 <= x < canvas_size and 0 <= y < canvas_size:
                        # Pixelated border pattern
                        on_border = (x == box_x or x == box_x + evidence_box_size - 1 or 
                                   y == box_y or y == box_y + evidence_box_size - 1)
                        if on_border:
                            pixels[x, y] = cat_colors['secondary']
                        else:
                            pixels[x, y] = cat_colors['primary']
    
    elif category == 'Domestic':
        # Domestic: Police Cruiser profile or Building with Badge
        if asset_variant == 0:
            # Police Cruiser profile
            cruiser_length = 35 + (seed % 6)
            cruiser_height = 12 + (seed % 4)
            cruiser_x = 8
            cruiser_y = canvas_size // 2 - cruiser_height // 2
            
            # Draw cruiser body (rectangle)
            for y in range(cruiser_y, cruiser_y + cruiser_height):
                for x in range(cruiser_x, cruiser_x + cruiser_length):
                    if 0 <= x < canvas_size and 0 <= y < canvas_size:
                        pixels[x, y] = cat_colors['primary']
            
            # Add cruiser roof (slightly offset)
            roof_x = cruiser_x + 8
            roof_length = cruiser_length - 16
            roof_height = cruiser_height - 4
            roof_y = cruiser_y - 2
            for y in range(roof_y, roof_y + roof_height):
                for x in range(roof_x, roof_x + roof_length):
                    if 0 <= x < canvas_size and 0 <= y < canvas_size:
                        pixels[x, y] = cat_colors['primary']
            
            # Add light bar (yellow/blue alternating)
            light_y = roof_y - 1
            for x in range(roof_x, roof_x + roof_length, 3):
                if (x - roof_x) % 6 < 3:
                    pixels[x, light_y] = cat_colors['secondary']  # Yellow
                else:
                    pixels[x, light_y] = cat_colors['accent']  # Blue
        elif asset_variant == 1:
            # Building with Badge icon
            building_width = 20 + (seed % 6)
            building_height = 35 + (seed % 8)
            building_x = canvas_size // 2 - building_width // 2
            building_y = canvas_size - building_height - 8
            
            # Draw building
            for y in range(building_y, building_y + building_height):
                for x in range(building_x, building_x + building_width):
                    if 0 <= x < canvas_size and 0 <= y < canvas_size:
                        pixels[x, y] = cat_colors['primary']
            
            # Add windows
            num_windows = 3 + (seed % 3)
            window_spacing = building_height // (num_windows + 1)
            for i in range(num_windows):
                win_y = building_y + (i + 1) * window_spacing
                for wx in range(building_x + 4, building_x + building_width - 4, 6):
                    for wy in range(win_y, win_y + 2):
                        if 0 <= wx < canvas_size and 0 <= wy < canvas_size:
                            pixels[wx, wy] = cat_colors['secondary']  # Yellow windows
            
            # Add badge icon at top
            badge_x = building_x + building_width // 2
            badge_y = building_y + 5
            # Draw simple star/badge shape
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    nx, ny = badge_x + dx, badge_y + dy
                    if abs(dx) + abs(dy) <= 2 and 0 <= nx < canvas_size and 0 <= ny < canvas_size:
                        pixels[nx, ny] = cat_colors['secondary']  # Yellow badge
        else:
            # Fallback: Evidence Box (safety net for unexpected asset_variant values)
            evidence_box_size = 24
            box_x = canvas_size // 2 - evidence_box_size // 2
            box_y = canvas_size // 2 - evidence_box_size // 2
            for y in range(box_y, box_y + evidence_box_size):
                for x in range(box_x, box_x + evidence_box_size):
                    if 0 <= x < canvas_size and 0 <= y < canvas_size:
                        # Pixelated border pattern
                        on_border = (x == box_x or x == box_x + evidence_box_size - 1 or 
                                   y == box_y or y == box_y + evidence_box_size - 1)
                        if on_border:
                            pixels[x, y] = cat_colors['secondary']
                        else:
                            pixels[x, y] = cat_colors['primary']
    
    elif category == 'White Collar':
        # White Collar: Bar Chart with 'Glitch' or Digital Vault
        if asset_variant == 0:
            # Bar Chart with Glitch
            chart_x = 8
            chart_y = canvas_size - 12
            chart_width = 48
            num_bars = 5 + (seed % 3)
            bar_width = chart_width // num_bars
            
            bar_heights = []
            for i in range(num_bars):
                height = 10 + (seed * (i + 1)) % 25  # Vary heights based on seed
                bar_heights.append(height)
            
            # Draw bars
            for i, height in enumerate(bar_heights):
                bar_x = chart_x + i * bar_width + 2
                bar_top = chart_y - height
                
                for y in range(bar_top, chart_y):
                    for x in range(bar_x, bar_x + bar_width - 2):
                        if 0 <= x < canvas_size and 0 <= y < canvas_size:
                            pixels[x, y] = cat_colors['primary']  # Emerald green
                
                # Add glitch effect (random offset pixels)
                glitch_count = 2 + (seed * i) % 3
                for _ in range(glitch_count):
                    glitch_x = bar_x + (seed * i) % (bar_width - 2)
                    glitch_y = bar_top + (seed * (i + 10)) % height
                    if 0 <= glitch_x < canvas_size and 0 <= glitch_y < canvas_size:
                        pixels[glitch_x, glitch_y] = cat_colors['accent']  # Bright highlight
            
            # Add axis lines
            for x in range(chart_x, chart_x + chart_width):
                if 0 <= x < canvas_size and 0 <= chart_y < canvas_size:
                    pixels[x, chart_y] = cat_colors['secondary']  # Gold axis
        elif asset_variant == 1:
            # Digital Vault
            vault_size = 24 + (seed % 6)
            vault_x = canvas_size // 2 - vault_size // 2
            vault_y = canvas_size // 2 - vault_size // 2
            
            # Draw vault outline (rounded rectangle)
            for y in range(vault_y, vault_y + vault_size):
                for x in range(vault_x, vault_x + vault_size):
                    if 0 <= x < canvas_size and 0 <= y < canvas_size:
                        # Check if on border
                        on_border = (x == vault_x or x == vault_x + vault_size - 1 or 
                                   y == vault_y or y == vault_y + vault_size - 1)
                        if on_border:
                            pixels[x, y] = cat_colors['secondary']  # Gold border
                        else:
                            pixels[x, y] = cat_colors['primary']  # Emerald fill
            
            # Add digital lock/keypad
            keypad_x = canvas_size // 2
            keypad_y = canvas_size // 2 + 4
            # Draw 3x3 grid of dots
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    kx, ky = keypad_x + dx * 3, keypad_y + dy * 3
                    if 0 <= kx < canvas_size and 0 <= ky < canvas_size:
                        pixels[kx, ky] = cat_colors['accent']  # Bright emerald dots
            
            # Add glow effect (outer ring)
            for y in range(vault_y - 2, vault_y + vault_size + 2):
                for x in range(vault_x - 2, vault_x + vault_size + 2):
                    if not (vault_x <= x < vault_x + vault_size and vault_y <= y < vault_y + vault_size):
                        if 0 <= x < canvas_size and 0 <= y < canvas_size:
                            dist_to_vault = min(abs(x - vault_x), abs(x - (vault_x + vault_size - 1)),
                                              abs(y - vault_y), abs(y - (vault_y + vault_size - 1)))
                            if dist_to_vault == 1:
                                pixels[x, y] = cat_colors['accent']  # Glow effect
        else:
            # Fallback: Evidence Box (safety net for unexpected asset_variant values)
            evidence_box_size = 24
            box_x = canvas_size // 2 - evidence_box_size // 2
            box_y = canvas_size // 2 - evidence_box_size // 2
            for y in range(box_y, box_y + evidence_box_size):
                for x in range(box_x, box_x + evidence_box_size):
                    if 0 <= x < canvas_size and 0 <= y < canvas_size:
                        # Pixelated border pattern
                        on_border = (x == box_x or x == box_x + evidence_box_size - 1 or 
                                   y == box_y or y == box_y + evidence_box_size - 1)
                        if on_border:
                            pixels[x, y] = cat_colors['secondary']
                        else:
                            pixels[x, y] = cat_colors['primary']
    else:
        # Default fallback: Evidence Box (if category doesn't match any known category)
        evidence_box_size = 24
        box_x = canvas_size // 2 - evidence_box_size // 2
        box_y = canvas_size // 2 - evidence_box_size // 2
        for y in range(box_y, box_y + evidence_box_size):
            for x in range(box_x, box_x + evidence_box_size):
                if 0 <= x < canvas_size and 0 <= y < canvas_size:
                    # Pixelated border pattern
                    on_border = (x == box_x or x == box_x + evidence_box_size - 1 or 
                               y == box_y or y == box_y + evidence_box_size - 1)
                    if on_border:
                        pixels[x, y] = cat_colors['secondary']
                    else:
                        pixels[x, y] = cat_colors['primary']
    
    # ICON STAMPS: Apply based on text content and category
    article_lower = article_text.lower()
    
    # Badge stamp: if text contains 'agent', 'ICE', or 'police'
    if any(keyword in article_lower for keyword in ['agent', 'ice', 'police']):
        stamp_x = canvas_size // 2 - 20
        stamp_y = canvas_size // 2 + 30
        stamp_badge(stamp_x, stamp_y, cat_colors['secondary'])
    
    # Impact stamp: if text contains 'crash' or 'accident'
    if any(keyword in article_lower for keyword in ['crash', 'accident']):
        stamp_x = canvas_size // 2 + 15
        stamp_y = canvas_size // 2 - 25
        stamp_impact(stamp_x, stamp_y, cat_colors['accent'])
    
    # Digital Vault stamp: if category is 'White Collar'
    if category == 'White Collar':
        stamp_x = canvas_size // 2
        stamp_y = canvas_size - 20
        stamp_digital_vault(stamp_x, stamp_y, cat_colors['secondary'])
    
    # LAYER 3: Atmosphere - Fog layer at bottom using semi-transparent dark gradient
    fog_height = 16  # Bottom quarter of canvas
    fog_start_y = canvas_size - fog_height
    
    for y in range(fog_start_y, canvas_size):
        fog_alpha = int(80 * (1 - (y - fog_start_y) / fog_height))  # More opaque at bottom
        for x in range(canvas_size):
            r, g, b, _ = pixels[x, y]
            # Blend with dark fog color
            fog_r, fog_g, fog_b = 5, 5, 10
            blend_factor = fog_alpha / 255.0
            new_r = int(r * (1 - blend_factor) + fog_r * blend_factor)
            new_g = int(g * (1 - blend_factor) + fog_g * blend_factor)
            new_b = int(b * (1 - blend_factor) + fog_b * blend_factor)
            pixels[x, y] = (new_r, new_g, new_b, 255)
    
    # 2D ENVIRONMENT: Add horizon line and grid floor to turn icon into environmental scene
    horizon_y = int(canvas_size * 0.65)  # Horizon line at 65% down the canvas
    
    # Grid floor (below horizon)
    grid_color = tuple(int(c * 0.7) for c in cat_colors['bg_bottom'])  # Slightly darker for grid
    for y in range(horizon_y, canvas_size):
        for x in range(canvas_size):
            # Grid pattern: every 8 pixels, draw a line
            if x % 8 == 0 or y % 8 == 0:
                pixels[x, y] = (grid_color[0], grid_color[1], grid_color[2], 255)
    
    # Horizon line (horizontal line at horizon_y)
    horizon_color = tuple(int(c * 0.8) for c in cat_colors['primary'])  # Horizon line color
    for x in range(canvas_size):
        pixels[x, horizon_y] = (horizon_color[0], horizon_color[1], horizon_color[2], 255)
    
    # Convert to RGB for final output (remove alpha channel for compatibility)
    # Use cat_colors['bg_bottom'] as background instead of black for seamless UI integration
    bg_rgb = cat_colors['bg_bottom']
    img_rgb = Image.new('RGB', (canvas_size, canvas_size), color=bg_rgb)
    img_rgb.paste(img, (0, 0), img)  # Paste RGBA onto RGB using alpha as mask
    
    # Upscale to 512x512 (sharp pixel art scaling)
    img_final = img_rgb.resize((final_size, final_size), resample=Image.NEAREST)
    
    # CRT Overlay: Soften scanlines to 10% opacity so they don't obscure the art
    overlay = Image.new('RGBA', (final_size, final_size), color=(0, 0, 0, 0))
    overlay_pixels = overlay.load()
    scanline_opacity = int(255 * 0.10)  # 10% opacity
    
    for y in range(final_size):
        if y % 4 == 0:  # Every 4th row for scanline effect
            for x in range(final_size):
                overlay_pixels[x, y] = (0, 0, 0, scanline_opacity)
    
    # Blend overlay onto final image
    img_final_rgba = img_final.convert('RGBA')
    img_final_rgba = Image.alpha_composite(img_final_rgba, overlay)
    img_final = img_final_rgba.convert('RGB')
    
    # Save to bytes
    img_bytes = io.BytesIO()
    img_final.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    return img_bytes

def create_fallback_2d_visualization():
    """Create a clean dark-mode blueprint style 2D visualization with grid, room rectangle, and neon-blue breach point."""
    # Create an 800x600 image with dark blue-black background (blueprint style)
    img = Image.new('RGB', (800, 600), color=(15, 20, 30))
    draw = ImageDraw.Draw(img)
    
    # Room dimensions (top-down view)
    room_size = 480
    room_x = (800 - room_size) // 2
    room_y = (600 - room_size) // 2
    
    # Draw clean grid pattern (blueprint style) - lighter blue lines
    grid_color = (0, 100, 150)  # Subtle grid color
    grid_spacing = 40
    
    # Vertical grid lines
    for i in range(room_x, room_x + room_size + 1, grid_spacing):
        draw.line([(i, room_y), (i, room_y + room_size)], fill=grid_color, width=1)
    
    # Horizontal grid lines
    for i in range(room_y, room_y + room_size + 1, grid_spacing):
        draw.line([(room_x, i), (room_x + room_size, i)], fill=grid_color, width=1)
    
    # Draw room rectangle (clean outline, neon blue)
    room_outline_color = (0, 212, 255)  # Neon blue
    draw.rectangle([room_x, room_y, room_x + room_size, room_y + room_size], 
                   outline=room_outline_color, width=2)
    
    # Draw breach point (neon-blue dot at center)
    breach_x = room_x + room_size // 2
    breach_y = room_y + room_size // 2
    
    # Outer glow ring
    draw.ellipse([breach_x - 20, breach_y - 20, breach_x + 20, breach_y + 20], 
                 outline=(0, 212, 255), width=2)
    
    # Main breach point dot (bright neon blue, solid)
    draw.ellipse([breach_x - 8, breach_y - 8, breach_x + 8, breach_y + 8], 
                 fill=(0, 212, 255), outline=(0, 255, 255), width=1)
    
    # Label for breach point
    try:
        label_font = ImageFont.truetype("arial.ttf", 16)
        small_font = ImageFont.truetype("arial.ttf", 12)
    except:
        label_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    # Label text "BREACH POINT" above the dot
    label_text = "BREACH POINT"
    label_bbox = draw.textbbox((0, 0), label_text, font=label_font)
    label_width = label_bbox[2] - label_bbox[0]
    label_x = breach_x - label_width // 2
    label_y = breach_y - 35
    
    # Draw label background (subtle dark rectangle)
    draw.rectangle([label_x - 5, label_y - 3, label_x + label_width + 5, label_y + 18], 
                   fill=(15, 20, 30), outline=(0, 212, 255), width=1)
    draw.text((label_x, label_y), label_text, fill=(0, 212, 255), font=label_font)
    
    # Add blueprint title in top-left corner
    title_text = "FORENSIC BLUEPRINT - TOP VIEW"
    draw.text((room_x + 15, room_y + 15), title_text, 
              fill=(0, 180, 220), font=small_font)
    
    # Add scale indicator in bottom-right corner
    scale_text = "GRID: 40 units"
    scale_bbox = draw.textbbox((0, 0), scale_text, font=small_font)
    scale_width = scale_bbox[2] - scale_bbox[0]
    draw.text((room_x + room_size - scale_width - 15, room_y + room_size - 25), 
              scale_text, fill=(100, 150, 180), font=small_font)
    
    # Save to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    return img_bytes

# Helper functions for case analysis
def analyze_modus_operandi(article):
    """Analyze article to determine Modus Operandi (M.O.)"""
    title = article.get('title', '').lower()
    description = article.get('description', '').lower()
    text = f"{title} {description}"
    
    mo_patterns = {
        'Theft/Burglary': ['theft', 'stolen', 'burglary', 'robbery', 'larceny', 'break-in', 'break in'],
        'Fraud/Scam': ['fraud', 'scam', 'embezzlement', 'identity theft', 'phishing', 'ponzi'],
        'Violence/Assault': ['assault', 'attack', 'violence', 'beating', 'battery', 'aggravated'],
        'Cyber Crime': ['hacking', 'cyber', 'malware', 'ransomware', 'data breach', 'phishing'],
        'Drug Related': ['drug', 'narcotics', 'trafficking', 'dealer', 'cocaine', 'heroin'],
        'Financial Crime': ['money laundering', 'embezzlement', 'tax evasion', 'financial fraud'],
        'Property Crime': ['vandalism', 'arson', 'property damage', 'destruction'],
        'Organized Crime': ['organized', 'syndicate', 'cartel', 'gang', 'mafia']
    }
    
    detected_mo = []
    for mo_type, keywords in mo_patterns.items():
        if any(keyword in text for keyword in keywords):
            detected_mo.append(mo_type)
    
    if detected_mo:
        return detected_mo[0]  # Return first match
    return "Pattern Analysis Required"

def analyze_victimology(article):
    """Analyze article to extract victimology information"""
    title = article.get('title', '').lower()
    description = article.get('description', '').lower()
    text = f"{title} {description}"
    
    victim_patterns = {
        'Individual': ['person', 'individual', 'man', 'woman', 'victim', 'resident', 'citizen'],
        'Business': ['business', 'company', 'store', 'shop', 'restaurant', 'bank', 'retailer'],
        'Financial Institution': ['bank', 'credit union', 'financial', 'atm', 'branch'],
        'Government': ['government', 'municipal', 'city', 'federal', 'agency', 'department'],
        'Educational': ['school', 'university', 'college', 'student', 'campus'],
        'Healthcare': ['hospital', 'clinic', 'medical', 'patient', 'healthcare'],
        'Multiple Victims': ['multiple', 'several', 'many', 'group', 'crowd']
    }
    
    detected_victims = []
    for victim_type, keywords in victim_patterns.items():
        if any(keyword in text for keyword in keywords):
            detected_victims.append(victim_type)
    
    if detected_victims:
        return detected_victims[0]  # Return first match
    return "Analysis Pending"

def determine_kill_chain_stage(article):
    """Determine where the crime falls in the cyber kill chain"""
    title = article.get('title', '').lower()
    description = article.get('description', '').lower()
    text = f"{title} {description}"
    
    # Cyber Kill Chain stages
    kill_chain_stages = [
        'Reconnaissance',
        'Weaponization',
        'Delivery',
        'Exploitation',
        'Installation',
        'Command & Control',
        'Actions on Objectives'
    ]
    
    # Keywords for each stage
    stage_keywords = {
        'Reconnaissance': ['investigating', 'surveillance', 'monitoring', 'gathering', 'research'],
        'Weaponization': ['preparing', 'developing', 'creating', 'building'],
        'Delivery': ['delivered', 'sent', 'transmitted', 'distributed', 'phishing', 'email'],
        'Exploitation': ['exploited', 'breach', 'hacked', 'compromised', 'vulnerability', 'attack'],
        'Installation': ['installed', 'deployed', 'placed', 'established'],
        'Command & Control': ['control', 'remote', 'access', 'command', 'connection'],
        'Actions on Objectives': ['stolen', 'exfiltrated', 'damage', 'disruption', 'theft', 'data breach']
    }
    
    # Score each stage
    stage_scores = {}
    for stage in kill_chain_stages:
        score = sum(1 for keyword in stage_keywords.get(stage, []) if keyword in text)
        stage_scores[stage] = score
    
    # Find the stage with highest score
    if max(stage_scores.values()) > 0:
        max_stage = max(stage_scores, key=stage_scores.get)
        stage_index = kill_chain_stages.index(max_stage)
        return max_stage, stage_index, kill_chain_stages
    else:
        # Default to middle stage if no clear match
        return 'Delivery', 2, kill_chain_stages

# Terminal Boot Logic: Home Screen
active_case = st.session_state.get('active_case', False)

if not active_case:
    # Home Screen: Minimalist neon logo and INITIALIZE INVESTIGATION button
    st.markdown("""
        <style>
        .home-screen {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 70vh;
            text-align: center;
        }
        .neon-logo {
            font-size: 4rem;
            color: #00D4FF;
            text-shadow: 0 0 20px #00D4FF, 0 0 40px #00D4FF, 0 0 60px #00D4FF;
            margin-bottom: 2rem;
            font-weight: 700;
            letter-spacing: 0.2em;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="home-screen">', unsafe_allow_html=True)
    st.markdown('<div class="neon-logo">DIGITAL DETECTIVE</div>', unsafe_allow_html=True)
    st.markdown("<p style='color: #00D4FF; font-size: 1.2rem; margin-bottom: 3rem;'>Evidence Room Generator & Analysis System</p>", unsafe_allow_html=True)
    
    if st.button("🔌 INITIALIZE INVESTIGATION", type="primary", use_container_width=True, key="init_investigation"):
        st.session_state['active_case'] = True
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Minimal sidebar for home screen (only API key)
    with st.sidebar:
        st.header("Configuration")
        secret_key = None
        if 'NEWS_API_KEY' in st.secrets:
            secret_key = st.secrets['NEWS_API_KEY']
        elif hasattr(st.secrets, 'NEWS_API_KEY'):
            secret_key = st.secrets.NEWS_API_KEY
        
        env_api_key = os.getenv('NEWS_API_KEY', '')
        default_key = secret_key if secret_key else (env_api_key if env_api_key else '')
        
        api_key = st.text_input(
            "News API Key",
            value=default_key,
            type="password",
            help="Get your API key from https://newsapi.org/register"
        )
        
        if api_key:
            st.session_state['news_api_key'] = api_key
else:
    # Main application: Title and full sidebar
    st.title("🔍 Digital Detective - Evidence Room Generator")
    st.markdown("<p style='color: #00D4FF; margin-bottom: 2rem;'>3D Evidence Room Generator & Analysis System</p>", unsafe_allow_html=True)

# Sidebar for API key configuration (shown only when active_case is True)
if active_case:
    with st.sidebar:
        st.header("Configuration")
        
        # Try to load API key from Streamlit secrets first (standard for Streamlit apps)
        # Then try environment variable, then user input
        secret_key = None
        if 'NEWS_API_KEY' in st.secrets:
            secret_key = st.secrets['NEWS_API_KEY']
        elif hasattr(st.secrets, 'NEWS_API_KEY'):
            secret_key = st.secrets.NEWS_API_KEY
        
        env_api_key = os.getenv('NEWS_API_KEY', '')
        default_key = secret_key if secret_key else (env_api_key if env_api_key else '')
        
        api_key = st.text_input(
        "News API Key",
        value=default_key,
        type="password",
        help="Get your API key from https://newsapi.org/register. You can also set it in .streamlit/secrets.toml or .env file"
    )
    
    if api_key:
        st.session_state['news_api_key'] = api_key
    
    st.divider()
    st.markdown("### Blender Path")
    default_blender_path = r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
    blender_path = st.text_input(
        "Blender Executable Path",
        value=st.session_state.get('blender_path', default_blender_path),
        help="Path to Blender executable (e.g., 'blender' if in PATH, or full path like 'C:/Program Files/Blender Foundation/Blender 5.0/blender.exe')"
    )
    st.session_state['blender_path'] = blender_path
    
    st.divider()
    st.markdown("### Department (Category)")
    
    # Widget Sync: Use index=0 (Domestic) and key - no manual st.session_state assignments
    # The widget will handle state automatically through the key
    category = st.selectbox(
        "Select Department",
        ["International", "Domestic", "White Collar"],
        index=0,  # Default to Domestic (index 0)
        key="crime_category",
        help="Select the crime category to search for news articles."
    )
    
    st.divider()
    st.markdown("### Threat Level")
    threat_level = st.selectbox(
        "Set Threat Level",
        ["Normal", "Elevated", "High", "Critical"],
        index=0,
        key="threat_level",
        help="Set the threat level for the current case. Critical mode activates pulsing red alert."
    )
    
    st.divider()
    st.markdown("### 🔍 Forensic Findings")
    
    # Display AI Forensic Scan results
    if 'forensic_scan_labels' in st.session_state and st.session_state['forensic_scan_labels'] is not None:
        labels = st.session_state['forensic_scan_labels']
        
        # Check for darkness/black warnings
        has_darkness = any(
            'dark' in label.get('description', '').lower() or 
            'black' in label.get('description', '').lower()
            for label in labels
        )
        
        if has_darkness:
            st.warning("⚠️ WARNING: Scene underexposed. Checking 3D lighting...")
        
        # Display labels with relevance scores
        st.markdown("**AI Vision Detections:**")
        for label in labels[:10]:  # Show top 10 labels
            description = label.get('description', 'Unknown')
            score = label.get('score', 0)
            relevance_score, category = get_relevance_score(description)
            
            # Format display
            confidence_pct = int(score * 100)
            st.markdown(f"• **{description}**")
            st.caption(f"  Confidence: {confidence_pct}% | Relevance: {relevance_score}/100 ({category})")
    
    elif 'forensic_scan_error' in st.session_state and st.session_state['forensic_scan_error']:
        st.error(f"❌ {st.session_state['forensic_scan_error']}")
    else:
        st.info("👆 Generate a render and click 'RUN AI FORENSIC SCAN' to analyze the scene.")
    
    st.divider()
    st.markdown("### ☁️ Cloud Archive")
    
    # Check if there's a current render and render image
    render_image_path_check = EVIDENCE_RENDERS_DIR / "latest_render.png"
    has_render = render_image_path_check.exists()
    has_current_case = 'current_render' in st.session_state and st.session_state['current_render']
    
    if has_render and has_current_case:
        render_info = st.session_state['current_render']
        case_id = f"CASE-{render_info.get('article_idx', 0)}-{int(time.time())}"
        headline = render_info.get('headline', 'Unknown Case')
        
        # Archive button
        if st.button("☁️ ARCHIVE CASE TO CLOUD", use_container_width=True, key="archive_to_cloud"):
            with st.spinner("Uploading case files to Google Drive..."):
                forensic_labels = st.session_state.get('forensic_scan_labels', None)
                results, error = archive_case_to_cloud(
                    render_image_path_check,
                    case_id,
                    headline,
                    forensic_labels
                )
                if error:
                    st.session_state['archive_error'] = error
                    st.session_state['archive_results'] = None
                else:
                    st.session_state['archive_results'] = results
                    st.session_state['archive_error'] = None
                    st.session_state['archive_case_id'] = case_id
            st.rerun()
        
        # Display archive results
        if 'archive_results' in st.session_state and st.session_state['archive_results']:
            st.success("✅ Case archived successfully!")
            results = st.session_state['archive_results']
            st.markdown("**Drive Links:**")
            if 'render' in results:
                st.markdown(f"• [Render Image]({results['render']['link']})")
            if 'findings' in results:
                st.markdown(f"• [Forensic Findings]({results['findings']['link']})")
            if 'archive_case_id' in st.session_state:
                st.caption(f"Case ID: {st.session_state['archive_case_id']}")
        elif 'archive_error' in st.session_state and st.session_state['archive_error']:
            st.error(f"❌ {st.session_state['archive_error']}")
    else:
        st.info("👆 Generate a render to archive cases to the cloud.")
    
    st.divider()
    st.markdown("### 📊 Live Status Log")
    if 'blender_stdout' in st.session_state and st.session_state['blender_stdout']:
        st.code('\n'.join(st.session_state['blender_stdout']), language='text')
    else:
        st.info("No recent Blender output. Generate a render to see status updates.")
    
    st.divider()
    st.markdown("### 🏥 System Health")
    
    # GCP Credit Monitor
    st.markdown('<div class="credit-meter">', unsafe_allow_html=True)
    st.markdown("**GCP Credit Monitor**")
    credit_amount = st.session_state.get('gcp_credits', 300.0)
    st.markdown(f'<div class="credit-amount">${credit_amount:.2f}</div>', unsafe_allow_html=True)
    st.caption("$0.05 deducted per AI scan")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Process Status LEDs
    st.markdown("**Process Status**")
    process_states = st.session_state.get('process_states', {
        'scraper': True,
        'vision_ai': False,
        'blender': False
    })
    
    # SCRAPER: Green (Always on)
    scraper_class = "led-green" if process_states.get('scraper', True) else "led-off"
    st.markdown(f'''
        <div class="process-status-item">
            <span class="led-indicator {scraper_class}"></span>
            <span>SCRAPER</span>
        </div>
    ''', unsafe_allow_html=True)
    
    # VISION AI: Pulsing Blue (Active when scanning)
    vision_class = "led-blue-pulse" if process_states.get('vision_ai', False) else "led-off"
    st.markdown(f'''
        <div class="process-status-item">
            <span class="led-indicator {vision_class}"></span>
            <span>VISION AI</span>
        </div>
    ''', unsafe_allow_html=True)
    
    # BLENDER: Pulsing Orange (Active when rendering)
    blender_class = "led-orange-pulse" if process_states.get('blender', False) else "led-off"
    st.markdown(f'''
        <div class="process-status-item">
            <span class="led-indicator {blender_class}"></span>
            <span>BLENDER</span>
        </div>
    ''', unsafe_allow_html=True)
    
    # Session Counter: Total Cases Archived
    try:
        # Count PDF files in Forensic_Archive directory
        archived_files = list(FORENSIC_ARCHIVE_DIR.glob("*.pdf"))
        total_archived = len(archived_files)
    except Exception:
        total_archived = 0
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**Session Stats**")
    st.metric("Total Cases Archived", total_archived)
    
    st.divider()
    st.markdown("### 📄 Case File Export")
    
    # Check if there's a current case to export
    has_current_case = 'current_render' in st.session_state and st.session_state['current_render']
    has_article = 'articles' in st.session_state and st.session_state['articles']
    
    if has_current_case and has_article:
        render_info = st.session_state['current_render']
        article_idx = render_info.get('article_idx', 0)
        
        if article_idx < len(st.session_state['articles']):
            article = st.session_state['articles'][article_idx]
            case_id = f"CASE-{article_idx}-{int(time.time())}"
            
            # Generate pixel art for PDF
            article_text = f"{article.get('title', '')} {article.get('description', '')}"
            category = st.session_state.get('crime_category', 'Domestic')
            pixel_art_bytes = generate_procedural_pixel_art(article_text, f"CASE-{article_idx}", category=category)
            
            # Check for 3D render
            render_image_path = EVIDENCE_RENDERS_DIR / "latest_render.png"
            render_path_str = str(render_image_path) if render_image_path.exists() else None
            
            # Get forensic labels
            forensic_labels = st.session_state.get('forensic_scan_labels', None)
            
            # Generate PDF
            pdf_bytes, pdf_error = generate_case_pdf(
                case_id=case_id,
                article=article,
                pixel_art_bytes=pixel_art_bytes,
                render_image_path=render_path_str,
                forensic_labels=forensic_labels
            )
            
            if pdf_bytes and not pdf_error:
                # Save PDF to Forensic_Archive folder for local archiving
                pdf_filename = f"{case_id}_Case_File.pdf"
                pdf_path = FORENSIC_ARCHIVE_DIR / pdf_filename
                try:
                    pdf_bytes.seek(0)  # Reset to beginning of BytesIO
                    with open(pdf_path, 'wb') as f:
                        f.write(pdf_bytes.read())
                    pdf_bytes.seek(0)  # Reset again for download button
                except Exception as e:
                    st.warning(f"⚠️ Could not save PDF to archive: {str(e)}")
                
                # Create download button
                st.download_button(
                    label="📄 DOWNLOAD CASE FILE",
                    data=pdf_bytes,
                    file_name=pdf_filename,
                    mime="application/pdf",
                    use_container_width=True,
                    key="download_case_pdf"
                )
                st.caption(f"Exports as: {pdf_filename}")
            elif pdf_error:
                st.error(f"❌ {pdf_error}")
                st.info("💡 Try installing fpdf2: `pip install fpdf2`")
            else:
                st.info("⚠️ PDF generation failed. Check logs for details.")
        else:
            st.info("👆 Generate a render to export case file.")
    else:
        st.info("👆 Generate a render to export case file.")

# Main content area with split layout
if 'news_api_key' not in st.session_state or not st.session_state['news_api_key']:
    st.warning("⚠️ Please enter your News API key in the sidebar to continue.")
    st.info("You can get a free API key at https://newsapi.org/register")
else:
    # Create split layout: 70% Render, 30% Analysis Desk
    render_col, analysis_col = st.columns([0.7, 0.3])
    
    with render_col:
        # Viewfinder container (custom HTML/CSS instead of st.container)
        # Check threat level and inject critical CSS if needed
        threat_level = st.session_state.get('threat_level', 'Normal')
        if threat_level == 'Critical':
            st.markdown("""
                <style>
                /* Critical mode styling for render container */
                .element-container:has(> div > div > div.render-container) {
                    border: 2px solid #FF3131 !important;
                    animation: pulse_red 2s ease-in-out infinite;
                    border-radius: 10px;
                    padding: 2px;
                }
                
                .element-container:has(> div > div > div.render-container) .render-container {
                    border-color: #FF3131 !important;
                    background: linear-gradient(135deg, rgba(255, 49, 49, 0.1), rgba(255, 49, 49, 0.05)) !important;
                }
                
                .element-container:has(> div > div > div.render-container) h3,
                .element-container:has(> div > div > div.render-container) .status-value,
                .element-container:has(> div > div > div.render-container) .kill-chain-active,
                .element-container:has(> div > div > div.render-container) .case-section {
                    color: #FF3131 !important;
                    border-color: #FF3131 !important;
                }
                </style>
            """, unsafe_allow_html=True)
        
        # Viewfinder container with custom HTML
        st.markdown("### 🎨 3D Render View")
        st.markdown('<div class="render-container">', unsafe_allow_html=True)
    
        # Check if there's a current render
        if 'current_render' in st.session_state and st.session_state['current_render']:
            # Display the render if available
            render_info = st.session_state['current_render']
            st.markdown(f"**Active Case:** {render_info.get('headline', 'No case')}")
            st.markdown(f"**Status:** {render_info.get('status', 'Processing')}")
            
            # Check for rendered image (using normalized absolute path)
            render_image_path = EVIDENCE_RENDERS_DIR / "latest_render.png"
            if render_image_path.exists():
                # Add cache buster timestamp to force refresh
                image_path_with_cache = f"{str(render_image_path)}?t={int(time.time())}"
                try:
                    st.image(image_path_with_cache, caption="Forensic Scene Reconstruction", use_container_width=True)
                    st.success("✅ Render image loaded successfully!")
                except Exception as img_error:
                    st.warning(f"⚠️ Image display error: {str(img_error)}")
                    # Fallback: try without cache buster
                    st.image(str(render_image_path), caption="Forensic Scene Reconstruction", use_container_width=True)
                
                # AI Forensic Scan button
                if st.button("🔍 RUN AI FORENSIC SCAN", use_container_width=True, key="run_forensic_scan"):
                    # Activate VISION AI LED
                    process_states = st.session_state.get('process_states', {'scraper': True, 'vision_ai': False, 'blender': False})
                    process_states['vision_ai'] = True
                    st.session_state['process_states'] = process_states
                    
                    with st.spinner("Analyzing forensic scene with AI Vision..."):
                        labels, error = run_forensic_scan(str(render_image_path))
                        if error:
                            st.session_state['forensic_scan_error'] = error
                            st.session_state['forensic_scan_labels'] = None
                        else:
                            st.session_state['forensic_scan_labels'] = labels
                            st.session_state['forensic_scan_error'] = None
                            # Deduct credits for successful scan
                            current_credits = st.session_state.get('gcp_credits', 300.0)
                            st.session_state['gcp_credits'] = max(0.0, current_credits - 0.05)
                    
                    # Deactivate VISION AI LED after scan
                    process_states['vision_ai'] = False
                    st.session_state['process_states'] = process_states
                    st.rerun()
            else:
                # Generate procedural pixel art as preliminary visual evidence
                render_info = st.session_state['current_render']
                article_text = f"{render_info.get('headline', '')} {render_info.get('description', '')}"
                case_id = f"CASE-{render_info.get('article_idx', 0)}"
                category = st.session_state.get('crime_category', 'Domestic')
                st.markdown("### 🎨 Preliminary Visual Evidence")
                pixel_art = generate_procedural_pixel_art(article_text, case_id, category=category)
                st.image(pixel_art, caption="Procedural Pixel Art - Case Analysis", use_container_width=True)
                
                # Refresh View button
                if st.button("🔄 REFRESH VIEW", use_container_width=True, key="refresh_render_view"):
                    st.rerun()
        else:
            # Preliminary Case Report Dashboard
            st.markdown('<div class="case-report">', unsafe_allow_html=True)
            st.markdown("### 📋 Preliminary Case Report")
            
            # Check if there's a selected article
            if 'articles' in st.session_state and st.session_state['articles']:
                # Get selected article index
                selected_idx = st.session_state.get('article_selector', 0)
                if selected_idx is not None and selected_idx < len(st.session_state['articles']):
                    article = st.session_state['articles'][selected_idx]
                    
                    # Generate and display preliminary pixel art visual evidence
                    article_text = f"{article.get('title', '')} {article.get('description', '')}"
                    case_id = f"CASE-{selected_idx}"
                    category = st.session_state.get('crime_category', 'Domestic')
                    st.markdown("### 🎨 Preliminary Visual Evidence")
                    pixel_art = generate_procedural_pixel_art(article_text, case_id, category=category)
                    st.image(pixel_art, caption="Procedural Pixel Art - Case Analysis", use_container_width=True)
                    st.divider()
                    
                    # Analyze the article
                    mo = analyze_modus_operandi(article)
                    victimology = analyze_victimology(article)
                    kill_chain_stage, stage_index, all_stages = determine_kill_chain_stage(article)
                    
                    # Get threat level for conditional styling
                    threat_level = st.session_state.get('threat_level', 'Normal')
                    accent_color = "#FF3131" if threat_level == 'Critical' else "#00D4FF"
                    accent_rgba = "rgba(255, 49, 49, 0.1)" if threat_level == 'Critical' else "rgba(0, 212, 255, 0.1)"
                    
                    # Modus Operandi Section
                    st.markdown('<div class="case-section">', unsafe_allow_html=True)
                    st.markdown("#### 🔍 Modus Operandi (M.O.)")
                    st.markdown(f"""
                    <div style="padding: 1rem; background: {accent_rgba}; border-left: 4px solid {accent_color}; border-radius: 4px; margin: 0.5rem 0;">
                        <p style="color: {accent_color}; font-weight: 600; font-size: 1.1rem; margin: 0;">{mo}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown(f"<p style='color: #B0B0B0; font-size: 0.9rem;'>Based on keyword analysis of the article content and headline.</p>", unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Victimology Section
                    st.markdown('<div class="case-section">', unsafe_allow_html=True)
                    st.markdown("#### 👥 Victimology")
                    st.markdown(f"""
                    <div style="padding: 1rem; background: {accent_rgba}; border-left: 4px solid {accent_color}; border-radius: 4px; margin: 0.5rem 0;">
                        <p style="color: {accent_color}; font-weight: 600; font-size: 1.1rem; margin: 0;">{victimology}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown(f"<p style='color: #B0B0B0; font-size: 0.9rem;'>Victim profile classification based on article analysis.</p>", unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Kill Chain Section
                    st.markdown('<div class="case-section">', unsafe_allow_html=True)
                    st.markdown("#### ⚡ Cyber Kill Chain Analysis")
                    
                    # Calculate progress percentage
                    progress_percentage = int((stage_index + 1) / len(all_stages) * 100)
                    
                    # Display progress bar
                    st.progress(progress_percentage / 100)
                    st.markdown(f"<p style='color: {accent_color}; font-weight: 600; text-align: center; margin: 0.5rem 0;'>{kill_chain_stage} ({progress_percentage}% through chain)</p>", unsafe_allow_html=True)
                    
                    # Display all stages with active stage highlighted
                    st.markdown("<div style='margin-top: 1rem;'>", unsafe_allow_html=True)
                    for idx, stage in enumerate(all_stages):
                        if idx == stage_index:
                            st.markdown(f"""
                            <div class="kill-chain-stage kill-chain-active">
                                <p style="color: {accent_color}; font-weight: 700; margin: 0; font-size: 0.95rem;">
                                    {'→' if idx > 0 else ''} <strong>{stage}</strong> <span style="color: {accent_color}; font-size: 0.8rem;">[CURRENT]</span>
                                </p>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            opacity = "0.4" if idx < stage_index else "0.6"
                            st.markdown(f"""
                            <div class="kill-chain-stage" style="opacity: {opacity};">
                                <p style="color: #B0B0B0; margin: 0; font-size: 0.9rem;">
                                    {'✓' if idx < stage_index else '○'} {stage}
                                </p>
                            </div>
                            """, unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    # No article selected
                    st.markdown('<div class="case-section">', unsafe_allow_html=True)
                    st.markdown("#### 📋 No Case Selected")
                    st.info("👆 Select an article from the Analysis Desk to view the Preliminary Case Report.")
                    st.markdown('</div>', unsafe_allow_html=True)
            else:
                # No articles loaded
                st.markdown('<div class="case-section">', unsafe_allow_html=True)
                st.markdown("#### 📋 No Case Data")
                st.info("👆 Fetch crime news from the Analysis Desk to begin case analysis.")
                st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with analysis_col:
        st.markdown('<div class="analysis-desk">', unsafe_allow_html=True)
        st.markdown("### 🖥️ Analysis Desk")
        
        # Fetch crime news button
        if st.button("🔎 FETCH NEWS", type="primary", use_container_width=True):
            with st.spinner("Fetching crime news..."):
                try:
                    category = st.session_state.get('crime_category', 'Domestic')
                    articles = fetch_crime_news(st.session_state['news_api_key'], category=category)
                    st.session_state['articles'] = articles
                    st.success(f"✅ Found {len(articles)} articles!")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
        
        st.divider()
        
        # Display articles and allow selection
        if 'articles' in st.session_state and st.session_state['articles']:
            st.markdown("#### 📰 Crime News Articles")
            
            # Use a selectbox for article selection
            article_titles = [article.get('title', 'No Title')[:60] + '...' if len(article.get('title', '')) > 60 else article.get('title', 'No Title') 
                            for article in st.session_state['articles']]
            
            selected_idx = st.selectbox(
                "Select Article",
                range(len(article_titles)),
                format_func=lambda x: article_titles[x],
                key="article_selector"
            )
            
            if selected_idx is not None:
                article = st.session_state['articles'][selected_idx]
                
                st.markdown(f"**Source:** {article.get('source', {}).get('name', 'Unknown')}")
                st.markdown(f"**Published:** {article.get('publishedAt', 'Unknown date')[:10] if article.get('publishedAt') else 'Unknown'}")
                st.markdown(f"**Description:**")
                st.markdown(f"<div style='font-size: 0.85rem; color: #B0B0B0;'>{article.get('description', 'No description available')}</div>", unsafe_allow_html=True)
                
                if article.get('url'):
                    st.markdown(f"[📄 Read Full Article]({article['url']})")
                
                st.divider()
                
                # Generate Evidence Room button
                if st.button("🏛️ GENERATE EVIDENCE ROOM", key=f"generate_{selected_idx}", use_container_width=True):
                    headline = article.get('title', 'Evidence Room')
                    description = article.get('description', '')
                    
                    # Activate BLENDER LED
                    process_states = st.session_state.get('process_states', {'scraper': True, 'vision_ai': False, 'blender': False})
                    process_states['blender'] = True
                    st.session_state['process_states'] = process_states
                    
                    with st.spinner("Generating Evidence Room..."):
                        try:
                            # Use reconstruct_scene.py for Forensic Architect (using normalized absolute path)
                            script_path = BASE_DIR / "reconstruct_scene.py"
                            
                            if not script_path.exists():
                                st.error(f"❌ Forensic Architect script not found at: {script_path.absolute()}")
                                st.stop()
                            
                            # Launch Blender in background
                            blender_exe_raw = st.session_state.get('blender_path', r'C:\Program Files\Blender Foundation\Blender 5.0\blender.exe')
                            
                            # Path sanitization: Wrap blender_path with os.path.normpath() for Windows compatibility
                            blender_exe = os.path.normpath(blender_exe_raw)
                            
                            # Ensure .exe extension on Windows if not present
                            if os.name == 'nt' and not blender_exe.endswith('.exe') and not blender_exe.endswith('.bat'):
                                # Check if it's a directory path and append blender.exe
                                if os.path.isdir(blender_exe):
                                    blender_exe = os.path.join(blender_exe, 'blender.exe')
                                elif os.path.exists(blender_exe + '.exe'):
                                    # Path exists if we add .exe
                                    blender_exe = blender_exe + '.exe'
                                blender_exe = os.path.normpath(blender_exe)
                            
                            # HARD-CODE BLENDER VALIDATION: Verify executable exists before running
                            if blender_exe != 'blender':  # Allow 'blender' command if in PATH
                                if not os.path.exists(blender_exe):
                                    st.error(f"❌ Blender Validation Failed: Executable not found at: {blender_exe}")
                                    st.error(f"Please check the Blender path in the sidebar. Current path: {blender_exe_raw}")
                                    st.stop()
                                else:
                                    st.success(f"✅ Blender Validation: Executable found at: {blender_exe}")
                            else:
                                st.info(f"⚠️ Using 'blender' command (assuming it's in system PATH)")
                            
                            # Create command as list with proper argument separation
                            script_path_str = os.path.normpath(str(script_path.absolute()))
                            # Separate --python and script path into distinct strings
                            cmd_list = [
                                blender_exe,
                                '--background',
                                '--factory-startup',
                                '--python',
                                script_path_str,
                                '--'  # Buffer: stop looking for Blender flags
                            ]
                            
                            # Diagnostic: Display the exact command being executed
                            cmd_str_display = ' '.join(cmd_list)
                            st.info(f"🔧 Executing command: `{cmd_str_display}`")
                            
                            # Setup Windows startup info to hide console window
                            startupinfo = None
                            if os.name == 'nt':
                                startupinfo = subprocess.STARTUPINFO()
                                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                                startupinfo.wShowWindow = subprocess.SW_HIDE
                            
                            # Run Blender with timeout and error capture
                            # Wrap in try/except to capture stdout even if it fails
                            result = None
                            try:
                                result = subprocess.run(
                                    cmd_list,
                                    shell=True,  # Set shell=True for Windows to properly initialize executable
                                    capture_output=True,
                                    text=True,
                                    timeout=60,  # Increased timeout for render (EEVEE should be fast, but safety buffer)
                                    startupinfo=startupinfo,
                                    env=os.environ.copy(),  # Environment passthrough
                                    cwd=os.getcwd()  # Ensure it runs in the local project directory, not system root
                                )
                            except subprocess.TimeoutExpired as timeout_error:
                                st.error("❌ Blender process timed out after 60 seconds")
                                st.error(f"Timeout Error: {str(timeout_error)}")
                                if hasattr(timeout_error, 'stdout') and timeout_error.stdout:
                                    st.error("Blender Output (before timeout):")
                                    st.code(timeout_error.stdout, language='text')
                                raise
                            except Exception as subprocess_error:
                                st.error(f"❌ Blender subprocess execution failed: {str(subprocess_error)}")
                                st.error(f"Error Type: {type(subprocess_error).__name__}")
                                # Try to capture any available output
                                if hasattr(subprocess_error, 'stdout') and subprocess_error.stdout:
                                    st.error("Blender Output (on error):")
                                    st.code(subprocess_error.stdout, language='text')
                                raise
                            
                            # After subprocess completes (success or failure), display stdout if it failed
                            if result is None:
                                st.error("❌ Blender subprocess returned None. Execution may have failed.")
                                st.stop()
                            
                            # Display stdout in st.error if subprocess failed (even if returncode != 0)
                            if result.returncode != 0:
                                st.error(f"❌ Blender render failed with return code: {result.returncode}")
                                if result.stdout:
                                    st.error("Blender Standard Output (stdout):")
                                    st.code(result.stdout, language='text')
                                if result.stderr:
                                    st.error("Blender Error Output (stderr):")
                                    st.code(result.stderr, language='text')
                            
                            # Store stdout for Live Status Log (whether success or failure)
                            if result.stdout:
                                stdout_lines = result.stdout.strip().split('\n')
                                st.session_state['blender_stdout'] = stdout_lines[-3:] if len(stdout_lines) > 3 else stdout_lines
                            
                            # Store render info in session state
                            st.session_state['current_render'] = {
                                'headline': headline,
                                'description': description,
                                'status': 'Completed' if result.returncode == 0 else 'Error',
                                'article_idx': selected_idx
                            }
                            
                            # Deactivate BLENDER LED after render completes
                            process_states = st.session_state.get('process_states', {'scraper': True, 'vision_ai': False, 'blender': False})
                            process_states['blender'] = False
                            st.session_state['process_states'] = process_states
                            
                            # Wait handshake: Give file system time to release the image file
                            # Windows sometimes takes a millisecond to "release" the file handle after Blender closes
                            if result.returncode == 0:
                                time.sleep(1)  # Wait protocol: 1 second delay to ensure file system has released the image
                            
                            # Check if the rendered image file exists (using normalized absolute path)
                            image_path = EVIDENCE_RENDERS_DIR / "latest_render.png"
                            
                            # Check for Blender crash/failure
                            if result.returncode != 0:
                                st.error('❌ Blender Crash Detected')
                                if result.stderr:
                                    st.code(result.stderr)
                                if result.stdout:
                                    st.code(result.stdout)
                                # Generate procedural pixel art on error
                                st.warning("⚠️ Generating preliminary visual evidence...")
                                article_text = f"{headline} {description}"
                                case_id = f"CASE-{selected_idx}"
                                category = st.session_state.get('crime_category', 'Domestic')
                                pixel_art = generate_procedural_pixel_art(article_text, case_id, category=category)
                                st.image(pixel_art, caption="Preliminary Visual Evidence - Pixel Art", use_container_width=True)
                                # Set current_render so pixel art shows in render view
                                st.session_state['current_render'] = {
                                    'headline': headline,
                                    'description': description,
                                    'status': 'Blender Error - Using Pixel Art',
                                    'article_idx': selected_idx
                                }
                                st.rerun()
                            else:
                                # Return code is 0, check if image exists
                                if image_path.exists():
                                    st.success("✅ Evidence Room generated successfully!")
                                    # CRITICAL: Set current_render in session state so the render view displays
                                    st.session_state['current_render'] = {
                                        'headline': headline,
                                        'description': description,
                                        'status': 'Complete',
                                        'article_idx': selected_idx
                                    }
                                    # Force immediate rerun to show the render
                                    st.rerun()
                                else:
                                    st.error('❌ Forensic Render Failed. Check Logs below:')
                                    if result.stdout:
                                        st.code(result.stdout)  # This will show us why it didn't save
                                    if result.stderr:
                                        st.code(result.stderr)  # Also show stderr for debugging
                                    # Generate procedural pixel art
                                    st.warning("⚠️ Generating preliminary visual evidence...")
                                    article_text = f"{headline} {description}"
                                    case_id = f"CASE-{selected_idx}"
                                    category = st.session_state.get('crime_category', 'Domestic')
                                    pixel_art = generate_procedural_pixel_art(article_text, case_id, category=category)
                                    st.image(pixel_art, caption="Preliminary Visual Evidence - Pixel Art", use_container_width=True)
                                    # Set current_render even on failure so pixel art shows in render view
                                    st.session_state['current_render'] = {
                                        'headline': headline,
                                        'description': description,
                                        'status': 'Failed - Using Pixel Art',
                                        'article_idx': selected_idx
                                    }
                                    st.rerun()
                            
                            # Note: rerun() is called conditionally above when render succeeds
                            # This prevents double rerun and ensures render view updates correctly
                            
                        except FileNotFoundError:
                            st.error(f"❌ Blender not found at '{blender_exe}'. Check the sidebar.")
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
        else:
            st.info("👆 Click 'FETCH NEWS' to load crime articles")
        
        st.markdown('</div>', unsafe_allow_html=True)


