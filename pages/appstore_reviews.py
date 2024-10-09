import os
import sys
import requests
import pandas as pd
import streamlit as st
import openai
from openai import OpenAI
import toml
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime, timedelta
import json
import base64
from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT

# imports for RAG
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import re

# Add the parent directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Set page configuration
st.set_page_config(
    page_title="App Review Analysis",
    page_icon="💬",
    layout="wide",
)

st.title("💬 App Review Analysis for Facetune")

st.markdown("""
This app retrieves App Store reviews for **Facetune**, analyzes them, and presents the most-loved and least-loved features based on user feedback.
""")

# Get the API keys from Streamlit secrets
secrets_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), ".streamlit", "secrets.toml"
)
if os.path.exists(secrets_path):
    with open(secrets_path, "r") as f:
        secrets = toml.load(f)
    appfollow_api_token = secrets.get("APPFOLLOW_API_TOKEN")
    openai_api_key = secrets.get("OPENAI_API_KEY")
    anthropic_api_key = secrets.get("ANTHROPIC_API_KEY")
    
    if not appfollow_api_token:
        st.error("APPFOLLOW_API_TOKEN is missing in the secrets.toml file.")
        st.stop()
    if not openai_api_key:
        st.error("OPENAI_API_KEY is missing in the secrets.toml file.")
        st.stop()
    if not anthropic_api_key:
        st.error("ANTHROPIC_API_KEY is missing in the secrets.toml file.")
        st.stop()
else:
    st.error("Secrets file not found. Please make sure you have a secrets.toml file in the .streamlit directory.")
    st.stop()

# Set OpenAI API key
openai.api_key = openai_api_key

# Replace OpenAI client setup with Anthropic client
anthropic = Anthropic(api_key=anthropic_api_key)

# Add this near the top of your file, after imports
if 'reviews' not in st.session_state:
    st.session_state.reviews = None
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None
if 'review_texts' not in st.session_state:
    st.session_state.review_texts = None
if 'current_tab' not in st.session_state:
    st.session_state.current_tab = 0
if 'faiss_index' not in st.session_state:
    st.session_state.faiss_index = None
if 'review_embeddings' not in st.session_state:
    st.session_state.review_embeddings = None
if 'embedding_model' not in st.session_state:
    st.session_state.embedding_model = None

# Function to fetch reviews from AppFollow API
def fetch_reviews(ext_id, from_date, to_date, page=1):
    url = "https://api.appfollow.io/api/v2/reviews"
    headers = {
        'X-AppFollow-API-Token': appfollow_api_token
    }
    params = {
        'ext_id': ext_id,
        'from': from_date,
        'to': to_date,
        'page': page
    }
    response = requests.get(url, headers=headers, params=params)
    return response

# Function to paginate through all reviews
def get_all_reviews(ext_id, from_date, to_date, max_reviews=2500):
    reviews = []
    page = 1
    total_fetched = 0
    while total_fetched < max_reviews:
        response = fetch_reviews(ext_id, from_date, to_date, page)
        if response.status_code != 200:
            st.error(f"Error fetching reviews: {response.status_code} - {response.text}")
            return None
        data = response.json()
        review_list = data.get('reviews', {}).get('list', [])
        if not review_list:
            break
        reviews.extend(review_list)
        total_fetched += len(review_list)
        page_info = data.get('reviews', {}).get('page', {})
        if not page_info.get('next'):
            break
        page += 1
    return reviews[:max_reviews]

# Function to create a download link
def get_download_link(data, filename, file_label='File'):
    if isinstance(data, pd.DataFrame):
        csv = data.to_csv(index=False)
        b64 = base64.b64encode(csv.encode()).decode()
    elif isinstance(data, list) or isinstance(data, dict):
        json_str = json.dumps(data, indent=2)
        b64 = base64.b64encode(json_str.encode()).decode()
    else:
        raise ValueError("Unsupported data type for download")
    
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">{file_label}</a>'
    return href

# Define Pydantic models for GPT output
class Feature(BaseModel):
    feature_name: str = Field(..., description="Name of the feature")
    description: str = Field(..., description="Description of how users describe this feature")
    mentions: int = Field(..., description="Number of times this feature is mentioned")

class AnalysisResult(BaseModel):
    most_loved: List[Feature] = Field(..., description="List of most-loved features")
    least_loved: List[Feature] = Field(..., description="List of least-loved features")

