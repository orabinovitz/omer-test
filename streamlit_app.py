import streamlit as st
from streamlit_extras.switch_page_button import switch_page
import math
from collections import defaultdict

# Set page configuration
st.set_page_config(
    page_title="Marketing AI Lab",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed"  # Add this line
)

# Hide Streamlit footer, header, and main menu
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# Add this near the top of your file, where you're setting other styles
st.markdown("""
    <style>
    div.stButton > button {
        width: 100%;
        height: auto;
        min-height: 75px;
        white-space: normal;
        text-align: center;
        margin: 5px 0;
        padding: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# Define tools with categories and hidden keywords
tools = [
    {
        "name": "Upscaler",
        "page": "Upscaler",
        "icon": "🖼️",
        "description": "Enhance image resolution",
        "category": "Creative Tools",
        "keywords": ["image", "enhance", "upscale", "resolution", "images", "photo"],
    },
    {
        "name": "Flux Pro",
        "page": "Flux Pro",
        "icon": "🎨",
        "description": "Advanced image generation",
        "category": "Creative Tools",
        "keywords": ["image", "generation", "creative", "generate images", "flux"],
    },
    {
        "name": "Trends Prediction",
        "page": "Trends Prediction",
        "icon": "📈",
        "description": "Predict and analyze trends",
        "category": "Strategic Tools",
        "keywords": ["trends", "predict", "analyze", "analytics", "data", "strategic", "strategy"],
    },
    {
        "name": "Campaign Image Finder",
        "page": "confluence",
        "icon": "🔗",
        "description": "Find campaign images",
        "category": "Brands",
        "keywords": ["campaign", "images", "brands", "popular pays", "popays", "overview", "confluence"],
    },
    {
        "name": "Popular Keywords",
        "page": "popular_keywords",
        "icon": "🔑",
        "description": "ASO keyword recommendations",
        "category": "AppStore Tools",
        "keywords": ["keywords", "aso", "appstore", "popular"],
    },
    {
        "name": "UI Frame Generator",
        "page": "ui_frames",
        "icon": "📱",
        "description": "Generate UI frames",
        "category": "Creative Tools",
        "keywords": ["ui", "frames", "design", "generate", "interface", "figma"],
    },
    {
        "name": "App Review Analysis",
        "page": "appstore_reviews",
        "icon": "💬",
        "description": "Analyze App Store reviews",
        "category": "AppStore Tools",
        "keywords": ["reviews", "analysis", "appstore", "feedback", "aso", "appfollow"],
    },
    {
        "name": "QR Code Generator",
        "page": "qr_generator",
        "icon": "🔲",
        "description": "Generate QR codes from links",
        "category": "Utilities",
        "keywords": ["qr", "code", "generator", "link", "url", "scan"],
    },
    {
        "name": "Translator",
        "page": "translator",
        "icon": "🌐",
        "description": "Translate copy to multiple languages",
        "category": "Utilities",
        "keywords": ["translate", "language", "copy", "localization", "international"],
    },
    {
        "name": "Brainstorm",
        "page": "brainstorm",
        "icon": "💡",
        "description": "Generate marketing ideas",
        "category": "Strategic Tools",
        "keywords": ["brainstorm", "ideas", "marketing", "creative", "generate", "campaign"],
    },
    # Add more tools as needed
]

# Header
st.markdown("<h1 style='text-align: center;'>🧬 Marketing AI Lab</h1>", unsafe_allow_html=True)

# Search bar
search_query = st.text_input("🔍 Search for a tool...")

# Category filter
categories = sorted(set(tool['category'] for tool in tools))
selected_categories = st.multiselect("Filter by Category", categories, default=categories)

# Function to filter tools
def filter_tools(tools, search_query, selected_categories):
    filtered = []
    for tool in tools:
        if tool['category'] not in selected_categories:
            continue
        if search_query:
            search_content = " ".join([
                tool['name'],
                tool['description'],
                " ".join(tool['keywords'])
            ]).lower()
            if search_query.lower() not in search_content:
                continue
        filtered.append(tool)
    return filtered

filtered_tools = filter_tools(tools, search_query, selected_categories)

# Group tools by category
tools_by_category = defaultdict(list)
for tool in filtered_tools:
    tools_by_category[tool['category']].append(tool)

# Update the display_tool function to remove the description
def display_tool(tool):
    if st.button(f"{tool['icon']} {tool['name']}", key=tool['name']):
        switch_page(tool['page'])

# Update the layout for displaying tools
for category in selected_categories:
    tools_in_category = tools_by_category.get(category, [])
    if tools_in_category:
        st.markdown(f"### {category}")
        
        # Use a more flexible column layout
        cols = st.columns([1, 1, 1, 1])
        
        for i, tool in enumerate(tools_in_category):
            with cols[i % 4]:
                display_tool(tool)
        
        st.markdown("<br>", unsafe_allow_html=True)  # Add some vertical space between categories
