"""Flask application for Deep Research tool."""
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import asyncio
import csv
import io
import json
from json.decoder import JSONDecodeError
import logging
import os
import re
import time
import uuid  # Add this import for generating unique IDs

from apify_client import ApifyClient
from dateutil.relativedelta import relativedelta
import aiohttp
import openai
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response, flash
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from flask_session import Session
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional as OptionalValidator

from config import settings
from utils.case_studies import (
    find_relevant_case_studies_from_sitemap,
    get_relevant_case_studies,
)

# Import the core functionality from deep_research.py
from deep_research import (
    Target, PerplexityMessage, PerplexityChoice, PerplexityResponse,
    get_recent_years_range, fetch_topic_research, get_linkedin_profiles_batch,
    generate_gpt_report, generate_email_messages, generate_linkedin_messages,
    fetch_case_studies, fetch_linkedin_posts_batch, process_research_pipeline,
    extract_name_from_linkedin_url, async_request, extract_message_content,
    create_download_csv
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],  # Log to console
)
logger = logging.getLogger("deep_research")

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
csrf = CSRFProtect(app)

# Configure JSON encoding to handle complex objects
class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle Target objects and other complex types."""
    def default(self, obj):
        # Handle Target objects
        if hasattr(obj, 'to_dict') and callable(getattr(obj, 'to_dict')):
            return obj.to_dict()
        # Handle datetime objects
        elif hasattr(obj, 'isoformat') and callable(getattr(obj, 'isoformat')):
            return obj.isoformat()
        # Handle sets by converting to lists
        elif isinstance(obj, set):
            return list(obj)
        # Handle bytes by converting to strings
        elif isinstance(obj, bytes):
            try:
                return obj.decode('utf-8')
            except UnicodeDecodeError:
                return str(obj)
        # Fall back to parent implementation (will raise TypeError for unhandled types)
        return super().default(obj)

app.json_encoder = CustomJSONEncoder

# Session configuration - important for storing large results
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join(os.getcwd(), 'flask_session')
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
Session(app)  # Initialize Flask-Session

# Directory for storing research results
RESULTS_DIR = os.path.join(os.getcwd(), 'research_results')
os.makedirs(RESULTS_DIR, exist_ok=True)

def sanitize_for_json(data):
    """
    Recursively sanitize data to ensure it's JSON serializable.
    
    Args:
        data: Any Python object that needs sanitizing
        
    Returns:
        A JSON-serializable version of the data
    """
    if data is None:
        return None
    elif isinstance(data, (str, int, float, bool)):
        return data
    elif isinstance(data, bytes):
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            return str(data)
    elif isinstance(data, dict):
        return {sanitize_for_json(key): sanitize_for_json(value) for key, value in data.items()}
    elif isinstance(data, (list, tuple, set)):
        return [sanitize_for_json(item) for item in data]
    elif hasattr(data, 'to_dict') and callable(getattr(data, 'to_dict')):
        return sanitize_for_json(data.to_dict())
    elif hasattr(data, 'isoformat') and callable(getattr(data, 'isoformat')):
        return data.isoformat()
    else:
        # For any other type, convert to string
        try:
            return str(data)
        except Exception as e:
            logger.warning(f"Could not convert {type(data)} to string: {str(e)}")
            return f"[Unserializable object of type: {type(data).__name__}]"

def save_research_results(results):
    """Save research results to a file and return the ID."""
    result_id = str(uuid.uuid4())
    result_path = os.path.join(RESULTS_DIR, f"{result_id}.json")
    
    try:
        # Sanitize the data before serializing
        sanitized_results = sanitize_for_json(results)
        
        with open(result_path, 'w') as f:
            json.dump(sanitized_results, f, cls=CustomJSONEncoder)
        return result_id
    except Exception as e:
        logger.error(f"Error saving research results: {str(e)}")
        raise

def load_research_results(result_id):
    """Load research results from a file."""
    result_path = os.path.join(RESULTS_DIR, f"{result_id}.json")
    
    try:
        if os.path.exists(result_path):
            with open(result_path, 'r') as f:
                return json.load(f)
        return None
    except Exception as e:
        logger.error(f"Error loading research results: {str(e)}")
        return None

def delete_research_results(result_id):
    """Delete research results file."""
    if not result_id:
        return
        
    result_path = os.path.join(RESULTS_DIR, f"{result_id}.json")
    
    try:
        if os.path.exists(result_path):
            os.remove(result_path)
    except Exception as e:
        logger.error(f"Error deleting research results: {str(e)}")

# Form for the main research page
class ResearchForm(FlaskForm):
    """Form for collecting research parameters."""
    urls = TextAreaField('LinkedIn URLs (one per line)', 
                        validators=[DataRequired()],
                        default="https://www.linkedin.com/in/clarissa-tovar/ \nhttps://www.linkedin.com/in/nathanpoekert/")
    topic = StringField('Research Topic', 
                       validators=[DataRequired()],
                       default="Whole Foods")
    user_name = StringField('Your Name', validators=[OptionalValidator()])
    user_title = StringField('Your Title', validators=[OptionalValidator()])
    user_company = StringField('Company Name', 
                              validators=[OptionalValidator()],
                              default="Popular Pays, a Lightricks brand")
    user_email = StringField('Your Email', validators=[OptionalValidator()])
    user_phone = StringField('Your Phone', validators=[OptionalValidator()])
    submit = SubmitField('Dive Deep')

@app.route('/', methods=['GET', 'POST'])
def index():
    """Main page for Deep Research Flask app."""
    form = ResearchForm()
    
    if form.validate_on_submit():
        # Store form data in session
        session['urls'] = form.urls.data
        session['topic'] = form.topic.data
        session['user_name'] = form.user_name.data
        session['user_title'] = form.user_title.data
        session['user_company'] = form.user_company.data
        session['user_email'] = form.user_email.data
        session['user_phone'] = form.user_phone.data
        
        # Redirect to processing page
        return redirect(url_for('process_research'))
    
    # If results exist in session, display them
    if 'result_id' in session and session['result_id']:
        return redirect(url_for('results'))
    
    return render_template('index.html', form=form)

@app.route('/process', methods=['GET'])
def process_research():
    """Process the research request."""
    if 'urls' not in session or 'topic' not in session:
        flash('Please enter a topic and at least one URL to begin research.')
        return redirect(url_for('index'))
    
    # Clear any previous results
    if 'result_id' in session:
        delete_research_results(session['result_id'])
        session.pop('result_id', None)
    
    # Render the processing page
    return render_template('processing.html')

@app.route('/run_research', methods=['POST'])
def run_research():
    """Run the research process asynchronously."""
    try:
        urls = [url.strip() for url in session['urls'].split('\n') if url.strip()]
        topic = session['topic']
        
        # Get user info from session
        user_info = {
            "name": session.get('user_name', ''),
            "title": session.get('user_title', ''),
            "company": session.get('user_company', 'Popular Pays, a Lightricks brand'),
            "email": session.get('user_email', ''),
            "phone": session.get('user_phone', ''),
        }
        
        # Create a modified version of process_research_pipeline that uses user_info
        async def run_pipeline():
            # Call the original pipeline function
            results = await process_research_pipeline(urls, topic)
            
            # Validate the results structure
            if isinstance(results, dict):
                # If it's an error dictionary with just an "error" key, wrap it for consistency
                if "error" in results and len(results) == 1:
                    return results
                    
                # Otherwise, it's a proper results dictionary, so add user_info to each result
                for url, result in results.items():
                    if isinstance(result, dict) and "report" in result:
                        result["report"]["user_info"] = user_info
                        
                        # Convert Target objects to dictionaries for JSON serialization
                        if "target" in result and isinstance(result["target"], Target):
                            result["target"] = result["target"].to_dict()
            
            return results
        
        # Run the research pipeline
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(run_pipeline())
        loop.close()
        
        # Store results in filesystem and ID in session
        result_id = save_research_results(results)
        session['result_id'] = result_id
        session['topic'] = topic  # Store topic for displaying on results page
        
        return jsonify({'success': True, 'redirect': url_for('results')})
    except Exception as e:
        # Log the error and return an error response
        logging.error(f"Error in run_research: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/results', methods=['GET'])
def results():
    """Display research results."""
    # Check for redirect loop
    redirect_count = session.get('redirect_count', 0)
    if redirect_count > 3:
        # Reset counter and show error page instead of redirecting again
        session['redirect_count'] = 0
        return render_template('error.html', 
                              error="Too many redirects occurred. There was an error processing your research request.",
                              details="Check the application logs for more information.")
    
    if 'result_id' not in session or not session['result_id']:
        # Increment redirect counter
        session['redirect_count'] = redirect_count + 1
        flash('No research results available. Please start a new research.')
        return redirect(url_for('index'))
    
    # Reset redirect counter on successful page load
    session['redirect_count'] = 0
    
    # Load results from filesystem
    results = load_research_results(session['result_id'])
    if not results:
        flash('Research results not found. Please start a new research.')
        return redirect(url_for('index'))
        
    topic = session.get('topic', 'Unknown Topic')
    
    # Check if results is a string or an error dictionary (not URL-keyed)
    if isinstance(results, str) or (isinstance(results, dict) and "error" in results and len(results) == 1):
        error_message = results if isinstance(results, str) else results.get("error", "Unknown error")
        flash(f'Research error: {error_message}')
        return redirect(url_for('index'))
    
    # Count successful and failed profiles
    success_count = sum(1 for r in results.values() if isinstance(r, dict) and "error" not in r)
    total_count = len(results)
    
    # Get one comprehensive research report, safely
    any_report = {}
    for result in results.values():
        if isinstance(result, dict) and "report" in result:
            any_report = result.get("report", {})
            break
    
    # Helper function to get target name (for sorting)
    def get_name_from_target(target_dict):
        if not target_dict:
            return "Unknown"
        
        try:
            # Handle target being a dict or Target object
            if isinstance(target_dict, dict):
                return target_dict.get("name", "Unknown")
            else:
                # Assume Target object (should not happen here as we're converting to dict)
                return target_dict.name
        except Exception:
            return "Unknown"

    # Render the results template
    return render_template(
        'results.html',
        results=results,
        topic=topic,
        success_count=success_count,
        total_count=total_count,
        any_report=any_report,
        Target=Target,  # Pass Target class for template use
        extract_name_from_linkedin_url=extract_name_from_linkedin_url,
    )

@app.route('/download_csv', methods=['GET'])
def download_csv_route():
    """Generate and download CSV of research results."""
    if 'result_id' not in session or not session['result_id']:
        flash('No research results available.')
        return redirect(url_for('results'))
    
    # Load results from filesystem
    results = load_research_results(session['result_id'])
    if not results:
        flash('Research results not found.')
        return redirect(url_for('index'))
    
    # Create CSV data
    csv_data = create_download_csv(results)
    
    # Create a response with the CSV data
    response = Response(
        csv_data,
        mimetype='text/csv',
        headers={
            'Content-Disposition': 'attachment; filename=outreach_messages.csv'
        }
    )
    
    return response

@app.route('/clear_results', methods=['POST'])
def clear_results():
    """Clear the research results from session and filesystem."""
    if 'result_id' in session:
        delete_research_results(session['result_id'])
        session.pop('result_id', None)
    
    return redirect(url_for('index'))

# Error handlers
@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle request entity too large errors."""
    return render_template('error.html', 
                          error="The data submitted was too large to process.",
                          details="Try processing fewer URLs or a simpler topic."), 413

@app.errorhandler(500)
def internal_server_error(error):
    """Handle internal server errors."""
    return render_template('error.html', 
                          error="An internal server error occurred.",
                          details="Please check the application logs for more information."), 500

@app.errorhandler(JSONDecodeError)
def json_decode_error(error):
    """Handle JSON decode errors."""
    return render_template('error.html', 
                          error="Error processing JSON data.",
                          details=str(error)), 400

# Create error template if it doesn't exist
if not os.path.exists(os.path.join(app.template_folder, 'error.html')):
    error_template = """{% extends "base.html" %}

{% block title %}Error - Deep Research{% endblock %}

{% block content %}
<div class="container mt-5">
    <div class="row">
        <div class="col-md-8 offset-md-2">
            <div class="card">
                <div class="card-header bg-danger text-white">
                    <h2>Error</h2>
                </div>
                <div class="card-body">
                    <h4>{{ error }}</h4>
                    <p>{{ details }}</p>
                    <a href="{{ url_for('index') }}" class="btn btn-primary mt-3">Return to Homepage</a>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}"""
    
    os.makedirs(app.template_folder, exist_ok=True)
    with open(os.path.join(app.template_folder, 'error.html'), 'w') as f:
        f.write(error_template)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000) 