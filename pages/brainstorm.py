import os
import sys
import toml
import streamlit as st
from openai import OpenAI
from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT
import streamlit.components.v1 as components
from pydantic import BaseModel

# Add the parent directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Get the API key from Streamlit secrets
secrets_path = os.path.join(parent_dir, ".streamlit", "secrets.toml")
secrets = toml.load(secrets_path)
os.environ["OPENAI_API_KEY"] = secrets.get("OPENAI_API_KEY", "")
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# Add Anthropic client initialization
anthropic_api_key = secrets.get("ANTHROPIC_API_KEY", "")
anthropic = Anthropic(api_key=anthropic_api_key)

# Add this near the top of the file, after the imports
FACETUNE_TOV = """Facetune tone of voice:
    Facetune is an image editing app for content creators of all kinds. We help highlight what makes you YOU, so you can express yourself and share with confidence. As one of the world's most successful selfie editing tools, Facetune has to toe the line between being supportive and inspirational, while ensuring that everyone who uses the app feels comfortable sharing who they are, exactly as they are. Please avoid the words perfect, better, best, stretch, squish, resize, and others that may give too much focus to distorting a user's physical attributes. When writing for Facetune, it's important to speak as if you're talking to a friend and being supportive, upbeat, and just a little bit sassy. 

    Authentic 
    Since we're all creators, we talk to our community like they talk to each other. That means no buzzwords, name dropping or complicated jargon — just honest, open dialogue that encourages sharing and discovery. 

    Playful
    Experimentation is an important part of self-expression. That's why we always champion play and encourage creators to explore all the ways our tools can bring their unique visions to life. 

    Sharp & Sassy
    Selfies can be serious business, but we don't take ourselves too seriously. We balance the seriousness of technology that makes Facetune great with a sharp self-aware sass that never loses sight of its context. 

    Encouraging & Confident 
    Confidence breeds experimentation. That's why we're all about emphasizing and celebrating the uniqueness inside every creator to inspire them to embrace it and find new ways to share it with the world. 

    Target audience: Facetune

    Makeup artists 
    Hair Stylists 
    Fashion designers 
    Beauty technicians: nail + lash technicians (SMB's) 
    Other fashion & beauty professionals 
    Gen Z women
    Gen Z men
    LGBTQ+ community
    Drag
    Celebrities lovers
    Photography enthusiasts
    Social media influencers + celebrities
    Self-love & body positivity advocates
    Content creators and vloggers
    Gothic community"""

class MarketingIdea(BaseModel):
    idea_title: str
    idea_content: str

def compare_summaries(liked_summary, rejected_summary):
    system_prompt = """You are a strategic marketing expert. Your task is to compare two summary lists: one of liked ideas and one of rejected ideas. Analyze these lists and create a concise comparison that highlights:

    1. Ideas the user likes and wants to pursue
    2. Ideas the user doesn't like and wants to avoid

    Focus on the key differences between the two lists. Ignore any similarities and concentrate on unique aspects of each. Your output should be in this format:

    Be concise and specific in your analysis, and write a list of Things to avoid and Things to pursue.
    Do not write any system prompts/introduction/instructions/conclusion, just output the comparison."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Liked ideas summary:\n{liked_summary}\n\nRejected ideas summary:\n{rejected_summary}"}
        ],
        temperature=0.3
    )
    comparison = response.choices[0].message.content.strip()
    return comparison

def generate_marketing_idea(topic, liked_summary, rejected_summary):
    # First, compare the summaries
    comparison = compare_summaries(liked_summary, rejected_summary)
    
    system_prompt = f"""You are a marketing expert for the Facetune brand, in charge of generating creative marketing ideas.
    
    {FACETUNE_TOV}

    Create a new idea that incorporates elements the user likes and avoids aspects they don't like.
    Your response should be creative, unique, and tailored to the user's preferences.
    
    Important guidelines:
    1. Do not simply repeat or closely mimic previously liked ideas.
    2. Use the liked elements as inspiration, not as a template to copy.
    3. Introduce new and unexpected elements while maintaining the overall theme.
    4. Focus on innovation and originality for each new idea.
    5. Consider combining liked elements in novel ways or exploring new angles.
    
    Do not write any system prompts/introduction/instructions/conclusion, just output the idea. You are limited to 150 words.
    """

    completion = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate a unique marketing idea for '{topic}'. Use this requirement list to know what to avoid and what to pursue: {comparison}. Remember to be innovative and avoid repeating previous ideas, even if they were liked."}
        ],
        response_format=MarketingIdea,
        temperature=1
    )
    
    return completion.choices[0].message.parsed

def summarize_ideas(ideas, idea_type):
    if not ideas:
        return f"No {idea_type} ideas to summarize."
    
    # Convert MarketingIdea objects to strings
    idea_strings = [f"{idea.idea_title}: {idea.idea_content}" for idea in ideas]
    
    system_prompt = f"""You are a marketing strategist. Summarize the following {idea_type} brainstorming ideas, identify any recurring themes, concepts and patterns. You must disregard any details about seasonality and holidays as I want the summary to be as dry as possible and only outline the campaign actions. Do not write any system prompts/introduction/instructions/conclusion, just output the idea. You are limited to 250 words."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "\n".join(idea_strings)}
        ],
        temperature=0.3
    )
    summary = response.choices[0].message.content.strip()
    return summary

