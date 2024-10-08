import os
import sys
import requests
import pandas as pd
import streamlit as st
import toml

# Add parent directory to sys.path (if needed)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Set page configuration
st.set_page_config(
    page_title="ASO Keyword Recommendations",
    page_icon="🔑",
    layout="centered",
)

st.title("🔑 ASO Keyword Recommendations")

st.markdown("""
This app retrieves the top App Store keyword recommendations for **Facetune** in the **US** market using the AppFollow API. The keywords are ranked based on their popularity.
""")

# Get the API key from Streamlit secrets
secrets_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), ".streamlit", "secrets.toml"
)

try:
    with open(secrets_path, "r") as f:
        secrets = toml.load(f)
    api_token = secrets["APPFOLLOW_API_TOKEN"]
except FileNotFoundError:
    st.error(f"Secrets file not found at {secrets_path}")
    st.stop()
except KeyError:
    st.error("API token not found in secrets file")
    st.stop()

# Set the parameters
app_name = "facetune"
country = "us"

# Build the API request URL and headers
url = "https://api.appfollow.io/api/v2/aso/search_ads"
headers = {
    'X-AppFollow-API-Token': api_token
}
params = {
    'app': app_name,
    'country': country
}

# Make the API request
with st.spinner('Fetching keyword recommendations...'):
    response = requests.get(url, headers=headers, params=params)

# Check if request was successful
if response.status_code == 200:
    data = response.json()
    keywords = data['result']['keywords']
    df = pd.DataFrame(keywords)
    df = df.sort_values(by='scoring', ascending=False)
    df.reset_index(drop=True, inplace=True)
    
    # Add a slider for user to select percentage of top keywords
    percentage = st.slider("Select percentage of top keywords to display", 1, 100, 15)
    
    # Calculate number of keywords based on selected percentage
    num_keywords = max(int(len(df) * percentage / 100), 1)  # Ensure at least one keyword
    top_keywords = df.head(num_keywords)
    
    # Display the table
    st.subheader(f"Top {percentage}% Keywords by Popularity")
    st.write(f"Displaying the top {num_keywords} keywords out of {len(df)} total.")
    st.table(top_keywords)

    # Provide download button for full list
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download Full Keyword List as CSV",
        data=csv,
        file_name='keyword_list.csv',
        mime='text/csv',
    )
    # Optionally, show the full keyword list in an expander
    with st.expander("See full keyword list"):
        st.dataframe(df)
else:
    st.error(f"Error: {response.status_code} - {response.text}")
