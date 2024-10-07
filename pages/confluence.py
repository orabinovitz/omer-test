import streamlit as st
import os
import requests
import json
from requests.auth import HTTPBasicAuth
from bs4 import BeautifulSoup
from io import BytesIO
import toml

# Load secrets
secrets_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".streamlit", "secrets.toml")
with open(secrets_path, "r") as f:
    secrets = toml.load(f)

ATLASSIAN_API_TOKEN = secrets.get('ATLASSIAN_API_TOKEN')
ATLASSIAN_EMAIL = secrets.get('ATLASSIAN_EMAIL')
ATLASSIAN_BASE_URL = secrets.get('ATLASSIAN_BASE_URL')
REVENUE_SPACE_KEY_OR_ID = secrets.get('REVENUE_SPACE_KEY_OR_ID')
OPENAI_API_KEY = secrets.get('OPENAI_API_KEY')

# Authentication for Atlassian API
auth = HTTPBasicAuth(ATLASSIAN_EMAIL, ATLASSIAN_API_TOKEN)

# Headers for Atlassian API
ATLASSIAN_HEADERS = {
    'Accept': 'application/json',
    'Content-Type': 'application/json'
}

# Headers for OpenAI API
OPENAI_HEADERS = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {OPENAI_API_KEY}'
}

def check_secrets():
    required_secrets = [
        'ATLASSIAN_API_TOKEN',
        'ATLASSIAN_EMAIL',
        'ATLASSIAN_BASE_URL',
        'REVENUE_SPACE_KEY_OR_ID',
        'OPENAI_API_KEY'
    ]
    missing_secrets = [var for var in required_secrets if secrets.get(var) is None]
    if missing_secrets:
        st.error(f"Missing required secrets: {', '.join(missing_secrets)}")
        st.stop()

def get_space_id(space_key_or_id):
    if not space_key_or_id:
        st.error("REVENUE_SPACE_KEY_OR_ID is not set. Please check your secrets.")
        return None

    if space_key_or_id.isdigit():
        return space_key_or_id
    else:
        url = f"{ATLASSIAN_BASE_URL}/wiki/api/v2/spaces"
        params = {'keys': space_key_or_id}
        response = requests.get(url, headers=ATLASSIAN_HEADERS, auth=auth, params=params)
        if response.status_code == 200:
            data = response.json()
            spaces = data.get('results', [])
            if spaces:
                return spaces[0].get('id')
            else:
                st.error(f"No spaces found with key: {space_key_or_id}")
                return None
        else:
            st.error(f"Failed to fetch spaces. Please check your Confluence settings.")
            return None

def get_content_id_by_title(space_id, title):
    url = f"{ATLASSIAN_BASE_URL}/wiki/rest/api/content"
    params = {
        "spaceId": space_id,
        "title": title,
        "expand": "version",
        "limit": 1
    }
    response = requests.get(url, headers=ATLASSIAN_HEADERS, auth=auth, params=params)
    if response.status_code == 200:
        data = response.json()
        results = data.get('results', [])
        if results:
            return results[0].get('id')
        else:
            st.error(f"No content found with title: {title}")
            return None
    else:
        st.error(f"Failed to fetch content. Please check your Confluence settings.")
        return None

def get_child_pages(content_id):
    url = f"{ATLASSIAN_BASE_URL}/wiki/rest/api/content/{content_id}/child/page"
    response = requests.get(url, headers=ATLASSIAN_HEADERS, auth=auth)
    if response.status_code == 200:
        data = response.json()
        pages = data.get('results', [])
        return [{'title': page.get('title'), 'id': page.get('id')} for page in pages]
    else:
        st.error(f"Failed to fetch child pages. Please check your Confluence settings.")
        return []

def ask_gpt(prompt):
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0
    }
    response = requests.post(url, headers=OPENAI_HEADERS, json=payload)
    if response.status_code == 200:
        data = response.json()
        return data['choices'][0]['message']['content'].strip()
    else:
        st.error(f"Failed to get response from GPT. Please check your OpenAI settings.")
        return None

def get_page_content(page_id):
    url = f"{ATLASSIAN_BASE_URL}/wiki/rest/api/content/{page_id}"
    params = {'expand': 'body.storage'}
    response = requests.get(url, headers=ATLASSIAN_HEADERS, auth=auth, params=params)
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        st.error(f"Failed to fetch page content. Status Code: {response.status_code}, Response: {response.text}")
        return None

def download_image(url):
    response = requests.get(url, headers=ATLASSIAN_HEADERS, auth=auth)
    if response.status_code == 200:
        return response.content
    else:
        st.error(f"Failed to download image. Status Code: {response.status_code}, Response: {response.text}")
        return None

