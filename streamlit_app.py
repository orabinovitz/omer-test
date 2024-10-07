from auth import check_auth

# Check authentication
check_auth()

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
        color: #ceeafd;
        margin-bottom: 30px;
        font-size: 2.5rem;
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
]

# Function to create a card with a clickable action
def create_card(tool):
    clicked = card(
        title=f"{tool['icon']} {tool['name']}",
        text=tool['description'],
        key=tool['name'],
        styles={
            "card": {
                "background-color": "#1e2d41",
                "color": "#ceeafd",
                "border-radius": "15px",
                "padding": "30px",
                "text-align": "center",
                "cursor": "pointer",
                "height": "100%",  # Changed to 100% to fill the column
                "box-shadow": "0 4px 6px rgba(0, 0, 0, 0.1)",
                "transition": "all 0.3s ease",
                "display": "flex",
                "flex-direction": "column",
                "justify-content": "center",
                "align-items": "center",
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

# Add custom CSS for responsiveness
st.markdown("""
<style>
    /* Default styles for horizontal layout */
    .stHorizontalBlock {
        display: flex;
        flex-direction: row;
        gap: 1rem;
    }
    .stHorizontalBlock > div {
        flex: 1;
    }
    
    /* Responsive styles for vertical layout */
    @media (max-width: 1200px) {
        .stHorizontalBlock {
            flex-direction: column;
            gap: 0;
        }
        .stHorizontalBlock > div {
            width: 100% !important;
        }
        /* Target the specific elements that wrap our cards */
        .stHorizontalBlock > div > div > div {
            margin-bottom: 0.5rem !important;
        }
        /* Remove extra padding from column containers */
        .css-1r6slb0 {
            padding: 0 !important;
        }
        /* Adjust card container spacing */
        .css-1r6slb0 > div {
            margin-bottom: 0.5rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)