def expand_topic(topic):
    if not st.session_state.use_topic_expansion:
        return topic
    
    try:
        with st.spinner(f'Expanding on "{topic}"...'):
            response = anthropic.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=1000,
                temperature=0.8,
                system="You are a marketing expert for Facetune.",
                messages=[
                    {"role": "user", "content": f"Read the following Facetune tone of voice guidelines:\n\n{FACETUNE_TOV}\n\nNow, create a unique system prompt that expands on the user's input topic '{topic}' while keeping its exact meaning. The expanded topic should be suitable for generating marketing ideas for Facetune. Your response should be concise and directly usable as a system prompt for further idea generation. Do not write any system prompts/introduction/instructions/conclusion, just output the idea. You are limited to 25 words."}
                ]
            )
            expanded_topic = response.content[0].text
            return expanded_topic
    except Exception as e:
        st.error(f"Error expanding topic: {e}")
        return topic

def process_idea_and_generate_new():
    if not st.session_state.expanded_topic:
        st.session_state.expanded_topic = expand_topic(st.session_state.topic)
    
    with st.spinner("Summarizing ideas..."):
        liked_summary = summarize_ideas(st.session_state.liked_ideas, "liked")
        rejected_summary = summarize_ideas(st.session_state.rejected_ideas, "rejected")
    
    with st.spinner("Comparing summaries..."):
        comparison = compare_summaries(liked_summary, rejected_summary)
    
    with st.spinner("Generating a new marketing concept..."):
        st.session_state.current_idea = generate_marketing_idea(st.session_state.expanded_topic, liked_summary, rejected_summary)
    
    st.rerun()

st.set_page_config(page_title="Brainstorm App", page_icon="💡", layout="centered")

if 'liked_ideas' not in st.session_state:
    st.session_state.liked_ideas = []
if 'rejected_ideas' not in st.session_state:
    st.session_state.rejected_ideas = []
if 'current_idea' not in st.session_state:
    st.session_state.current_idea = None
if 'topic' not in st.session_state:
    st.session_state.topic = ''
if 'need_new_idea' not in st.session_state:
    st.session_state.need_new_idea = False
if 'expanded_topic' not in st.session_state:
    st.session_state.expanded_topic = None
if 'use_topic_expansion' not in st.session_state:
    st.session_state.use_topic_expansion = True

st.title("💡 Brainstorm App")
st.write("Welcome! Input a topic to start generating marketing ideas.")

st.session_state.topic = st.text_input("Enter a topic for brainstorming:", st.session_state.topic)
st.session_state.use_topic_expansion = st.checkbox("Expand topic using AI", value=st.session_state.use_topic_expansion)

if st.session_state.current_idea:
    st.subheader("Here's a marketing idea:")
    st.info(f"**{st.session_state.current_idea.idea_title}**\n\n{st.session_state.current_idea.idea_content}")

    # Use custom CSS to style the buttons
    st.markdown("""
    <style>
    .stButton > button {
        width: 100%;
        height: 50px;
    }
    </style>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("👍 Like", key="like_button", use_container_width=True):
            st.session_state.liked_ideas.append(st.session_state.current_idea)
            process_idea_and_generate_new()
    with col2:
        if st.button("👎 Reject", key="reject_button", use_container_width=True):
            st.session_state.rejected_ideas.append(st.session_state.current_idea)
            process_idea_and_generate_new()

# Initial idea generation when there's no current idea
if st.session_state.current_idea is None and st.session_state.topic:
    if st.session_state.expanded_topic is None or not st.session_state.use_topic_expansion:
        st.session_state.expanded_topic = expand_topic(st.session_state.topic)
    process_idea_and_generate_new()

# Add a divider line
st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Liked Ideas")
    if st.session_state.liked_ideas:
        for i, idea in enumerate(st.session_state.liked_ideas, 1):
            with st.expander(idea.idea_title, expanded=False):
                st.write(idea.idea_content)
    else:
        st.write("No liked ideas yet.")

with col2:
    st.subheader("Rejected Ideas")
    if st.session_state.rejected_ideas:
        for i, idea in enumerate(st.session_state.rejected_ideas, 1):
            with st.expander(idea.idea_title, expanded=False):
                st.write(idea.idea_content)
    else:
        st.write("No rejected ideas yet.")

if st.session_state.current_idea is None and st.session_state.topic and (st.session_state.liked_ideas or st.session_state.rejected_ideas):
    with st.spinner("Summarizing your liked and rejected ideas..."):
        liked_summary = summarize_ideas(st.session_state.liked_ideas, "liked")
        rejected_summary = summarize_ideas(st.session_state.rejected_ideas, "rejected")
    st.subheader("Summary of Your Ideas")
    if st.session_state.liked_ideas:
        with st.expander("Liked Ideas Summary", expanded=False):
            st.success(liked_summary)
    if st.session_state.rejected_ideas:
        with st.expander("Rejected Ideas Summary", expanded=False):
            st.error(rejected_summary)