def main():
    st.title("Campaign Image Finder")

    # Check that all secrets are set
    check_secrets()

    # Get user input
    company_name = st.text_input("Enter the company name:")
    num_campaigns = st.slider("Number of campaigns to pull:", min_value=1, max_value=10, value=3)

    if st.button("Find Campaign Images"):
        if not company_name:
            st.error("Please enter a company name.")
        else:
            with st.spinner('Processing...'):
                try:
                    # Step 1-3: Get space ID, content ID, and categories
                    space_id = get_space_id(REVENUE_SPACE_KEY_OR_ID)
                    if not space_id:
                        st.stop()
                    
                    campaign_examples_id = get_content_id_by_title(space_id, "Campaign Examples")
                    if not campaign_examples_id:
                        st.stop()
                    
                    categories = get_child_pages(campaign_examples_id)
                    if not categories:
                        st.error("No categories found under 'Campaign Examples'.")
                        st.stop()
                    category_names = [category['title'] for category in categories]

                    # Step 4: Use GPT to find the most relevant category
                    categories_str = ', '.join(category_names)
                    prompt = f"The {company_name} brand is most relevant for which category? Choose only 1 and your output should be only the category name without any system text/intro/conclusions. Here is the list of categories: {categories_str}"
                    selected_category = ask_gpt(prompt)
                    if not selected_category:
                        st.stop()

                    # Allow the user to confirm or change the category
                    selected_category = st.selectbox("Select a category:", category_names, index=category_names.index(selected_category) if selected_category in category_names else 0)

                    # Step 5: Access the selected category
                    selected_category_page = next(
                        (cat for cat in categories if cat['title'] == selected_category), None
                    )
                    if not selected_category_page:
                        st.error(f"Could not find category page for '{selected_category}'.")
                        st.stop()
                    selected_category_id = selected_category_page['id']

                    # Step 6: Retrieve brand names from the table
                    page_content = get_page_content(selected_category_id)
                    if not page_content:
                        st.error("Failed to retrieve page content for the selected category.")
                        st.stop()
                    storage = page_content.get('body', {}).get('storage', {}).get('value', '')
                    if not storage:
                        st.error("No storage content found in the page.")
                        st.stop()
                    soup = BeautifulSoup(storage, 'html.parser')
                    table = soup.find('table')
                    if not table:
                        st.error("No table found in the category page.")
                        st.stop()

                    # Extract table headers
                    rows = table.find_all('tr')
                    if not rows:
                        st.error("Table has no rows.")
                        st.stop()
                    headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(['th', 'td'])]

                    try:
                        brand_index = headers.index('brand')
                        preview_index = headers.index('preview')
                    except ValueError as e:
                        st.error("Required columns 'brand' and 'preview' not found in the table headers.")
                        st.stop()

                    # Extract brands and associated preview cells
                    brand_names = []
                    rows_data = []
                    for row in rows[1:]:
                        cells = row.find_all(['td', 'th'])
                        cell_texts = [cell.get_text(strip=True) for cell in cells]
                        if len(cells) < max(brand_index, preview_index) + 1:
                            continue  # Skip rows that don't have enough columns
                        brand_name = cell_texts[brand_index]
                        preview_cell = cells[preview_index]
                        rows_data.append({
                            'brand': brand_name,
                            'preview_cell': preview_cell
                        })
                        brand_names.append(brand_name)

                    # Step 7: Use GPT to find the top N most relevant brands
                    brands_str = ', '.join(brand_names)
                    prompt = (
                        f"The {company_name} brand is most relevant to which {num_campaigns} brands? "
                        f"Choose only {num_campaigns} and your output should be only the brand names separated by commas without any system text/intro/conclusions. "
                        f"Here is the list of brands: {brands_str}"
                    )
                    selected_brands = ask_gpt(prompt)
                    if not selected_brands:
                        st.error("Failed to get brand suggestions.")
                        st.stop()
                    selected_brands_list = [brand.strip() for brand in selected_brands.split(',')]

                    # Allow the user to select brands
                    selected_brands_list = st.multiselect("Select brands to display:", brand_names, default=selected_brands_list)
                    if not selected_brands_list:
                        st.error("Please select at least one brand.")
                        st.stop()

                    # Step 8: Find the rows corresponding to the selected brands
                    selected_rows = [
                        row for row in rows_data if row['brand'] in selected_brands_list
                    ]
                    if not selected_rows:
                        st.error(f"Could not find data for selected brands.")
                        st.stop()

                    # Step 9: Download and display the images
                    for selected_row in selected_rows:
                        preview_cell = selected_row['preview_cell']
                        # Try to find Confluence attachment tags
                        attachment_tags = preview_cell.find_all('ri:attachment')
                        image_data = None
                        filename = None
                        if attachment_tags:
                            for attachment_tag in attachment_tags:
                                filename = attachment_tag.get('ri:filename')
                                if filename:
                                    # Construct the download URL for the attachment
                                    download_url = f"{ATLASSIAN_BASE_URL}/wiki/download/attachments/{selected_category_id}/{filename}"
                                    image_data = download_image(download_url)
                                    if image_data:
                                        break
                        else:
                            # Fallback to previous img and a tag checks
                            img_tag = preview_cell.find('img')
                            if img_tag:
                                src = img_tag.get('src')
                                if src.startswith('/'):
                                    file_url = f"{ATLASSIAN_BASE_URL}{src}"
                                elif src.startswith('http'):
                                    file_url = src
                                else:
                                    file_url = f"{ATLASSIAN_BASE_URL}/{src}"
                                filename = os.path.basename(src.split('?')[0])  # Remove query parameters
                                image_data = download_image(file_url)
                            else:
                                a_tag = preview_cell.find('a')
                                if a_tag:
                                    href = a_tag.get('href')
                                    if href.startswith('/'):
                                        file_url = f"{ATLASSIAN_BASE_URL}{href}"
                                    elif href.startswith('http'):
                                        file_url = href
                                    else:
                                        file_url = f"{ATLASSIAN_BASE_URL}/{href}"
                                    filename = os.path.basename(href.split('?')[0])  # Remove query parameters
                                    image_data = download_image(file_url)
                                else:
                                    st.error(f"No image, attachment, or link found in the 'preview' cell for {selected_row['brand']}.")
                        if image_data:
                            st.write(f"### {selected_row['brand']}")
                            st.image(image_data, use_column_width=True)
                            st.download_button(
                                label="Download Image",
                                data=image_data,
                                file_name=filename or f"{selected_row['brand']}.png",
                                mime="image/png"
                            )
                        else:
                            st.error(f"Failed to retrieve image for {selected_row['brand']}.")
                except Exception as e:
                    st.error("An error occurred. Please try again or contact support if the problem persists.")

if __name__ == "__main__":
    main()