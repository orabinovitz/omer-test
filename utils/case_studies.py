from difflib import get_close_matches
from typing import Any, Dict, List, Optional
import base64
import logging
import os

from bs4 import BeautifulSoup
from requests.auth import HTTPBasicAuth
import requests

from config import settings

logger = logging.getLogger(__name__)

# Confluence API credentials
ATLASSIAN_API_TOKEN = settings.ATLASSIAN_API_KEY
ATLASSIAN_EMAIL = "tfactor@lightricks.com"
ATLASSIAN_BASE_URL = "https://popularpays.atlassian.net"
REVENUE_SPACE_KEY_OR_ID = "18514037"

# Authentication and headers setup
auth = HTTPBasicAuth(ATLASSIAN_EMAIL, ATLASSIAN_API_TOKEN)
ATLASSIAN_HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}
OPENAI_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
}


def get_space_id(space_key_or_id: str) -> Optional[str]:
    """Get the Confluence space ID from a key or ID."""
    if not space_key_or_id:
        logger.error("REVENUE_SPACE_KEY_OR_ID is not set.")
        return None

    if space_key_or_id.isdigit():
        return space_key_or_id
    else:
        url = f"{ATLASSIAN_BASE_URL}/wiki/api/v2/spaces"
        params = {"keys": space_key_or_id}
        response = requests.get(url, headers=ATLASSIAN_HEADERS, auth=auth, params=params)
        if response.status_code == 200:
            data = response.json()
            spaces = data.get("results", [])
            if spaces:
                return spaces[0].get("id")
            else:
                logger.error(f"No spaces found with key: {space_key_or_id}")
                return None
        else:
            logger.error("Failed to fetch spaces. Please check your Confluence settings.")
            return None


def get_content_id_by_title(space_id: str, title: str) -> Optional[str]:
    """Get content ID by title in a given space."""
    url = f"{ATLASSIAN_BASE_URL}/wiki/rest/api/content"
    params = {"spaceId": space_id, "title": title, "expand": "version", "limit": 1}
    response = requests.get(url, headers=ATLASSIAN_HEADERS, auth=auth, params=params)
    if response.status_code == 200:
        data = response.json()
        results = data.get("results", [])
        if results:
            return results[0].get("id")
        else:
            logger.error(f"No content found with title: {title}")
            return None
    else:
        logger.error("Failed to fetch content. Please check your Confluence settings.")
        return None


def get_child_pages(content_id: str) -> List[Dict[str, str]]:
    """Get child pages of a Confluence page."""
    url = f"{ATLASSIAN_BASE_URL}/wiki/rest/api/content/{content_id}/child/page"
    response = requests.get(url, headers=ATLASSIAN_HEADERS, auth=auth)
    if response.status_code == 200:
        data = response.json()
        pages = data.get("results", [])
        return [{"title": page.get("title"), "id": page.get("id")} for page in pages]
    else:
        logger.error("Failed to fetch child pages. Please check your Confluence settings.")
        return []


def get_page_content(page_id: str) -> Optional[Dict[str, Any]]:
    """Get the content of a Confluence page."""
    url = f"{ATLASSIAN_BASE_URL}/wiki/rest/api/content/{page_id}"
    params = {"expand": "body.storage"}
    response = requests.get(url, headers=ATLASSIAN_HEADERS, auth=auth, params=params)
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        logger.error(
            f"Failed to fetch page content. Status Code: {response.status_code},"
            f"Response: {response.text}"
        )
        return None


def download_image(url: str) -> Optional[bytes]:
    """Download an image from Confluence."""
    response = requests.get(url, headers=ATLASSIAN_HEADERS, auth=auth)
    if response.status_code == 200:
        return response.content
    else:
        logger.error(
            f"Failed to download image. Status Code: {response.status_code},"
            f"Response: {response.text}"
        )
        return None


def find_closest_matches(suggestions: List[str], options: List[str], n: int = 1) -> List[str]:
    """Find closest matching strings."""
    closest_matches = []
    for suggestion in suggestions:
        matches = get_close_matches(suggestion, options, n=n, cutoff=0.6)
        if matches:
            closest_matches.extend(matches)
    return list(set(closest_matches))  # Remove duplicates


