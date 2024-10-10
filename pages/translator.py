import streamlit as st
from streamlit_tags import st_tags
import toml
from anthropic import Anthropic
import os
import sys

# Add utils folder to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
from translator_prompt import PROMPTS

# Load API key from secrets.toml
secrets = toml.load(os.path.join(os.path.dirname(__file__), '..', '.streamlit', 'secrets.toml'))
anthropic_api_key = secrets['ANTHROPIC_API_KEY']

# Initialize Anthropic client
anthropic = Anthropic(api_key=anthropic_api_key)

# Streamlit app configuration
st.set_page_config(page_title="Copy Translator", page_icon="🌐", layout="wide")

st.title("🌐 Copy Translator")

# Input text area for the content to translate
content = st.text_area("Enter the copy content to translate:", height=200)

# Language selection
languages = ["Spanish", "Portuguese", "Mandarin Chinese", "Japanese", "Korean", "French", "German", "Italian", "Arabic", "Hindi"]
language = st.selectbox("Select the output language:", languages)

# Country selection based on language
country_options = {
    "Spanish": ["Argentina", "Mexico", "Spain", "Colombia", "Chile", "Peru"],
    "Portuguese": ["Brazil", "Portugal", "Angola"],
    "Mandarin Chinese": ["China", "Taiwan", "Singapore"],
    "Japanese": ["Japan"],
    "Korean": ["South Korea"],
    "French": ["France", "Canada", "Belgium", "Switzerland"],
    "German": ["Germany", "Austria", "Switzerland"],
    "Italian": ["Italy", "Switzerland"],
    "Arabic": ["Egypt", "Saudi Arabia", "UAE", "Morocco"],
    "Hindi": ["India"]
}

if language in country_options:
    country = st.selectbox("Select the country variant:", country_options[language])
else:
    country = st.text_input("Enter the country variant:")

# Button to trigger translation
if st.button("Translate"):
    if not content.strip():
        st.warning("Please enter the content to translate.")
    else:
        # Get the appropriate prompt
        prompt_template = PROMPTS.get(language)
        if not prompt_template:
            st.error("Prompt for the selected language is not available.")
        else:
            # Fill in the placeholders
            prompt = prompt_template.format(Country=country, content=content)

            # Call the Claude API using the Messages API
            with st.spinner('Translating...'):  # Add this line
                try:
                    response = anthropic.messages.create(
                        model="claude-3-sonnet-20240229",
                        max_tokens=4000,
                        temperature=0.7,
                        system="You are a professional translator.",
                        messages=[
                            {"role": "user", "content": prompt}
                        ]
                    )
                    translated_text = response.content[0].text.strip()
                    st.subheader("Translated Content:")
                    st.write(translated_text)
                except Exception as e:
                    st.error(f"An error occurred during translation: {e}")