# Function to elaborate on a feature
def elaborate_feature(feature_name):
    # Retrieve relevant reviews
    retrieved_reviews = retrieve_reviews(feature_name, k=10)
    # Prepare the prompt
    reviews_text = "\n\n".join(retrieved_reviews)
    user_prompt = f"""
    Please analyze the app reviews below to provide insights into how users perceive the feature "{feature_name}". Your analysis should include:

    - A summary of the general sentiment towards the feature.
    - Specific examples and direct quotes from the reviews that mention this feature.
    - An explanation of any common themes or patterns in user feedback regarding this feature.
    - Any suggestions or requests users have made about this feature.

    Please ensure your response is clear, concise, and focused on the feature "{feature_name}".

    App Reviews:
    {reviews_text}
    """
    try:
        with st.spinner(f'Elaborating on "{feature_name}"...'):
            response = anthropic.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=8000,
                temperature=0.3,
                system="You are a data analyst specializing in app reviews.",
                messages=[{"role": "user", "content": user_prompt}]
            )
            elaboration = response.content[0].text
            return elaboration
    except Exception as e:
        st.error(f"Error elaborating on {feature_name}: {e}")
        return None

# Function to set the current tab and trigger elaboration
def elaborate_and_set_tab(tab_index, feature_name, notification_placeholder):
    st.session_state.current_tab = tab_index
    with notification_placeholder:
        st.info(f'Elaborating on "{feature_name}"...')
    elaboration = elaborate_feature(feature_name)
    st.session_state[f"elaboration_{tab_index}_{feature_name}"] = elaboration
    notification_placeholder.empty()

# Function to generate embeddings and build FAISS index
def build_faiss_index(reviews):
    with st.spinner('Generating embeddings and building FAISS index...'):
        # Initialize the embedding model
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')  # You can choose a different model
        st.session_state.embedding_model = embedding_model
        # Prepare review texts
        review_texts = []
        for i, review in enumerate(reviews):
            content = review.get('translated_content') or review.get('content', '')
            review_texts.append(content)
        # Generate embeddings
        embeddings = embedding_model.encode(review_texts, show_progress_bar=False)
        st.session_state.review_embeddings = embeddings
        # Build FAISS index
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(np.array(embeddings))
        st.session_state.faiss_index = index
        st.session_state.review_texts = review_texts

# Function to retrieve relevant reviews using FAISS
def retrieve_reviews(query, k=5):
    # Generate embedding for the query
    query_embedding = st.session_state.embedding_model.encode([query])
    # Search in the FAISS index
    distances, indices = st.session_state.faiss_index.search(np.array(query_embedding), k)
    indices = indices.flatten()
    # Retrieve the corresponding reviews
    retrieved_reviews = [st.session_state.review_texts[idx] for idx in indices]
    return retrieved_reviews

# Function to analyze reviews using retrieved summaries
def analyze_reviews():
    with st.spinner('Analyzing reviews...'):
        chunk_size = 50
        summaries = []
        for i in range(0, len(st.session_state.review_texts), chunk_size):
            chunk_reviews = st.session_state.review_texts[i:i+chunk_size]
            reviews_text = "\n\n".join(chunk_reviews)
            user_prompt = f"""
            Summarize the key features mentioned in the following app reviews for Facetune. Identify features that are most loved and least loved by users, and provide a brief description for each.

            App Reviews:
            {reviews_text}

            Your response should be a JSON object with "most_loved" and "least_loved" keys, each containing a list of features with their descriptions.
            """
            try:
                response = anthropic.messages.create(
                    model="claude-3-5-sonnet-20240620",
                    max_tokens=4000,
                    temperature=0.5,
                    system="You are a data analyst specializing in app reviews.",
                    messages=[{"role": "user", "content": user_prompt}]
                )
                summary = response.content[0].text.strip()
                summaries.append(summary)
            except Exception as e:
                st.error(f"Error summarizing reviews: {e}")
                return None

        combined_summaries = "\n\n".join(summaries)
        final_prompt = f"""
        Based on the following summaries, provide a consolidated analysis of the most loved and least loved features for the Facetune app.

        Summaries:
        {combined_summaries}

        Your response MUST be a valid JSON object with the following structure:
        {{
            "most_loved": [
                {{"feature_name": "Feature 1", "description": "Description 1", "mentions": 10}},
                {{"feature_name": "Feature 2", "description": "Description 2", "mentions": 8}}
            ],
            "least_loved": [
                {{"feature_name": "Feature 3", "description": "Description 3", "mentions": 5}},
                {{"feature_name": "Feature 4", "description": "Description 4", "mentions": 3}}
            ]
        }}
        Ensure that the JSON is properly formatted and contains only the required information.
        """
        try:
            response = anthropic.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=2000,
                temperature=0.5,
                system="You are a data analyst specializing in app reviews. Always respond with valid JSON.",
                messages=[{"role": "user", "content": final_prompt}]
            )
            response_text = response.content[0].text.strip()
            
            # Try to extract JSON from the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                analysis_result = json.loads(json_str)
            else:
                raise ValueError("No valid JSON found in the response")

            # Validate and store the result
            st.session_state.analysis_result = AnalysisResult(**analysis_result)
        except Exception as e:
            st.error(f"Error in final analysis: {e}")
            st.error("Raw response from AI:")
            st.text(response_text)
            return None