def analyze_image_with_gpt_vision(image_data: bytes, company_name: str) -> str:
    """Analyze an image using GPT-4.5 Vision to extract case study information."""
    try:
        # Convert image data to base64
        base64_image = base64.b64encode(image_data).decode("utf-8")

        # Prepare the prompt for GPT-4.5 Vision
        prompt = f"""
        This is a case study image for a Popular Pays marketing campaign. 
        
        Please extract and summarize the key details from this image including:
        1. The client/brand featured in the case study
        2. Key performance metrics (e.g., engagement rate, ROI, reach)
        3. Campaign strategy used
        4. Target audience if mentioned
        5. Any specific successful tactics mentioned
        
        Format this as a concise summary that could be referenced when discussing with {company_name}.
        Only include factual information visible in the image, don't make up details.
        """

        # Prepare the API call to OpenAI
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": "gpt-4.5-preview",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ],
                }
            ],
            "max_tokens": 800,
        }

        response = requests.post(url, headers=OPENAI_HEADERS, json=payload)
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        else:
            logger.error(f"Error calling GPT Vision API: {response.status_code}, {response.text}")
            return "Failed to analyze case study image."

    except Exception as e:
        logger.error(f"Error in analyze_image_with_gpt_vision: {str(e)}")
        return "Error analyzing case study image."


def determine_relevant_category(company_name: str, category_names: List[str]) -> str:
    """Determine the most relevant category for a company."""
    # Use GPT to determine the relevant category
    url = "https://api.openai.com/v1/chat/completions"

    categories_str = ", ".join(category_names)
    prompt = (
        f"Given information about {company_name}, "
        f"which category is most relevant? Choose only 1 and your output should "
        f"be only the category name without any additional text. "
        f"Here is the list of categories: {categories_str}"
    )

    payload = {
        "model": "gpt-4.5-preview",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }

    response = requests.post(url, headers=OPENAI_HEADERS, json=payload)
    if response.status_code == 200:
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    else:
        logger.error(f"Failed to get category from GPT: {response.status_code}")
        return category_names[0]  # Return the first category as fallback


def determine_relevant_brands(
    company_name: str, brand_names: List[str], num_brands: int = 3
) -> List[str]:
    """Determine the most relevant brands for a company."""
    url = "https://api.openai.com/v1/chat/completions"

    brands_str = ", ".join(brand_names)
    prompt = (
        f"The {company_name} brand is most relevant to which {num_brands} brands? "
        f"Choose only {num_brands} and your output should be only the brand "
        f"names separated by commas without any additional text. "
        f"Here is the list of brands: {brands_str}"
    )

    payload = {
        "model": "gpt-4.5-preview",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }

    response = requests.post(url, headers=OPENAI_HEADERS, json=payload)
    if response.status_code == 200:
        data = response.json()
        selected_brands = data["choices"][0]["message"]["content"].strip()
        selected_brands_list = [brand.strip() for brand in selected_brands.split(",")]
        return selected_brands_list
    else:
        logger.error(f"Failed to get brand suggestions from GPT: {response.status_code}")
        return brand_names[:num_brands]  # Return the first num_brands as fallback


