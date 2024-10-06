import streamlit as st
from streamlit_extras.card import card

# Set page configuration
st.set_page_config(
    page_title="My AI Tools Hub",
    page_icon="🚀",
    layout="centered",
)

# Hide Streamlit footer and add custom CSS
st.markdown(
    """
    <style>
    footer {visibility: hidden;}
    .main-header {text-align: center;}
    .card {
        background-color: #f9f9f9;
        border-radius: 10px;
        padding: 20px;
        margin: 10px;
        text-align: center;
        cursor: pointer;
        transition: transform 0.2s;
    }
    .card:hover {
        transform: scale(1.02);
    }
    .cards-container {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("<h1 class='main-header'>🚀 My AI Tools Hub</h1>", unsafe_allow_html=True)

# Define tools
tools = [
    {"name": "Upscaler", "page": "Upscaler", "icon": "🖼️"},
    {"name": "Flux Pro 1.1", "page": "Flux Pro 1.1", "icon": "🎨"},
]

# Display tool cards
st.markdown("<div class='cards-container'>", unsafe_allow_html=True)

for tool in tools:
    st.markdown(
        f"""
        <div class="card" onclick="window.location.href='/{tool['page'].replace(' ', '%20')}'">
            <h2>{tool['icon']} {tool['name']}</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("</div>", unsafe_allow_html=True)
