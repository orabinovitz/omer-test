# pages/trends_prediction.py

import streamlit as st
from auth import check_auth

# Check authentication
check_auth()

import os
import json
import requests
import csv
import aiohttp
import asyncio
import logging
from datetime import datetime, timedelta
import sys
import subprocess
import toml
import pandas as pd
from serpapi import GoogleSearch
from bs4 import BeautifulSoup
# Configure logging
logging.basicConfig(level=logging.INFO)

# Set page configuration
st.set_page_config(
    page_title="Trends Prediction Tool",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Trends Prediction Tool")

# Hide Streamlit footer and add custom CSS
st.markdown(
    """
    <style>
    footer {visibility: hidden;}
    .css-18e3th9 {padding-top: 2rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

# Get API keys from Streamlit secrets
secrets_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.streamlit', 'secrets.toml')
with open(secrets_path, 'r') as f:
    secrets = toml.load(f)
serpapi_key = secrets.get("SERPAPI_KEY")
openai_key = secrets.get("OPENAI_API_KEY")

# Check if API keys are available
if not serpapi_key or not openai_key:
    st.error("API keys for SerpApi and OpenAI are required. Please add them to your Streamlit secrets.")
    st.stop()

# Initialize session state
if 'trends_list' not in st.session_state:
    st.session_state['trends_list'] = []
if 'processed_trends' not in st.session_state:
    st.session_state['processed_trends'] = []
if 'trend_summaries' not in st.session_state:
    st.session_state['trend_summaries'] = []
if 'filtered_trends' not in st.session_state:
    st.session_state['filtered_trends'] = []

# Set search_term to always be "trend"
search_term = "trend"

# User Inputs
st.sidebar.header("Search Parameters")

date_option = st.sidebar.selectbox(
    "Date Range",
    options=["Last 4 days", "Last 7 days", "Last 30 days", "Custom Range"],
    help="Select the date range for the trends data.",
)

geo_location = st.sidebar.selectbox(
    "Geographical Location",
    options=["United States", "United Kingdom", "Canada", "Australia", "Worldwide"],
    index=0,
    help="Select the geographical location for the trends data.",
)

if date_option == "Custom Range":
    start_date = st.sidebar.date_input("Start Date", datetime.now() - timedelta(days=7))
    end_date = st.sidebar.date_input("End Date", datetime.now())
    if start_date > end_date:
        st.sidebar.error("Start date must be before end date.")
        st.stop()
else:
    end_date = datetime.now()
    if date_option == "Last 4 days":
        start_date = end_date - timedelta(days=4)
    elif date_option == "Last 7 days":
        start_date = end_date - timedelta(days=7)
    elif date_option == "Last 30 days":
        start_date = end_date - timedelta(days=30)

start_date_str = start_date.strftime("%Y-%m-%d")
end_date_str = end_date.strftime("%Y-%m-%d")

# Map geo location to country code
geo_location_map = {
    "United States": "US",
    "United Kingdom": "GB",
    "Canada": "CA",
    "Australia": "AU",
    "Worldwide": "",
}
geo_code = geo_location_map.get(geo_location, "US")

# Run Button
if st.sidebar.button("🔍 Run Analysis"):
    with st.spinner("Fetching trends..."):
        # Perform Google Trends search
        search_params = {
            "engine": "google_trends",
            "q": search_term,
            "data_type": "RELATED_QUERIES",
            "date": f"{start_date_str} {end_date_str}",
            "geo": geo_code,
            "api_key": serpapi_key,
        }
        search = GoogleSearch(search_params)
        result = search.get_dict()

        if 'related_queries' in result:
            rising_queries = result['related_queries'].get('rising', [])
            st.session_state['trends_list'] = [query['query'] for query in rising_queries]

    if st.session_state['trends_list']:
        st.success(f"Found {len(st.session_state['trends_list'])} trends.")
        with st.expander("Initial Trends", expanded=False):
            st.table(pd.DataFrame(st.session_state['trends_list'], columns=["Trend"]))
    else:
        st.warning("No trends found.")
        st.stop()

    # Process trends with GPT
    with st.spinner("Processing trends with GPT..."):
        prompt = f"""Analyze this list of Google Trends queries and consolidate them into main trends. Follow these rules:
1. Combine similar trends (e.g., "demure trend" and "very demure trend" should be combined).
2. Remove percentage values and "Breakout" mentions.
3. If a trend asks "what is...", remove that part and just list the trend itself.
4. List only the top 10 unique trends, ordered from most to least significant.
5. Do not include any explanations or additional text.

Format the output as a numbered list:
1. Trend 1
2. Trend 2
3. Trend 3
...

Here is the list to analyze: {st.session_state['trends_list']}"""

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai_key}"
        }

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json={
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }
        )

        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content'].strip()
            st.session_state['processed_trends'] = [line.split('. ', 1)[1] if '. ' in line else line for line in content.split('\n') if line]
            st.success("Trends processed.")
        else:
            st.error("Error processing trends with GPT.")
            st.stop()

    with st.expander("Processed Trends", expanded=False):
        st.table(pd.DataFrame(st.session_state['processed_trends'], columns=["Trend"]))

    # Summarize content for each trend
    async def summarize_trend(trend):
        search_results = await get_search_results(trend)
        contents = await fetch_contents(search_results)
        combined_content = " ".join(contents)
        summary = await summarize_with_gpt(combined_content, trend)
        return {"name": trend, "summary": summary}

    async def get_search_results(trend):
        params = {
            "engine": "google",
            "q": trend,
            "gl": geo_code,
            "api_key": serpapi_key,
        }
        search = GoogleSearch(params)
        results = search.get_dict()
        links = []
        if 'organic_results' in results:
            for result in results['organic_results'][:5]:
                link = result.get('link')
                if link and 'youtube.com' not in link:
                    links.append(link)
        return links

    async def fetch_contents(urls):
        async with aiohttp.ClientSession() as session:
            tasks = []
            for url in urls:
                tasks.append(fetch_content(session, url))
            contents = await asyncio.gather(*tasks)
        return [content for content in contents if content]

    async def fetch_content(session, url):
        try:
            async with session.get(url, timeout=10) as response:
                text = await response.text()
                soup = BeautifulSoup(text, 'html.parser')
                return soup.get_text()
        except:
            return None

    async def summarize_with_gpt(content, trend_name):
        prompt = f"""Read this content and write a short 200 words long summary for the trend "{trend_name}". 
Format the output as a JSON object with 'name' and 'summary' fields, like this:
{{
  "name": "{trend_name}",
  "summary": "Your 200-word summary here"
}}
Provide only the JSON object, without any additional text or explanation."""

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai_key}"
        }

        response = await asyncio.to_thread(requests.post,
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json={
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }
        )

        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content'].strip()
            try:
                result = json.loads(content)
                return result['summary']
            except json.JSONDecodeError:
                return "Summary not available."
        else:
            return "Summary not available."

    # Process trends and generate summaries
    with st.spinner("Generating summaries..."):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tasks = [summarize_trend(trend) for trend in st.session_state['processed_trends']]
        st.session_state['trend_summaries'] = loop.run_until_complete(asyncio.gather(*tasks))
        loop.close()
        st.success("Summaries generated.")

    with st.expander("Trend Summaries", expanded=False):
        summaries_df = pd.DataFrame(st.session_state['trend_summaries'])
        st.table(summaries_df)

    # Filter trends with GPT
    with st.spinner("Filtering trends for Facetune..."):
        prompt = """Review these trends and their summaries. Identify which of these trends will be relevant for a marketing campaign for the Facetune App that has an audience that is interested in: Fashion, Makeup, Beauty, Pop Culture, Viral Trends, Social Media, Retouching, Body Care, Cosmetics, Hair Care, Fitness, Celebs, Gossip, Tabloids, Entertainment News, Influencer Culture, Wellness and Self-Care, Creative Expression, Photography and Editing. Remove anything not related, and anything that is not a current trending topic. Return only the relevant trends in the same format. If there are no relevant trends, return an empty list."""

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(st.session_state['trend_summaries'])}
        ]

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai_key}"
        }

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json={
                "model": "gpt-3.5-turbo",
                "messages": messages,
                "temperature": 0.3
            }
        )

        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content'].strip()
            try:
                st.session_state['filtered_trends'] = json.loads(content)
                st.success("Trends filtered.")
            except json.JSONDecodeError:
                st.session_state['filtered_trends'] = []
                st.warning("No relevant trends found or error in GPT response.")
        else:
            st.error("Error filtering trends with GPT.")
            st.stop()

    if st.session_state['filtered_trends']:
        st.write("### Relevant Marketing Trends for Facetune")
        filtered_df = pd.DataFrame(st.session_state['filtered_trends'])
        st.table(filtered_df)
    else:
        st.info("No relevant trends found for Facetune.")

    # Download Options
    st.write("### Download Results")
    csv1 = summaries_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Trend Summaries CSV",
        data=csv1,
        file_name='trend_summaries.csv',
        mime='text/csv',
    )

    if st.session_state['filtered_trends']:
        csv2 = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Filtered Trends CSV",
            data=csv2,
            file_name='filtered_trends.csv',
            mime='text/csv',
        )

else:
    st.info("Adjust the search parameters and click 'Run Analysis' to start.")