def get_relevant_case_studies(company_name: str, num_case_studies: int = 3) -> List[Dict[str, Any]]:
    """
    Fetch relevant case studies for a company from Confluence.

    Args:
        company_name: The name of the company to find relevant case studies for
        num_case_studies: Number of case studies to retrieve (default: 3)

    Returns:
        List of dictionaries containing case study information:
        - brand: Name of the brand
        - image_data: Raw binary image data
        - image_analysis: Text analysis of the image by GPT Vision
        - filename: Name of the image file
    """
    case_studies = []

    try:
        # Step 1: Get space ID
        space_id = get_space_id(REVENUE_SPACE_KEY_OR_ID)
        if not space_id:
            logger.error("Failed to get space ID")
            return case_studies

        # Step 2: Get Campaign Examples page
        campaign_examples_id = get_content_id_by_title(space_id, "Campaign Examples")
        if not campaign_examples_id:
            logger.error("Failed to find Campaign Examples page")
            return case_studies

        # Step 3: Get categories
        categories = get_child_pages(campaign_examples_id)
        if not categories:
            logger.error("No categories found under Campaign Examples")
            return case_studies

        category_names = [category["title"] for category in categories]

        # Step 4: Determine relevant category
        selected_category = determine_relevant_category(company_name, category_names)

        # Step 5: Get the selected category page
        selected_category_page = next(
            (cat for cat in categories if cat["title"] == selected_category), None
        )

        if not selected_category_page:
            # Fallback to first category
            selected_category_page = categories[0]

        selected_category_id = selected_category_page["id"]

        # Step 6: Get brands from the table
        page_content = get_page_content(selected_category_id)
        if not page_content:
            logger.error("Failed to get page content")
            return case_studies

        storage = page_content.get("body", {}).get("storage", {}).get("value", "")
        if not storage:
            logger.error("No storage content found")
            return case_studies

        soup = BeautifulSoup(storage, "html.parser")
        table = soup.find("table")
        if not table:
            logger.error("No table found in category page")
            return case_studies

        # Extract table headers
        rows = table.find_all("tr")
        if not rows:
            logger.error("Table has no rows")
            return case_studies

        headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]

        try:
            brand_index = headers.index("brand")
            preview_index = headers.index("preview")
        except ValueError:
            logger.error("Required columns not found in table headers")
            return case_studies

        # Extract brands and preview cells
        brand_names = []
        rows_data = []
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            cell_texts = [cell.get_text(strip=True) for cell in cells]
            if len(cells) < max(brand_index, preview_index) + 1:
                continue

            brand_name = cell_texts[brand_index]
            preview_cell = cells[preview_index]
            rows_data.append({"brand": brand_name, "preview_cell": preview_cell})
            brand_names.append(brand_name)

        # Step 7: Find relevant brands
        relevant_brands = determine_relevant_brands(company_name, brand_names, num_case_studies)
        selected_brand_names = find_closest_matches(relevant_brands, brand_names)

        # Step 8: Get case studies for selected brands
        selected_rows = [row for row in rows_data if row["brand"] in selected_brand_names]

        # Step 9: Process images for the selected brands
        for selected_row in selected_rows:
            preview_cell = selected_row["preview_cell"]
            brand_name = selected_row["brand"]

            # Try to find attachment
            attachment_tags = preview_cell.find_all("ri:attachment")
            image_data = None
            filename = None

            if attachment_tags:
                for attachment_tag in attachment_tags:
                    filename = attachment_tag.get("ri:filename")
                    if filename:
                        download_url = f"{ATLASSIAN_BASE_URL}/wiki/download/attachments/{selected_category_id}/{filename}"
                        image_data = download_image(download_url)
                        if image_data:
                            break
            else:
                # Try to find img tag
                img_tag = preview_cell.find("img")
                if img_tag:
                    src = img_tag.get("src")
                    if src.startswith("/"):
                        file_url = f"{ATLASSIAN_BASE_URL}{src}"
                    elif src.startswith("http"):
                        file_url = src
                    else:
                        file_url = f"{ATLASSIAN_BASE_URL}/{src}"

                    filename = os.path.basename(src.split("?")[0])
                    image_data = download_image(file_url)
                else:
                    # Try to find a tag with href
                    a_tag = preview_cell.find("a")
                    if a_tag:
                        href = a_tag.get("href")
                        if href.startswith("/"):
                            file_url = f"{ATLASSIAN_BASE_URL}{href}"
                        elif href.startswith("http"):
                            file_url = href
                        else:
                            file_url = f"{ATLASSIAN_BASE_URL}/{href}"

                        filename = os.path.basename(href.split("?")[0])
                        image_data = download_image(file_url)

            if image_data:
                # Analyze the image content
                image_analysis = analyze_image_with_gpt_vision(image_data, company_name)

                case_studies.append(
                    {
                        "brand": brand_name,
                        "image_data": image_data,
                        "image_analysis": image_analysis,
                        "filename": filename or f"{brand_name}.png",
                    }
                )

    except Exception as e:
        logger.error(f"Error fetching case studies: {str(e)}")

    return case_studies