# Get date range from user
st.sidebar.header("Select Date Range for Reviews")
today = datetime.today()

# Define preset options
preset_options = {
    "Last 7 days": timedelta(days=7),
    "Last 30 days": timedelta(days=30),
    "Last 90 days": timedelta(days=90),
    "Last 12 months": timedelta(days=365),
    "Custom range": None
}

# Add preset selector
selected_preset = st.sidebar.selectbox("Choose a preset or custom range", list(preset_options.keys()))

if selected_preset == "Custom range":
    default_from = today - timedelta(days=30)  # Default to 30 days ago
    from_date = st.sidebar.date_input("From", default_from)
    to_date = st.sidebar.date_input("To", today, min_value=from_date)
else:
    to_date = today
    from_date = today - preset_options[selected_preset]

if from_date > to_date:
    st.sidebar.error("Error: 'From' date must be before 'To' date.")

# Fetch and analyze reviews when button is clicked
if st.button("Analyze Reviews"):
    ext_id = "1149994032"  # Facetune app ID
    from_date_str = from_date.strftime("%Y-%m-%d")
    to_date_str = to_date.strftime("%Y-%m-%d")
    
    with st.spinner('Fetching and processing reviews...'):
        st.session_state.reviews = get_all_reviews(ext_id, from_date_str, to_date_str, max_reviews=2500)
    
    if st.session_state.reviews:
        # Create download links
        st.markdown(get_download_link(st.session_state.reviews, "facetune_reviews.json", "📄 Download JSON"), unsafe_allow_html=True)
        
        # Convert to DataFrame for CSV download
        df = pd.DataFrame(st.session_state.reviews)
        st.markdown(get_download_link(df, "facetune_reviews.csv", "📄 Download CSV"), unsafe_allow_html=True)
        
        # Build FAISS index
        build_faiss_index(st.session_state.reviews)
        
        # Analyze reviews
        analyze_reviews()

        # Removed the success message:
        # if st.session_state.analysis_result:
        #     st.success("Analysis completed successfully!")
    else:
        st.error("No reviews found for the selected date range. Please check the API response above for more details.")

# Display results
if st.session_state.analysis_result and st.session_state.review_texts:
    st.header("App Review Analysis Results")
    
    tab1, tab2 = st.tabs(["Most Loved Features", "Least Loved Features"])
    
    def display_features(features, tab, tab_index):
        # Sort features by mentions in descending order
        sorted_features = sorted(features, key=lambda x: x.mentions, reverse=True)
        
        for i, feature in enumerate(sorted_features):
            tab.subheader(feature.feature_name)
            tab.write(f"**Description:** {feature.description}")
            tab.write(f"**Mentions:** {feature.mentions}")
            
            elaboration_key = f"elaboration_{tab_index}_{feature.feature_name}"
            
            # Create a placeholder for the elaboration notification
            notification_placeholder = tab.empty()
            
            if elaboration_key not in st.session_state:
                if tab.button('Elaborate', key=f"elaborate_{tab_index}_{i}", on_click=elaborate_and_set_tab, args=(tab_index, feature.feature_name, notification_placeholder)):
                    pass  # The actual elaboration is handled in the callback
            
            if elaboration_key in st.session_state:
                with tab.expander("See detailed analysis", expanded=True):
                    st.write(st.session_state[elaboration_key])
            
            tab.markdown("---")  # Add a separator between features
    
    # Display content for both tabs
    with tab1:
        display_features(st.session_state.analysis_result.most_loved, tab1, 0)
    
    with tab2:
        display_features(st.session_state.analysis_result.least_loved, tab2, 1)