import streamlit as st
from streamlit_extras.switch_page_button import switch_page
from streamlit_extras.card import card
import math

# Set page configuration
st.set_page_config(
    page_title="Marketing AI Lab",
    page_icon="🧬",
    layout="wide",
)

# Hide Streamlit footer and add custom CSS
st.markdown(
    """
    <style>
    footer {visibility: hidden;}
    .main-header {
        text-align: center;
        color: var(--text-color);
        margin-bottom: 30px;
        font-size: 2.5rem;
    }
    /* Custom card styles */
    .element-container .stCard {
        background-color: #f0f2f6 !important;
    }
    .element-container .stCard:hover {
        border-color: var(--primary-color) !important;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1) !important;
    }
    @media (prefers-color-scheme: dark) {
        .element-container .stCard {
            background-color: #2c3e50 !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("<h1 class='main-header'>🧬 Marketing AI Lab</h1>", unsafe_allow_html=True)

# Define tools
tools = [
    {
        "name": "Upscaler",
        "page": "Upscaler",
        "icon": "🖼️",
        "description": "Enhance image resolution",
    },
    {
        "name": "Flux Pro",
        "page": "Flux Pro",
        "icon": "🎨",
        "description": "Advanced image generation",
    },
    {
        "name": "Trends Prediction",
        "page": "Trends Prediction",
        "icon": "📈",
        "description": "Predict and analyze trends",
    },
    {
        "name": "Confluence",
        "page": "confluence",
        "icon": "🔗",
        "description": "Find campaign images",
    },
    {
        "name": "Popular Keywords",
        "page": "popular_keywords",
        "icon": "🔑",
        "description": "ASO keyword recommendations",
    },
    {
        "name": "UI Frame Generator",
        "page": "ui_frames",
        "icon": "📱",
        "description": "Generate UI frames",
    },
    {
        "name": "App Review Analysis",
        "page": "appstore_reviews",
        "icon": "💬",
        "description": "Analyze App Store reviews",
    },
]

# Update the create_card function
def create_card(tool):
    clicked = card(
        title=f"{tool['icon']} {tool['name']}",
        text=tool['description'],
        key=tool['name'],
        styles={
            "card": {
                "border-radius": "15px",
                "padding": "30px",
                "text-align": "center",
                "cursor": "pointer",
                "height": "100%",
                "transition": "all 0.3s ease",
            },
            "title": {
                "font-size": "1.5rem",
                "margin-bottom": "10px",
                "word-wrap": "break-word",
                "max-width": "100%",
            },
            "text": {
                "font-size": "1rem",
                "word-wrap": "break-word",
                "max-width": "100%",
            },
        },
    )
    if clicked:
        switch_page(tool["page"])

# Calculate the number of rows and columns
num_tools = len(tools)
num_columns = 3
num_rows = math.ceil(num_tools / num_columns)

# Create a grid layout
for row in range(num_rows):
    cols = st.columns(num_columns)
    for col in range(num_columns):
        tool_index = row * num_columns + col
        if tool_index < num_tools:
            with cols[col]:
                create_card(tools[tool_index])