def get_case_study_urls_from_sitemap() -> List[Dict[str, str]]:
    """
    Fetch and parse the Popular Pays sitemap to extract case study URLs.

    Returns:
        List of dictionaries containing case study information:
        - url: Full URL to the case study
        - title: Title of the case study (extracted from URL)
    """
    try:
        sitemap_url = "https://popularpays.com/sitemap.xml"
        response = requests.get(sitemap_url)

        if response.status_code != 200:
            logger.error(f"Failed to fetch sitemap. Status code: {response.status_code}")
            return []

        # Parse the XML
        soup = BeautifulSoup(response.content, "xml")
        urls = soup.find_all("loc")

        # Extract case study URLs
        case_study_urls = []
        for url in urls:
            url_text = url.text.strip()
            if "/case-studies/" in url_text and url_text != "https://popularpays.com/case-studies/":
                # Extract title from URL
                title = url_text.split("/case-studies/")[1].replace("-", " ").title()
                case_study_urls.append({"url": url_text, "title": title})

        logger.info(f"Found {len(case_study_urls)} case study URLs in sitemap")
        return case_study_urls

    except Exception as e:
        logger.error(f"Error fetching case study URLs from sitemap: {str(e)}")
        return []


def find_relevant_case_studies_from_sitemap(
    company_name: str, num_case_studies: int = 3
) -> List[Dict[str, str]]:
    """
    Find relevant case studies for a company from the Popular Pays sitemap.

    Args:
        company_name: The name of the company to find relevant case studies for
        num_case_studies: Number of case studies to retrieve (default: 3)

    Returns:
        List of dictionaries containing case study information:
        - url: Full URL to the case study
        - title: Title of the case study
    """
    try:
        # Get all case study URLs from sitemap
        all_case_studies = get_case_study_urls_from_sitemap()

        if not all_case_studies:
            logger.warning("No case studies found in sitemap")
            return []

        # Extract titles for GPT matching
        case_study_titles = [cs["title"] for cs in all_case_studies]

        # Use GPT to find the most relevant case studies
        url = "https://api.openai.com/v1/chat/completions"

        titles_str = ", ".join(case_study_titles)
        prompt = (
            f"Given information about {company_name}, which {num_case_studies} case studies are most relevant? "
            f"Choose only {num_case_studies} and your output should be only the case study titles "
            f"separated by commas without any additional text. "
            f"Here is the list of case studies: {titles_str}"
        )

        payload = {
            "model": "gpt-4.5-preview",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }

        response = requests.post(url, headers=OPENAI_HEADERS, json=payload)

        if response.status_code != 200:
            logger.error(f"Failed to get case study suggestions from GPT: {response.status_code}")
            # Return random case studies as fallback
            import random

            return random.sample(all_case_studies, min(num_case_studies, len(all_case_studies)))

        # Parse GPT response
        data = response.json()
        selected_titles = data["choices"][0]["message"]["content"].strip()
        selected_titles_list = [title.strip() for title in selected_titles.split(",")]

        # Find matching case studies
        relevant_case_studies = []
        for title in selected_titles_list:
            # Find closest match
            closest_match = None
            highest_similarity = 0

            for cs in all_case_studies:
                from difflib import SequenceMatcher

                similarity = SequenceMatcher(None, title.lower(), cs["title"].lower()).ratio()
                if similarity > highest_similarity:
                    highest_similarity = similarity
                    closest_match = cs

            if closest_match and highest_similarity > 0.6:
                relevant_case_studies.append(closest_match)

        # If we couldn't find enough matches, add random ones
        if len(relevant_case_studies) < num_case_studies:
            remaining = num_case_studies - len(relevant_case_studies)
            # Filter out already selected case studies
            remaining_case_studies = [
                cs for cs in all_case_studies if cs not in relevant_case_studies
            ]
            if remaining_case_studies:
                import random

                random_selections = random.sample(
                    remaining_case_studies, min(remaining, len(remaining_case_studies))
                )
                relevant_case_studies.extend(random_selections)

        logger.info(f"Found {len(relevant_case_studies)} relevant case studies for {company_name}")
        return relevant_case_studies

    except Exception as e:
        logger.error(f"Error finding relevant case studies from sitemap: {str(e)}")
        return []
