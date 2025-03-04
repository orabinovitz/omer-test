from datetime import datetime
from typing import Any, Dict, List, NotRequired, Tuple, TypedDict
import asyncio
import csv
import io
import json
import logging
import re
import time

from apify_client import ApifyClient
from dateutil.relativedelta import relativedelta
import aiohttp
import openai

from config import settings
from utils.case_studies import (
    find_relevant_case_studies_from_sitemap,
    get_relevant_case_studies,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],  # Log to console
)
logger = logging.getLogger("deep_research")

PERPLEXITY_KEY: str = settings.PERPLEXITY_API_KEY
OPENAI_KEY: str = settings.OPENAI_API_KEY
APIFY_KEY: str = settings.APIFY_API_KEY

apify_client = ApifyClient(APIFY_KEY)
openai_client = openai.OpenAI(
    api_key=OPENAI_KEY,
)


class Target:
    """Class representing a LinkedIn profile target."""

    def __init__(
        self,
        name: str,
        headline: str,
        url: str,
        bio: str = "",
        recent_posts: List[Dict[str, Any]] = None,
    ):
        """
        Initialize a Target object.
        
        Args:
            name: The target's name
            headline: The target's headline/title
            url: The target's LinkedIn URL
            bio: The target's bio text
            recent_posts: List of the target's recent LinkedIn posts
        """
        self.name = name
        self.headline = headline
        self.url = url
        self.bio = bio
        self.recent_posts = recent_posts or []

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Target object to a dictionary for JSON serialization.
        
        Returns:
            Dictionary representation of the Target
        """
        # Helper function to sanitize binary data for JSON
        def sanitize_value(value):
            if isinstance(value, bytes):
                try:
                    return value.decode('utf-8')
                except UnicodeDecodeError:
                    return str(value)
            elif isinstance(value, dict):
                return {k: sanitize_value(v) for k, v in value.items()}
            elif isinstance(value, (list, tuple)):
                return [sanitize_value(item) for item in value]
            return value
        
        # Create basic dict with sanitized values
        result = {
            "name": sanitize_value(self.name),
            "headline": sanitize_value(self.headline),
            "url": sanitize_value(self.url),
            "bio": sanitize_value(self.bio),
        }
        
        # Handle recent_posts specially to ensure they're all JSON serializable
        if self.recent_posts:
            result["recent_posts"] = [sanitize_value(post) for post in self.recent_posts]
        else:
            result["recent_posts"] = []
            
        return result

    def __str__(self) -> str:
        """String representation of the Target."""
        return f"{self.name} - {self.headline}"


class PerplexityMessage(TypedDict):
    content: str


class PerplexityChoice(TypedDict):
    message: PerplexityMessage


class PerplexityResponse(TypedDict):
    choices: List[PerplexityChoice]
    citations: NotRequired[List[str]]


def get_recent_years_range() -> Tuple[int, int]:
    """
    Get the current year and calculate the recent years range (current year and previous year).

    Returns:
        Tuple[int, int]: A tuple containing (current_year, previous_year)
    """
    current_year = datetime.now().year
    previous_year = current_year - 1
    return current_year, previous_year


async def fetch_topic_research(topic: str, progress_bar=None, status_text=None) -> Dict[str, Any]:
    """Research a topic using Perplexity API."""
    url = "https://api.perplexity.ai/chat/completions"
    start_time = time.time()

    # Track progress steps
    total_steps = 3  # Removed case study fetching step
    current_step = 0

    def update_progress(step_name: str):
        nonlocal current_step
        current_step += 1
        if progress_bar and status_text:
            progress = current_step / total_steps
            progress_bar.progress(progress)
            status_text.text(
                f"Researching {topic} - Step {current_step}/{total_steps}: {step_name}"
            )
        elif status_text:
            # Update only the status text if progress bar is None
            status_text.text(
                f"Researching {topic} - Step {current_step}/{total_steps}: {step_name}"
            )
        # Log to console
        logger.info(f"Topic research - {step_name} for topic: {topic}")

    # Basic report to return in case of error
    basic_report = {
        "choices": [{"message": {"content": f"Basic information about {topic}"}}],
        "citations": [],
    }

    try:
        # Step 1: Initial research with Perplexity
        update_progress("Initial topic research")

        payload = {
            "model": "sonar-reasoning-pro",
            "messages": [
                {
                    "role": "system",
                    "content": f"""
                    You are a sales person working for Popular Pays, a Lightricks brand. Popular Pays is an influencer agency. 
                    You are tasked with the goal of securing a meeting with relevant people from {topic} so we can sell them 
                    an influencer campaign. When mentioning any statistics, case studies, or blog posts, please provide actual URLs.
                """,
                },
                {
                    "role": "user",
                    "content": f"""
                        Do an exhaustive research on {topic}, I want to know:
                        1. About pain points.
                        2. What is the value proposition Popular Pays can offer?
                        3. What their brand is about?
                        4. Research marketing, social media, influencers, brand teams, creative teams, communities etc.
                        5. Find a connection between {topic} and Lightricks.
                        I want at least 500 words on each of the relevant points with specific evidence and examples.
                """,
                },
            ],
            "return_citations": True,
            "return_images": False,
            "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {PERPLEXITY_KEY}",
            "Content-Type": "application/json",
        }

        response = await async_request(url, payload, headers)

        if not isinstance(response, dict) or "choices" not in response:
            raise ValueError("Invalid response format from Perplexity API")

        # Step 2: Expanded research
        update_progress("Expanding topic research")
        assistant_response = response["choices"][0]["message"]["content"]
        payload["messages"].append({"role": "assistant", "content": assistant_response})
        payload["messages"].append(
            {
                "role": "user",
                "content": "Expand on the most critical pain points and how Popular Pays specifically addresses them. Include competitor analysis and specific use cases with evidence.",
            }
        )

        response_2 = await async_request(url, payload, headers)
        if not isinstance(response_2, dict) or "choices" not in response_2:
            raise ValueError("Invalid response format from Perplexity API in second request")

        # Step 3: Final research
        update_progress("Finalizing detailed research")
        assistant_response = response_2["choices"][0]["message"]["content"]
        payload["messages"].append({"role": "assistant", "content": assistant_response})
        payload["messages"].append(
            {
                "role": "user",
                "content": """
                Give me a final comprehensive report on everything you've researched about this topic. 
                Include specific strategies, statistics, case studies, and actionable insights.
            """,
            }
        )

        final_response = await async_request(url, payload, headers)
        if not isinstance(final_response, dict) or "choices" not in final_response:
            raise ValueError("Invalid response format from Perplexity API in final request")

        # Extract citations from all steps
        all_citations = []
        for research in [response, response_2, final_response]:
            if "citations" in research:
                all_citations.extend(research["citations"])

        # Add unique citations to final response
        final_response["all_citations"] = list(set(all_citations))

        # Log completion and return
        execution_time = time.time() - start_time
        if progress_bar and status_text:
            status_text.text(f"Topic research completed in {execution_time:.1f} seconds")
        elif status_text:
            status_text.text(f"Topic research completed in {execution_time:.1f} seconds")

        logger.info(f"Topic research completed in {execution_time:.1f} seconds for topic: {topic}")

        return final_response

    except Exception as e:
        error_msg = f"Topic research encountered an error: {str(e)}"
        logger.error(error_msg)
        st.warning(error_msg)
        return basic_report


async def get_linkedin_profiles_batch(
    urls: List[str], progress_bar=None, status_text=None
) -> Dict[str, Target]:
    """
    Fetch LinkedIn profiles for a list of URLs.

    Args:
        urls: List of LinkedIn profile URLs to process
        progress_bar: Optional Streamlit progress bar
        status_text: Optional Streamlit text element for status updates

    Returns:
        Dict mapping URLs to Target objects
    """
    start_time = time.time()

    if progress_bar and status_text:
        status_text.text(f"Fetching LinkedIn profiles for {len(urls)} people...")
        progress_bar.progress(0.1)
    elif status_text:
        status_text.text(f"Fetching LinkedIn profiles for {len(urls)} people...")

    logger.info(f"Starting LinkedIn profile fetch for {len(urls)} URLs")

    targets = {}

    logger.info(f"Calling Apify with URLs: {urls}")

    # Prepare the run input for Apify
    run_input = {"profileUrls": urls}

    # Define a function to run in a separate thread for Apify API calls
    logger.info("Starting Apify API call in a separate thread")

    async def run_apify_and_get_items():
        # Call the actor in a thread
        run = await asyncio.to_thread(
            lambda: apify_client.actor("dev_fusion/linkedin-profile-scraper").call(
                run_input=run_input
            )
        )

        if run is None:
            raise ValueError("Received null response from server")

        logger.info(f"Apify run completed. Dataset ID: {run['defaultDatasetId']}")

        # Get the items in a thread
        items = await asyncio.to_thread(
            lambda: list(apify_client.dataset(run["defaultDatasetId"]).iterate_items())
        )

        return items

    # Run the Apify call and get items
    items = await run_apify_and_get_items()

    logger.info(f"Retrieved {len(items)} profiles from Apify")

    # Process each profile
    for i, item in enumerate(items):
        try:
            # Extract profile data - check multiple possible field names
            profile_url = (
                item.get("profileUrl", "")
                or item.get("publicIdentifier", "")
                or item.get("url", "")
            )

            # For name, try multiple fields and formats
            name = (
                item.get("fullName", "")
                or item.get("name", "")
                or " ".join(filter(None, [item.get("firstName", ""), item.get("lastName", "")]))
            )

            # Clean up name if it exists
            if name:
                name = name.strip()

            # For headline/title, try multiple fields
            headline = (
                item.get("headline", "")
                or item.get("title", "")
                or item.get("position", "")
                or "No headline available"
            )

            # For bio/summary, try multiple fields
            summary = (
                item.get("summary", "")
                or item.get("about", "")
                or item.get("bio", "")
                or item.get("description", "")
                or "No bio available"
            )

            # Debug log the extracted data
            logger.debug(f"Extracted profile data - URL: {profile_url}, Name: {name}")

            # If we have a URL but no name, try to extract from URL
            if profile_url and not name:
                name = extract_name_from_linkedin_url(profile_url)
                logger.info(f"Generated name '{name}' from URL for profile: {profile_url}")

            # Skip profiles without URL (required for matching)
            if not profile_url:
                logger.warning(f"Skipping profile with no URL: {item}")
                continue

            # Create a Target object
            target = Target(name=name, headline=headline, url=profile_url, bio=summary)

            # First approach: Use same index if counts match
            if len(items) == len(urls):
                # Try to get the corresponding URL from the input list
                try:
                    target_url = urls[i]

                    # Check if the URL from Apify partially matches the input URL
                    if profile_url in target_url or target_url in profile_url:
                        # This is likely the corresponding profile
                        targets[target_url] = target
                        continue
                except IndexError:
                    # If index is out of range, fall back to URL matching
                    pass

            # Second approach: Match by URL
            matched = False

            for target_url in urls:
                # Check if the URL from Apify partially matches the input URL
                if profile_url in target_url or target_url in profile_url:
                    # This is likely the corresponding profile
                    targets[target_url] = target
                    matched = True
                    break

            # If no match found, use the URL from Apify directly
            if not matched:
                targets[profile_url] = target
        except Exception as e:
            logger.error(f"Error processing profile: {str(e)}")
            continue

    # Check if we have all the requested profiles
    for url in urls:
        if url not in targets:
            # Try to extract name from URL
            name = extract_name_from_linkedin_url(url)
            targets[url] = Target(
                name=name,
                headline="Profile information unavailable",
                url=url,
                bio="Profile information could not be retrieved",
            )

    execution_time = time.time() - start_time

    if progress_bar and status_text:
        status_text.text(f"LinkedIn profiles fetched in {execution_time:.1f} seconds")
    elif status_text:
        status_text.text(f"LinkedIn profiles fetched in {execution_time:.1f} seconds")

    logger.info(f"LinkedIn profiles fetch completed in {execution_time:.1f} seconds")
    return targets


async def generate_gpt_report(target: Target, topic_research: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a comprehensive report for a topic using GPT-o3-mini based on the research data."""
    try:
        logger.info(f"Generating report for {target.name}")
        start_time = time.time()

        # Extract content from topic research
        initial_content = (
            topic_research.get("initial_research", {})
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        expanded_content = (
            topic_research.get("expanded_research", {})
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        final_content = (
            topic_research.get("final_research", {})
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        # Extract case study analyses
        case_studies = topic_research.get("case_studies", [])
        case_study_analyses = []
        for cs in case_studies:
            case_study_analyses.append(f"Case Study - {cs['brand']}:\n{cs['image_analysis']}")

        case_study_text = "\n\n".join(case_study_analyses)

        all_citations = topic_research.get("all_citations", [])

        # Prepare prompt for GPT
        system_prompt = f"""
        You are a talented sales researcher helping prepare a detailed industry analysis for {target.name}.
        Your task is to synthesize research about this industry/company and create a comprehensive report that can be
        used as a foundation for personalized outreach to various stakeholders in the industry.
        """

        user_prompt = f"""
        ## Topic Information
        - Industry/Company: {target.name}
        
        ## Research Data
        {initial_content}
        
        {expanded_content}
        
        {final_content}
        
        ## Actual Popular Pays Case Studies
        {case_study_text}
        
        Based on this information, please create a comprehensive industry/company report that:
        1. Analyzes the industry/company landscape, trends, and challenges
        2. Identifies specific pain points common in this industry/company
        3. Outlines tailored value propositions for Popular Pays that address these pain points
        4. Provides key statistics, case studies, and resources that demonstrate our value
        5. Suggests specific talking points for securing meetings with decision-makers
        
        This report will serve as the foundation for personalized outreach to various stakeholders,
        so make it comprehensive enough to be adaptable to different roles and seniority levels.
        When writing the report, do not make stuff out, only write about what you got in the research data.
        When referencing case studies, ONLY mention the provided Popular Pays case studies, not external ones.
        
        Format the report with clear headings, bullet points, and actionable insights. Each section should be thorough and detailed.
        """

        logger.info(f"Calling OpenAI API to generate report for {target.name}")

        # Define a function to make the OpenAI API call
        async def call_openai_api():
            # Run the OpenAI API call in a thread
            return await asyncio.to_thread(
                lambda: openai_client.chat.completions.create(
                    model="o3-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
            )

        # Make the API call
        response = await call_openai_api()

        # Create case study citations for the report
        case_study_citations = []
        for cs in case_studies:
            case_study_citations.append(f"Popular Pays Case Study: {cs['brand']}")

        # Combine all citations
        combined_citations = all_citations + case_study_citations

        execution_time = time.time() - start_time
        logger.info(
            f"Report generation for {target.name} completed in {execution_time:.1f} seconds"
        )

        return {
            "content": response.choices[0].message.content,
            "citations": combined_citations,
            "case_studies": case_studies,
        }

    except Exception as e:
        error_msg = f"Error generating report for {target.name}: {str(e)}"
        logger.error(error_msg)
        st.warning(error_msg)
        return {
            "content": f"Failed to generate report for {target.name}. Error: {str(e)}",
            "citations": [],
            "case_studies": [],
        }


async def generate_email_messages(target: Target, report: Dict[str, Any]) -> str:
    """Generate outreach emails using GPT-4.5-preview by combining topic research with specific profile data."""
    try:
        logger.info(f"Generating email messages for {target.name}")
        start_time = time.time()

        # Extract first name for personalized greeting
        first_name = target.name.split(" ")[0]

        # Get current year and recent years range for relevance filtering
        current_year, previous_year = get_recent_years_range()
        recent_years_text = f"{previous_year}-{current_year}"

        # Get user information for signature
        user_info = report.get("user_info", {})
        user_name = user_info.get("name", "")
        user_title = user_info.get("title", "")
        user_company = user_info.get("company", "Popular Pays, a Lightricks brand")
        user_email = user_info.get("email", "")
        user_phone = user_info.get("phone", "")

        # Create signature based on available information
        signature = ""
        if user_name:
            signature += f"{user_name}\n"
            if user_title:
                signature += f"{user_title}\n"
            signature += f"{user_company}\n"
            if user_email:
                signature += f"{user_email}\n"
            if user_phone:
                signature += f"{user_phone}\n"

        # Extract case studies from report
        case_studies = report.get("case_studies", [])
        case_study_descriptions = []

        # Create a mapping of brand names to URLs for sitemap case studies
        brand_to_url = {}

        # Process case studies based on their source
        for cs in case_studies:
            if cs.get("source") == "sitemap":
                # For sitemap case studies, include the URL
                brand_to_url[cs["brand"]] = cs["url"]
                case_study_descriptions.append(
                    f"Case Study - {cs['brand']}:\n" f"URL: {cs['url']}\n" f"{cs['image_analysis']}"
                )
            else:
                # For Confluence case studies, include the image analysis
                case_study_descriptions.append(
                    f"Case Study - {cs['brand']}:\n{cs['image_analysis']}"
                )

        case_study_text = "\n\n".join(case_study_descriptions)

        # Prepare instructions for referencing case studies
        case_study_instructions = ""
        has_sitemap_case_studies = any(cs.get("source") == "sitemap" for cs in case_studies)
        has_confluence_case_studies = any(cs.get("source") != "sitemap" for cs in case_studies)

        # Create a list of brands with URLs for explicit instructions
        brands_with_urls = [f"{brand}: {url}" for brand, url in brand_to_url.items()]
        brands_with_urls_text = "\n".join(brands_with_urls)

        if has_sitemap_case_studies:
            case_study_instructions += (
                "IMPORTANT: Whenever you mention ANY of the following case studies in your emails, "
                "you MUST include the corresponding HTML link immediately after mentioning the brand name. "
                "For example: 'Our work with Chameleon Cold Brew (<a href=\"https://example.com\">case study</a>) showed...' "
                "\n\nHere are the case studies with their URLs:\n" + brands_with_urls_text + "\n\n"
            )

        if has_confluence_case_studies:
            case_study_instructions += (
                "For case studies with images, mention that you're attaching a relevant case study image. "
                'Use language like "I\'ve attached a case study showing our results with [brand]."\n\n'
            )

        # Prepare recent posts information if available
        recent_posts_text = ""
        if target.recent_posts:
            posts_details = []
            for i, post in enumerate(target.recent_posts[:5]):  # Limit to 5 most recent posts
                post_content = post.get("content", "").strip()
                post_date = post.get("date", "")

                if post_content:
                    posts_details.append(f"Post {i+1} ({post_date}):\n{post_content}")

            if posts_details:
                recent_posts_text = "RECENT LINKEDIN POSTS:\n" + "\n\n".join(posts_details)

        system_prompt = f"""
        You are a senior sales development representative for Popular Pays, a Lightricks brand specializing in influencer marketing.
        Your job is to craft compelling, personalized outreach emails to secure meetings with potential clients.
        
        Current year: {current_year}
        
        Follow these guidelines:
        - Create 5 sequential emails following a standard outreach sequence
        - Be upbeat, engaging, and focused on securing a meeting
        - Each email must be highly personalized to the recipient's background and needs
        - Include specific pain points and value propositions relevant to their industry
        - When mentioning resources, use HTML formatting: <a href="URL_HERE">text here</a>
        - Keep emails concise, actionable, and with clear CTAs
        - ALWAYS use the recipient's proper name, not their LinkedIn handle
        - ONLY reference Popular Pays' actual case studies, not external ones
        - ALWAYS include the HTML link when mentioning a case study that has a URL
        - ONLY mention recent achievements or recognition (from {recent_years_text}). Do not congratulate or mention achievements older than {previous_year}
        - If the person has recent LinkedIn posts, reference them in a natural, conversational way to personalize your message
        
        FORMAT INSTRUCTIONS (CRITICAL):
        - Use EXACT formatting for email sections:
        - Start each email with "Email 1:", "Email 2:", etc.
        - Include "Subject:" on its own line for each email
        - Separate emails with a blank line
        - DO NOT include any explanatory text between emails
        - DO NOT include any notes or comments at the end
        """

        # Add signature instructions
        signature_instructions = ""
        if signature:
            signature_instructions = f"""
            Use the following signature at the end of each email:
            
            {signature}
            """

        user_prompt = f"""
        Generate 5 sequential outreach emails for:
        
        RECIPIENT:
        - Name: {target.name}
        - First Name: {first_name}
        - Position: {target.headline}
        - LinkedIn: {target.url}
        - Bio: {target.bio}
        {recent_posts_text}
        
        INDUSTRY/COMPANY CONTEXT:
        {report.get("content", "")}
        
        POPULAR PAYS CASE STUDIES TO REFERENCE:
        {case_study_text}
        
        AVAILABLE RESOURCES (use these exact URLs when referencing):
        {json.dumps(report.get("citations", []), indent=2)}
        
        The emails should follow this sequence:
        1. Email 1: Initial cold outreach - introduce value proposition and establish relevance to {target.name}'s specific role
        2. Email 2: Follow-up with specific case study or resource that addresses pain points relevant to their position as "{target.headline}"
        3. Email 3: Value-add email sharing a relevant insight or resource specific to their background
        4. Email 4: Meeting request with specific agenda tailored to their role
        5. Email 5: Final breakup email with soft call-to-action
        
        If they have recent LinkedIn posts, reference them in Email 1 or 2 to show you've done your research and create a personalized connection.
        
        {case_study_instructions}
        
        CRITICAL REQUIREMENT: For Email 2 or 3, reference at least one case study. If the case study has a URL, you MUST include the HTML link immediately after mentioning the brand name. For example: "Our work with Chameleon Cold Brew (<a href="https://popularpays.com/case-study/chameleon">case study</a>) showed..."
        
        CONSISTENCY CHECK: Before finalizing each message, verify that EVERY case study mentioned has its corresponding HTML link included if a URL is available for that brand.
        
        {signature_instructions}
        
        IMPORTANT: Use this EXACT format for each email:
        
        Email 1:
        Subject: [Your subject line]
        
        [Email body]
        
        [Your signature]
        
        Email 2:
        Subject: [Your subject line]
        
        [Email body]
        
        [Your signature]
        
        (and so on for all 5 emails)
        """

        logger.info(f"Calling OpenAI API to generate emails for {target.name}")

        # Define a function to make the OpenAI API call
        async def call_openai_api():
            # Run the OpenAI API call in a thread
            try:
                return await asyncio.to_thread(
                    lambda: openai_client.chat.completions.create(
                        model="gpt-4.5-preview",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    )
                )
            except Exception as e:
                logger.error(f"OpenAI API call failed for {target.name}: {str(e)}")
                return None

        # Make the API call
        response = await call_openai_api()

        # Check if the response is valid
        if response is None:
            return "Failed to generate emails due to API error. Please try again later."

        # Extract the content from the response
        try:
            content = response.choices[0].message.content
            if not isinstance(content, str):
                logger.warning(
                    f"OpenAI API returned non-string content for {target.name}: {type(content).__name__}"
                )
                content = str(content)
        except Exception as e:
            logger.error(
                f"Error extracting content from OpenAI response for {target.name}: {str(e)}"
            )
            return f"Failed to extract email content from API response. Error: {str(e)}"

        execution_time = time.time() - start_time
        logger.info(f"Email generation for {target.name} completed in {execution_time:.1f} seconds")

        return content

    except Exception as e:
        error_msg = f"Error generating emails for {target.name}: {str(e)}"
        logger.error(error_msg)
        st.warning(error_msg)
        return f"Failed to generate emails. Error: {str(e)}"


async def generate_linkedin_messages(target: Target, report: Dict[str, Any]) -> str:
    """Generate LinkedIn outreach messages using GPT-4.5-preview by combining topic research with specific profile data."""
    try:
        logger.info(f"Generating LinkedIn messages for {target.name}")
        start_time = time.time()

        # Extract first name for personalized greeting
        first_name = target.name.split(" ")[0]

        # Get current year and recent years range for relevance filtering
        current_year, previous_year = get_recent_years_range()
        recent_years_text = f"{previous_year}-{current_year}"

        # Get user information for signature
        user_info = report.get("user_info", {})
        user_name = user_info.get("name", "")
        user_title = user_info.get("title", "")
        user_company = user_info.get("company", "Popular Pays, a Lightricks brand")

        # Create signature based on available information
        signature = ""
        if user_name:
            signature += f"{user_name}"
            if user_title:
                signature += f", {user_title}"
            signature += f" at {user_company}"

        # Extract case studies from report
        case_studies = report.get("case_studies", [])
        case_study_descriptions = []

        # Create a mapping of brand names to URLs for sitemap case studies
        brand_to_url = {}

        # Process case studies based on their source
        for cs in case_studies:
            if cs.get("source") == "sitemap":
                # For sitemap case studies, include the URL
                brand_to_url[cs["brand"]] = cs["url"]
                case_study_descriptions.append(
                    f"Case Study - {cs['brand']}:\n" f"URL: {cs['url']}\n" f"{cs['image_analysis']}"
                )
            else:
                # For Confluence case studies, include the image analysis
                case_study_descriptions.append(
                    f"Case Study - {cs['brand']}:\n{cs['image_analysis']}"
                )

        case_study_text = "\n\n".join(case_study_descriptions)

        # Prepare instructions for referencing case studies
        case_study_instructions = ""
        has_sitemap_case_studies = any(cs.get("source") == "sitemap" for cs in case_studies)
        has_confluence_case_studies = any(cs.get("source") != "sitemap" for cs in case_studies)

        # Create a list of brands with URLs for explicit instructions
        brands_with_urls = [f"{brand}: {url}" for brand, url in brand_to_url.items()]
        brands_with_urls_text = "\n".join(brands_with_urls)

        if has_sitemap_case_studies:
            case_study_instructions += (
                "IMPORTANT: Whenever you mention ANY of the following case studies in your messages, "
                "you MUST explicitly offer to share the case study link. "
                "For example: 'I'd be happy to share our Chameleon Cold Brew case study link that shows how we...' "
                "\n\nHere are the case studies with their URLs:\n" + brands_with_urls_text + "\n\n"
            )

        if has_confluence_case_studies:
            case_study_instructions += (
                "For case studies with images, mention that you can share a relevant case study image. "
                "For example: 'I can share our case study image showing our results with [brand].'\n\n"
            )

        # Prepare recent posts information if available
        recent_posts_text = ""
        if target.recent_posts:
            posts_details = []
            for i, post in enumerate(
                target.recent_posts[:3]
            ):  # Limit to 3 most recent posts for LinkedIn
                post_content = post.get("content", "").strip()
                post_date = post.get("date", "")

                if post_content:
                    posts_details.append(f"Post {i+1} ({post_date}):\n{post_content}")

            if posts_details:
                recent_posts_text = "RECENT LINKEDIN POSTS:\n" + "\n\n".join(posts_details)

        system_prompt = f"""
        You are a senior sales development representative for Popular Pays, a Lightricks brand specializing in influencer marketing.
        Your job is to craft compelling, personalized LinkedIn outreach messages to secure meetings with potential clients.
        
        Current year: {current_year}
        
        Follow these guidelines:
        - Create 3 sequential LinkedIn messages following a standard outreach sequence
        - Be upbeat, engaging, and focused on securing a meeting
        - Each message must be highly personalized to the recipient's background and needs
        - Include specific pain points and value propositions relevant to their industry
        - Keep messages concise (under 300 characters for first message, under 1500 for follow-ups)
        - ALWAYS use the recipient's proper name, not their LinkedIn handle
        - ONLY reference Popular Pays' actual case studies, not external ones
        - When mentioning a case study with a URL, ALWAYS offer to share the link
        - ONLY mention recent achievements or recognition (from {recent_years_text}). Do not congratulate or mention achievements older than {previous_year}
        - If the person has recent LinkedIn posts, reference them in a natural way to personalize your message
        
        FORMAT INSTRUCTIONS (CRITICAL):
        - Use EXACT formatting for message sections:
        - Start each message with "Message 1:", "Message 2:", etc.
        - Separate messages with a blank line
        - DO NOT include any explanatory text between messages
        - DO NOT include any notes or comments at the end
        """

        # Add signature instructions
        signature_instructions = ""
        if signature:
            signature_instructions = f"""
            Use the following signature at the end of each message:
            
            {signature}
            """

        user_prompt = f"""
        Generate 3 sequential LinkedIn outreach messages for:
        
        RECIPIENT:
        - Name: {target.name}
        - First Name: {first_name}
        - Position: {target.headline}
        - LinkedIn: {target.url}
        - Bio: {target.bio}
        {recent_posts_text}
        
        INDUSTRY/COMPANY CONTEXT:
        {report.get("content", "")}
        
        POPULAR PAYS CASE STUDIES TO REFERENCE:
        {case_study_text}
        
        The messages should follow this sequence:
        1. Message 1: Initial connection request - brief, personalized, under 300 characters
        2. Message 2: Follow-up after connection - introduce value proposition with specific relevance to {target.name}'s role
        3. Message 3: Value-add message with specific case study or resource that addresses pain points relevant to their position
        
        If they have recent LinkedIn posts, briefly reference one in your initial connection request to create a personalized connection.
        
        {case_study_instructions}
        
        CRITICAL REQUIREMENT: For Message 3, reference at least one case study that would be most relevant to their industry or role. If the case study has a URL, you MUST explicitly offer to share the link.
        
        CONSISTENCY CHECK: Before finalizing each message, verify that EVERY case study mentioned includes an explicit offer to share the link if a URL is available for that brand.
        
        {signature_instructions}
        
        IMPORTANT: Use this EXACT format for each message:
        
        Message 1:
        [Message body]
        
        [Your signature]
        
        Message 2:
        [Message body]
        
        [Your signature]
        
        Message 3:
        [Message body]
        
        [Your signature]
        """

        logger.info(f"Calling OpenAI API to generate LinkedIn messages for {target.name}")

        # Define a function to make the OpenAI API call
        async def call_openai_api():
            # Run the OpenAI API call in a thread
            try:
                return await asyncio.to_thread(
                    lambda: openai_client.chat.completions.create(
                        model="gpt-4.5-preview",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    )
                )
            except Exception as e:
                logger.error(
                    f"OpenAI API call failed for LinkedIn messages for {target.name}: {str(e)}"
                )
                return None

        # Make the API call
        response = await call_openai_api()

        # Check if the response is valid
        if response is None:
            return "Failed to generate LinkedIn messages due to API error. Please try again later."

        # Extract the content from the response
        try:
            content = response.choices[0].message.content
            if not isinstance(content, str):
                logger.warning(
                    f"OpenAI API returned non-string content for LinkedIn messages for {target.name}: {type(content).__name__}"
                )
                content = str(content)
        except Exception as e:
            logger.error(
                f"Error extracting content from OpenAI response for LinkedIn messages for {target.name}: {str(e)}"
            )
            return f"Failed to extract LinkedIn message content from API response. Error: {str(e)}"

        execution_time = time.time() - start_time
        logger.info(
            f"LinkedIn message generation for {target.name} completed in {execution_time:.1f} seconds"
        )

        return content

    except Exception as e:
        error_msg = f"Error generating LinkedIn messages for {target.name}: {str(e)}"
        logger.error(error_msg)
        st.warning(error_msg)
        return f"Failed to generate LinkedIn messages. Error: {str(e)}"


async def fetch_case_studies(
    topic: str, progress_bar=None, status_text=None
) -> List[Dict[str, Any]]:
    """Fetch relevant case studies from both the Popular Pays sitemap and Confluence."""
    start_time = time.time()

    if progress_bar and status_text:
        status_text.text(f"Fetching case studies for {topic}...")
        progress_bar.progress(0.2)
    elif status_text:
        status_text.text(f"Fetching case studies for {topic}...")

    logger.info("-" * 50)
    logger.info(f"CASE STUDIES FETCH STARTED for topic: {topic}")

    try:
        # First, try to get case studies from the sitemap
        logger.info("Fetching case studies from Popular Pays sitemap")
        sitemap_case_studies = await asyncio.to_thread(
            find_relevant_case_studies_from_sitemap, company_name=topic, num_case_studies=3
        )

        # Then, get case studies from Confluence as a backup
        logger.info("Fetching case studies from Confluence")
        confluence_case_studies = await asyncio.to_thread(
            get_relevant_case_studies, company_name=topic, num_case_studies=3
        )

        # Process and combine the results
        combined_case_studies = []

        # Add sitemap case studies first (these are preferred)
        for cs in sitemap_case_studies:
            combined_case_studies.append(
                {
                    "brand": cs["title"],
                    "url": cs["url"],
                    "source": "sitemap",
                    "image_data": None,  # No image data for sitemap case studies
                    "image_analysis": f"Case study from Popular Pays website: {cs['title']}",
                    "filename": None,
                }
            )

        # Add Confluence case studies if we need more
        remaining_slots = 3 - len(combined_case_studies)
        if remaining_slots > 0 and confluence_case_studies:
            for cs in confluence_case_studies[:remaining_slots]:
                combined_case_studies.append(
                    {
                        "brand": cs["brand"],
                        "image_data": cs["image_data"],
                        "image_analysis": cs["image_analysis"],
                        "filename": cs["filename"],
                        "source": "confluence",
                        "url": None,  # No URL for Confluence case studies
                    }
                )

        # Log the results
        logger.info(
            f"Retrieved {len(sitemap_case_studies)} case studies from sitemap and {len(confluence_case_studies)} from Confluence"
        )
        logger.info(f"Combined into {len(combined_case_studies)} total case studies")

        for i, cs in enumerate(combined_case_studies):
            source = cs["source"]
            if source == "sitemap":
                logger.info(f"Case Study {i+1}: {cs['brand']} - URL: {cs['url']} (from sitemap)")
            else:
                logger.info(f"Case Study {i+1}: {cs['brand']} - {cs['filename']} (from Confluence)")

        execution_time = time.time() - start_time
        if progress_bar and status_text:
            progress_bar.progress(1.0)
            status_text.text(f"Case studies fetched in {execution_time:.1f} seconds")
        elif status_text:
            status_text.text(f"Case studies fetched in {execution_time:.1f} seconds")

        logger.info(f"CASE STUDIES FETCH COMPLETED in {execution_time:.1f} seconds")
        logger.info("-" * 50)
        return combined_case_studies

    except Exception as e:
        error_msg = f"Error fetching case studies: {str(e)}"
        logger.error(error_msg)
        if progress_bar and status_text:
            status_text.text(error_msg)

        logger.info("CASE STUDIES FETCH FAILED")
        logger.info("-" * 50)
        return []


async def fetch_linkedin_posts_batch(
    urls: List[str], progress_bar=None, status_text=None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch recent LinkedIn posts for a list of profile URLs using Apify.

    Args:
        urls: List of LinkedIn profile URLs to fetch posts for
        progress_bar: Optional Streamlit progress bar
        status_text: Optional Streamlit text element for status updates

    Returns:
        Dict mapping LinkedIn profile URLs to lists of their recent posts
    """
    start_time = time.time()

    logger.info(f"Starting LinkedIn posts fetch for {len(urls)} URLs")
    logger.info("=" * 50)
    logger.info("LINKEDIN POSTS FETCH STARTED")

    posts_by_profile = {}

    # Get the current date and the date 6 months ago using relativedelta
    current_date = datetime.now()
    cutoff_date = current_date - relativedelta(months=6)
    date_range_text = f"Filtering posts between {cutoff_date.strftime('%Y-%m-%d')} and {current_date.strftime('%Y-%m-%d')}"
    logger.info(date_range_text)

    if progress_bar and status_text:
        status_text.text(f"Fetching LinkedIn posts for {len(urls)} profiles... ({date_range_text})")
    elif status_text:
        status_text.text(f"Fetching LinkedIn posts for {len(urls)} profiles... ({date_range_text})")

    try:
        # Prepare the run input
        run_input = {
            "urls": urls,
            "limitPerSource": 10,  # Limit to 10 recent posts per profile
            "deepScrape": True,
        }
        logger.info(f"Calling LinkedIn Posts Apify with URLs: {urls}")

        # Define a function to run the Apify call and get items
        async def run_apify_and_get_items():
            # Call the actor in a thread
            run = await asyncio.to_thread(
                lambda: apify_client.actor("supreme_coder/linkedin-post").call(run_input=run_input)
            )

            if run is None:
                raise ValueError("Received null response from server")

            logger.info(f"Apify run completed. Dataset ID: {run['defaultDatasetId']}")

            # Get the items in a thread
            items = await asyncio.to_thread(
                lambda: list(apify_client.dataset(run["defaultDatasetId"]).iterate_items())
            )

            return items

        # Run the Apify call and get items
        items = await run_apify_and_get_items()

        logger.info(f"Retrieved {len(items)} posts from Apify")

        # Statistics for tracking filtering decisions
        stats = {
            "total": len(items),
            "skipped_url_mismatch": 0,
            "skipped_no_content": 0,
            "skipped_empty_date": 0,
            "skipped_too_old": 0,
            "accepted": 0,
            "error": 0,
            "matched_by_url": 0,
            "matched_by_id": 0,
            "matched_by_name": 0,
        }

        # Group posts by profile URL and filter by date
        for i, item in enumerate(items):
            try:
                # Get profile URL and post information
                profile_url = item.get("sourceUrl", "")
                author_data = item.get("author", {})
                author_public_id = author_data.get("publicId", "")
                author_name = (
                    f"{author_data.get('firstName', '')} {author_data.get('lastName', '')}".strip()
                )

                # Skip if the profile URL is not in our list and we can't find a match using author ID
                if not any(url in profile_url for url in urls) and not author_public_id:
                    stats["skipped_url_mismatch"] += 1
                    continue

                # Extract post information
                post_content = item.get("text", "")
                post_url = item.get("url", "")
                post_date_str = item.get(
                    "timeSincePosted", ""
                )  # Try using timeSincePosted instead of date
                post_timestamp = item.get(
                    "postedAtTimestamp", None
                )  # Try using timestamp if available
                post_iso = item.get("postedAtISO", "")  # Try using ISO date if available

                # If we have a timestamp, convert it to a date
                if post_timestamp:
                    try:
                        post_date = datetime.fromtimestamp(
                            post_timestamp / 1000
                        )  # Convert milliseconds to seconds
                        post_date_str = post_date.strftime("%Y-%m-%d")
                    except Exception as e:
                        logger.warning(f"Failed to convert timestamp {post_timestamp}: {str(e)}")

                # If we have an ISO date string, use it
                if not post_timestamp and post_iso:
                    try:
                        post_date = datetime.fromisoformat(post_iso.replace("Z", "+00:00"))
                        post_date_str = post_date.strftime("%Y-%m-%d")
                    except Exception as e:
                        logger.warning(f"Failed to convert ISO date {post_iso}: {str(e)}")

                # Skip if there's no content
                if not post_content:
                    stats["skipped_no_content"] += 1
                    continue

                # Handle empty date string
                if not post_date_str:
                    logger.warning("Empty date string for post, assuming current date")
                    post_date = current_date
                    stats["skipped_empty_date"] += 1
                    continue

                # Parse the post date (format may vary, handle potential exceptions)
                try:
                    # Try multiple date formats
                    date_formats = [
                        "%Y-%m-%d",
                        "%Y/%m/%d",
                        "%d-%m-%Y",
                        "%d/%m/%Y",  # Standard formats
                        "%B %d, %Y",
                        "%b %d, %Y",  # Month name formats (January 1, 2023)
                        "%d %B %Y",
                        "%d %b %Y",  # Day first formats (1 January 2023)
                        "%Y-%m-%dT%H:%M:%S",
                        "%Y-%m-%dT%H:%M:%SZ",  # ISO formats
                        "%b %d",  # Month day without year (Jan 15)
                    ]

                    for date_format in date_formats:
                        try:
                            # Special handling for formats without year
                            if date_format == "%b %d":
                                # Parse with current year, then check if it's in the future
                                # If so, use previous year
                                month_day = datetime.strptime(post_date_str, date_format)
                                post_date = month_day.replace(year=current_date.year)

                                # If the resulting date is in the future, use previous year
                                if post_date > current_date:
                                    post_date = post_date.replace(year=current_date.year - 1)
                                break
                            else:
                                post_date = datetime.strptime(post_date_str, date_format)
                                break
                        except ValueError:
                            continue
                    else:
                        # Try to handle relative dates like "1 month ago", "3 days ago", etc.
                        parsed = False

                        # Common relative date patterns
                        if re.search(r"(\d+)\s+month(?:s)?\s+ago", post_date_str, re.IGNORECASE):
                            months = int(
                                re.search(
                                    r"(\d+)\s+month(?:s)?\s+ago", post_date_str, re.IGNORECASE
                                ).group(1)
                            )
                            post_date = current_date - relativedelta(months=months)
                            parsed = True
                        elif re.search(r"(\d+)\s+week(?:s)?\s+ago", post_date_str, re.IGNORECASE):
                            weeks = int(
                                re.search(
                                    r"(\d+)\s+week(?:s)?\s+ago", post_date_str, re.IGNORECASE
                                ).group(1)
                            )
                            post_date = current_date - relativedelta(weeks=weeks)
                            parsed = True
                        elif re.search(r"(\d+)\s+day(?:s)?\s+ago", post_date_str, re.IGNORECASE):
                            days = int(
                                re.search(
                                    r"(\d+)\s+day(?:s)?\s+ago", post_date_str, re.IGNORECASE
                                ).group(1)
                            )
                            post_date = current_date - relativedelta(days=days)
                            parsed = True
                        elif "yesterday" in post_date_str.lower():
                            post_date = current_date - relativedelta(days=1)
                            parsed = True
                        elif "last week" in post_date_str.lower():
                            post_date = current_date - relativedelta(weeks=1)
                            parsed = True

                        if not parsed:
                            # If none of the formats or patterns work, assume it's recent
                            logger.warning(
                                f"Could not parse date: '{post_date_str}', assuming it's recent (current date)"
                            )
                            post_date = current_date
                except Exception as e:
                    # If any other error occurs, assume it's recent
                    logger.warning(
                        f"Error parsing date: '{post_date_str}' - {str(e)}, assuming current date"
                    )
                    post_date = current_date

                # Check if the post is within the last 6 months
                if post_date < cutoff_date:
                    stats["skipped_too_old"] += 1
                    continue
                else:
                    stats["accepted"] += 1

                # Find the matching profile URL from our original list using multiple methods
                matching_url = None

                # Method 1: Direct profile URL matching (original method)
                if profile_url:
                    matching_url = next((url for url in urls if url in profile_url), None)
                    if matching_url:
                        stats["matched_by_url"] += 1

                # Method 2: If no match found and we have author public ID, try to match by that
                if not matching_url and author_public_id:
                    for url in urls:
                        # Check if the public ID is part of the URL
                        if author_public_id.lower() in url.lower():
                            matching_url = url
                            stats["matched_by_id"] += 1
                            break

                # Method 3: If still no match but we have author name, try name-based matching
                if not matching_url and author_name:
                    for url in urls:
                        # Extract name from URL and compare with author name
                        url_name = extract_name_from_linkedin_url(url).lower().replace("-", " ")
                        author_name_lower = author_name.lower()
                        if url_name and (
                            url_name in author_name_lower or author_name_lower in url_name
                        ):
                            matching_url = url
                            stats["matched_by_name"] += 1
                            break

                if matching_url:
                    # Initialize the list for this profile if it doesn't exist
                    if matching_url not in posts_by_profile:
                        posts_by_profile[matching_url] = []

                    # Add the post to the profile's list
                    posts_by_profile[matching_url].append(
                        {"content": post_content, "url": post_url, "date": post_date_str}
                    )
            except Exception as e:
                logger.error(f"Error processing post: {str(e)}")
                stats["error"] += 1
                # Continue with the next post

        # Log the results
        total_posts = 0
        posts_by_profile_summary = []

        for url, posts in posts_by_profile.items():
            post_count = len(posts)
            total_posts += post_count
            profile_name = extract_name_from_linkedin_url(url)
            posts_by_profile_summary.append(f"{profile_name}: {post_count} posts")
            logger.info(f"Retrieved {post_count} recent posts for profile: {url}")

        execution_time = time.time() - start_time
        if progress_bar and status_text:
            if total_posts > 0:
                status_text.text(
                    f"Found {total_posts} LinkedIn posts across {len(posts_by_profile)} profiles in {execution_time:.1f} seconds"
                )
            else:
                status_text.text(
                    f"No recent LinkedIn posts found for the profiles in {execution_time:.1f} seconds"
                )
        elif status_text:
            if total_posts > 0:
                status_text.text(
                    f"Found {total_posts} LinkedIn posts across {len(posts_by_profile)} profiles in {execution_time:.1f} seconds"
                )
            else:
                status_text.text(
                    f"No recent LinkedIn posts found for the profiles in {execution_time:.1f} seconds"
                )

        logger.info(f"LINKEDIN POSTS FETCH COMPLETED in {execution_time:.1f} seconds")

        # Log final statistics summary
        logger.info("=" * 50)
        logger.info("LINKEDIN POSTS PROCESSING SUMMARY:")
        logger.info(f"Total posts retrieved from API: {stats['total']}")
        logger.info(f"Posts matched to profiles: {total_posts}")
        logger.info(f"Posts filtered out: {stats['total'] - stats['accepted']}")

        return posts_by_profile, stats

    except Exception as e:
        error_msg = f"Error fetching LinkedIn posts: {str(e)}"
        logger.error(error_msg)
        if progress_bar and status_text:
            status_text.text(error_msg)

        logger.info("LINKEDIN POSTS FETCH FAILED")
        return {}, {
            "total": 0,
            "skipped_url_mismatch": 0,
            "skipped_no_content": 0,
            "skipped_empty_date": 0,
            "skipped_too_old": 0,
            "accepted": 0,
            "error": 1,
        }


async def process_research_pipeline(urls: List[str], topic: str, progress_bar=None, status_text=None) -> Dict[str, Any]:
    """
    Process a full research pipeline for multiple profiles related to a topic.
    
    Args:
        urls: List of LinkedIn profile URLs to research
        topic: The topic to research in relation to the profiles
        progress_bar: Optional progress bar object (for UI integration)
        status_text: Optional status text object (for UI integration)
        
    Returns:
        Dictionary with results for each URL
    """
    results = {}
    
    # User info (will be passed through Flask session now)
    user_info = {
        "name": "",
        "title": "",
        "company": "Popular Pays, a Lightricks brand",
        "email": "",
        "phone": "",
    }
    
    # Create progress trackers
    progress_steps = len(urls) * 3 + 2  # LinkedIn profile + posts + emails/messages for each URL, plus topic research and case studies
    current_step = 0
    
    # Define a function to update progress
    def update_progress(step_name: str):
        nonlocal current_step
        current_step += 1
        progress_percentage = current_step / progress_steps
        logger.info(f"Progress: {progress_percentage:.0%} - {step_name}")
        if progress_bar is not None:
            progress_bar.progress(progress_percentage)
        if status_text is not None:
            status_text.write(f"Step {current_step}/{progress_steps}: {step_name}")
    
    try:
        # Step 1: Research the topic
        update_progress(f"Researching topic: {topic}")
        topic_research = await fetch_topic_research(topic, progress_bar, status_text)
        
        # Step 2: Get case studies
        update_progress(f"Fetching case studies for {topic}")
        case_studies = await fetch_case_studies(topic, progress_bar, status_text)
        
        # Add case studies to the research
        topic_research["case_studies"] = case_studies
        
        # Step 3: Process each LinkedIn profile
        update_progress("Processing LinkedIn profiles")
        targets = await get_linkedin_profiles_batch(urls, progress_bar, status_text)
        
        # Step 4: Fetch LinkedIn posts for each profile
        update_progress("Fetching LinkedIn posts")
        posts_data_result = await fetch_linkedin_posts_batch(urls, progress_bar, status_text)
        
        # Unpack the tuple returned by fetch_linkedin_posts_batch
        if isinstance(posts_data_result, tuple) and len(posts_data_result) == 2:
            posts_data, posts_stats = posts_data_result
        else:
            # Handle the case where it's not a tuple (e.g., just a dict in error cases)
            posts_data = posts_data_result
        
        # Add posts to targets
        for url, posts in posts_data.items():
            if url in targets:
                targets[url].recent_posts = posts
        
        # Track processed targets for UI
        targets_list = []
        
        # Step 5: Generate reports, emails, and messages for each profile
        for url, target in targets.items():
            try:
                update_progress(f"Generating report for {target.name}")
                
                # Generate comprehensive report
                report = await generate_gpt_report(target, topic_research)
                
                update_progress(f"Generating emails for {target.name}")
                emails = await generate_email_messages(target, report)
                
                update_progress(f"Generating LinkedIn messages for {target.name}")
                linkedin_messages = await generate_linkedin_messages(target, report)
                
                # Store results
                results[url] = {
                    "target": target,
                    "report": report,
                    "emails": emails,
                    "linkedin_messages": linkedin_messages,
                }
                
                targets_list.append((url, target))
                
            except Exception as e:
                logger.error(f"Error processing {url}: {str(e)}")
                results[url] = {
                    "error": f"Failed to process profile: {str(e)}",
                    "target": target if url in targets else None,
                    "report": topic_research,
                }
        
        return results
    
    except Exception as e:
        logger.error(f"Pipeline error: {str(e)}")
        return {"error": f"Research pipeline failed: {str(e)}"}


def extract_name_from_linkedin_url(url: str) -> str:
    """
    Extract name from LinkedIn URL with fallback to URL itself.

    The function handles different formats of LinkedIn URLs and attempts to
    convert usernames to more readable display names.
    """
    try:
        # Remove trailing slash if present
        url = url.rstrip("/")

        # Get the last part of the URL
        username = url.split("/")[-1]

        # Handle potential formats like 'in/nathanpoekert'
        if not username and len(url.split("/")) > 2:
            username = url.split("/")[-2]

        # Skip empty username
        if not username:
            return url

        # Check if the username is actually an ID (all digits)
        if username.isdigit():
            return url

        # Convert username to display name:
        # 1. Replace hyphens and underscores with spaces
        # 2. Handle camelCase by adding spaces before uppercase letters that follow lowercase
        name = username.replace("-", " ").replace("_", " ")

        # Insert space before capital letters in middle of words (e.g., "nathanPoekert" -> "nathan Poekert")
        spaced_name = ""
        for i, char in enumerate(name):
            if i > 0 and char.isupper() and name[i - 1].islower():
                spaced_name += " " + char
            else:
                spaced_name += char

        # Title case each word for proper capitalization
        display_name = " ".join(word.capitalize() for word in spaced_name.split())

        # Log the transformation
        logger.debug(f"Transformed LinkedIn username '{username}' to display name '{display_name}'")

        return display_name
    except Exception as e:
        logger.warning(f"Error extracting name from LinkedIn URL '{url}': {str(e)}")
        return url


async def async_request(
    url: str, payload: Dict[str, Any], headers: Dict[str, str]
) -> Dict[str, Any]:
    """Async helper function for making HTTP requests"""
    start_time = time.time()
    request_id = f"{url}_{int(start_time * 1000) % 10000}"  # Create a unique ID for this request

    logger.info(f"[{request_id}] Starting async request to: {url}")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=300)
            ) as response:
                result = await response.json()
                if result is None:
                    logger.error(f"[{request_id}] Received null response from server: {url}")
                    raise ValueError("Received null response from server")

                execution_time = time.time() - start_time
                logger.info(
                    f"[{request_id}] Async request completed in {execution_time:.1f} seconds"
                )
                return result
        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.error(
                f"[{request_id}] Request timed out after {execution_time:.1f} seconds: {url}"
            )
            raise ValueError(f"Request timed out after {execution_time:.1f} seconds")
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"[{request_id}] Request failed after {execution_time:.1f} seconds: {str(e)}"
            )
            raise


def extract_message_content(text: str, message_number: int, message_type: str = "email") -> str:
    """Extract specific message content from the generated text using a simple, robust approach."""
    # Return a proper error message for invalid inputs
    if isinstance(text, bool):
        return f"Error: received boolean value ({text}) instead of text"

    if not isinstance(text, str):
        try:
            # Try to convert to string
            text = str(text)
        except Exception:
            return f"Error: could not process {type(text).__name__} input"

    if not text:
        return ""

    # Define patterns to look for
    if message_type == "email":
        # Use regex to find email sections
        import re

        # Define patterns for email markers
        email_patterns = [
            # Pattern for "Email X" followed by content
            rf"Email\s+{message_number}[^\n]*\n(.*?)(?:Email\s+{message_number + 1}|$)",
            # Pattern for "Subject:" followed by content (for first email)
            r"Subject:[^\n]*\n(.*?)(?:Email\s+2|$)" if message_number == 1 else None,
        ]

        # Try each pattern
        for pattern in email_patterns:
            if pattern:
                try:
                    match = re.search(pattern, text, re.DOTALL)
                    if match:
                        return match.group(1).strip()
                except Exception:
                    continue

        # Fallback: for message 1, just return the first part of the text
        if message_number == 1:
            # Take roughly the first 1/5 of the text
            parts = text.split("\n\n")
            if len(parts) >= 5:
                return "\n\n".join(parts[: len(parts) // 5]).strip()
            else:
                return text.strip()

        # For other messages, just return a placeholder
        return f"Email {message_number} content not found"

    else:  # LinkedIn messages
        # Similar approach for LinkedIn messages
        import re

        # Define patterns for LinkedIn message markers
        message_patterns = [
            # Pattern for "Message X" followed by content
            rf"Message\s+{message_number}[^\n]*\n(.*?)(?:Message\s+{message_number + 1}|$)",
            # Pattern for "LinkedIn Message X" followed by content
            rf"LinkedIn Message\s+{message_number}[^\n]*\n(.*?)(?:LinkedIn Message\s+{message_number + 1}|$)",
        ]

        # Try each pattern
        for pattern in message_patterns:
            try:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    return match.group(1).strip()
            except Exception:
                continue

        # Fallback: for message 1, just return the first part of the text
        if message_number == 1:
            # Take roughly the first 1/3 of the text for LinkedIn messages
            parts = text.split("\n\n")
            if len(parts) >= 3:
                return "\n\n".join(parts[: len(parts) // 3]).strip()
            else:
                return text.strip()

        # For other messages, just return a placeholder
        return f"LinkedIn Message {message_number} content not found"


def create_download_csv(results: Dict[str, Dict[str, Any]]) -> str:
    """Create a CSV string containing all target information and generated messages."""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)

    # Write header
    writer.writerow(
        [
            "Name",
            "LinkedIn URL",
            "Headline",
            "Bio",
            "Email 1 (Cold Outreach)",
            "Email 2 (Follow-up)",
            "Email 3 (Value Add)",
            "Email 4 (Meeting Request)",
            "Email 5 (Final Follow-up)",
            "LinkedIn Message 1 (Connection Request)",
            "LinkedIn Message 2 (Resource Share)",
            "LinkedIn Message 3 (Case Study & Question)",
            "Citations",
            "Processing Status",  # Add status column
        ]
    )

    # Write data for each target
    for url, result in results.items():
        try:
            # Safely get the target
            target = result.get("target")
            
            # Handle target as dictionary or Target object
            if isinstance(target, dict):
                target_name = target.get("name", extract_name_from_linkedin_url(url))
                target_url = target.get("url", url)
                target_headline = target.get("headline", "Profile information unavailable")
                target_bio = target.get("bio", "Profile information could not be retrieved")
            elif isinstance(target, Target):
                target_name = target.name
                target_url = target.url
                target_headline = target.headline
                target_bio = target.bio
            else:
                # Create basic target info from URL if missing
                target_name = extract_name_from_linkedin_url(url)
                target_url = url
                target_headline = "Profile information unavailable"
                target_bio = "Profile information could not be retrieved"

            # Get message content with empty fallbacks
            # Ensure we're dealing with strings, not other types
            email_content = result.get("emails", "")
            if not isinstance(email_content, str):
                if email_content is None:
                    email_content = ""
                else:
                    try:
                        email_content = str(email_content)
                    except Exception:
                        email_content = (
                            f"Error: Unable to convert {type(email_content).__name__} to string"
                        )

            linkedin_content = result.get("linkedin_messages", "")
            if not isinstance(linkedin_content, str):
                if linkedin_content is None:
                    linkedin_content = ""
                else:
                    try:
                        linkedin_content = str(linkedin_content)
                    except Exception:
                        linkedin_content = (
                            f"Error: Unable to convert {type(linkedin_content).__name__} to string"
                        )

            # Extract messages with empty fallbacks for errors
            emails = []
            for i in range(1, 6):
                try:
                    if email_content:
                        email = extract_message_content(email_content, i)
                    else:
                        email = ""
                except Exception as e:
                    logger.error(f"Error extracting email {i} for {target_name}: {str(e)}")
                    email = f"Error extracting email {i}"
                emails.append(email)

            linkedin_msgs = []
            for i in range(1, 4):
                try:
                    if linkedin_content:
                        msg = extract_message_content(linkedin_content, i, "linkedin")
                    else:
                        msg = ""
                except Exception as e:
                    logger.error(
                        f"Error extracting LinkedIn message {i} for {target_name}: {str(e)}"
                    )
                    msg = f"Error extracting LinkedIn message {i}"
                linkedin_msgs.append(msg)

            # Get citations with empty fallback
            try:
                citations = result.get("report", {}).get("citations", [])
                # Ensure citations is a list
                if not isinstance(citations, list):
                    if citations is None:
                        citations = []
                    elif isinstance(citations, str):
                        citations = [citations]
                    else:
                        try:
                            citations = [str(citations)]
                        except Exception:
                            citations = ["Error: Unable to convert citations to string"]

                citations_str = "\n".join(str(c) for c in citations) if citations else ""
            except Exception as e:
                logger.error(f"Error processing citations for {target_name}: {str(e)}")
                citations_str = f"Error processing citations: {str(e)}"

            # Determine processing status
            status = "Success"
            if "error" in result:
                status = "Error: " + str(result["error"])
            if result.get("partial_data"):
                status = "Partial Data: " + status

            # Write row with status
            writer.writerow(
                [
                    target_name,
                    target_url,
                    target_headline,
                    target_bio,
                    *emails,
                    *linkedin_msgs,
                    citations_str,
                    status,
                ]
            )
        except Exception as e:
            logger.error(f"Error creating CSV row for {url}: {str(e)}")
            # Fallback row for completely failed entries
            try:
                name = extract_name_from_linkedin_url(url)
            except Exception as e:
                name = "Unknown"

            writer.writerow(
                [
                    name,
                    url,
                    "Error processing profile",
                    str(e),
                    *[""] * 8,  # Empty cells for messages
                    "",  # Empty citations
                    f"Failed: {str(e)}",  # Status with error
                ]
            )

    return output.getvalue()
