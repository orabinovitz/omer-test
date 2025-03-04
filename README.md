# Deep Research - Flask Application

This is a Flask-based application for conducting deep research on LinkedIn profiles and topics. The application allows you to enter LinkedIn profile URLs and a research topic, and then generates comprehensive reports, personalized emails, and LinkedIn messages.

## Features

- Research topics using Perplexity API
- Process LinkedIn profiles to extract information
- Fetch recent LinkedIn posts for profiles
- Generate comprehensive research reports
- Create personalized emails and LinkedIn messages
- Include relevant case studies in research
- Download results as CSV

## Prerequisites

- Python 3.10 or higher
- Required API keys (configured in `.env` file):
  - OpenAI API key
  - Perplexity API key
  - Apify API key
  - (Optional) Additional API keys as needed

## Installation

1. Clone the repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure your API keys in the `.env` file (see `.env` file for format)

## Running the Application

To run the Flask application:

```bash
python app.py
```

The application will be available at http://127.0.0.1:5000/

## Usage

1. Enter LinkedIn profile URLs (one per line) in the text area
2. Enter a research topic
3. (Optional) Fill in your information for email/message signatures
4. Click "Dive Deep" to start the research process
5. Wait for the research to complete
6. View and download the results

## Project Structure

- `app.py`: Main Flask application
- `deep_research.py`: Core research functionality
- `config.py`: Configuration handling
- `templates/`: HTML templates
- `static/`: Static files (CSS, JS, images)
- `utils/`: Utility functions

## Note on Environment Variables

The application uses environment variables for API keys. These are loaded from the `.env` file. The environment variables are prefixed with `DYNACONF_` in the `.env` file to maintain compatibility with the original codebase.

## License

Proprietary - All rights reserved 