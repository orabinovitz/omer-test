import streamlit as st
from streamlit_extras.switch_page_button import switch_page
from streamlit_extras.card import card

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
        "name": "Flux Pro",  # Changed from "Flux Pro 1.1"
        "page": "Flux Pro",  # Changed from "Flux Pro 1.1"
        "icon": "🎨",
        "description": "Advanced image generation",
    },
    {
        "name": "Trends Prediction",
        "page": "Trends Prediction",
        "icon": "📈",
        "description": "Predict and analyze trends",
    },
]

# Create columns for the cards
cols = st.columns(len(tools))

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
                "padding": "20px",
                "text-align": "center",
                "cursor": "pointer",
                "height": "250px",
                "box-shadow": "0 4px 6px rgba(0, 0, 0, 0.1)",
                "transition": "all 0.3s ease",
            },
            "title": {
                "font-size": "1.5rem",
                "margin-bottom": "10px",
            },
            "text": {
                "font-size": "1rem",
            },
        },
    )
    if clicked:
        switch_page(tool["page"])

# Display tool cards
for idx, tool in enumerate(tools):
    with cols[idx]:
        create_card(tool)
