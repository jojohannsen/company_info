from fasthtml.common import *
import csv
import io
import requests
import os
import json
from typing import Optional, Tuple
from starlette.responses import Response
from agno.agent import Agent
from agno.models.anthropic import Claude
from io import StringIO

def get_company_address(company_name: str) -> Optional[Tuple[str, Optional[str]]]:
    if not company_name.strip():
        return None
    
    url = "https://api.tavily.com/search"
    token = os.environ.get('TAVILY_API_KEY')
    
    if not token:
        return (f"Error: TAVILY_API_KEY environment variable not set", None)
    
    payload = {
        "query": f"What is the mailing address for this company: {company_name}?",
        "topic": "general",
        "search_depth": "basic",
        "chunks_per_source": 3,
        "max_results": 1,
        "time_range": None,
        "days": 7,
        "include_answer": True,
        "include_raw_content": False,
        "include_images": False,
        "include_image_descriptions": False,
        "include_domains": [],
        "exclude_domains": []
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.request("POST", url, json=payload, headers=headers)
        response_data = json.loads(response.text)
        source_url = None
        if 'results' in response_data and response_data['results'] and 'url' in response_data['results'][0]:
            source_url = response_data['results'][0]['url']
        return (response_data.get('answer', f"No address found for {company_name}"), source_url)
    except Exception as e:
        return (f"Error: {str(e)}", None)

# Add some basic styling
css = """
.htmx-indicator {
    display: none;
    margin: 10px 0;
    color: #666;
    font-weight: bold;
}
.htmx-request .htmx-indicator {
    display: block;
}
.htmx-request .submit-button {
    pointer-events: none;
    opacity: 0.5;
}
.form-group {
    margin-bottom: 1rem;
}
textarea {
    width: 100%;
}
.download-btn {
    margin-top: 10px;
    display: none;
}
.download-btn.show {
    display: inline-block;
}
pre {
    white-space: pre-wrap;
    word-wrap: break-word;
}
#results {
    opacity: 0;
    transition: opacity 0.3s ease-in-out;
}
#results.show {
    opacity: 1;
}
.page-container {
    padding: 2rem;
}
.page-title {
    font-size: 1.5rem;
    margin-bottom: 0.5rem;
}
.format-example {
    color: #666;
    font-size: 0.9rem;
    margin-bottom: 1rem;
    font-family: monospace;
}
.main-container {
    display: flex;
    gap: 2rem;
    margin-top: 1rem;
}
.input-section {
    flex: 1;
    min-width: 300px;
}
.results-container {
    flex: 1;
    min-width: 300px;
    padding: 15px;
    border: 1px solid #dee2e6;
    border-radius: 4px;
    background-color: #f8f9fa;
}
.submit-button {
    padding: 10px 20px;
    background-color: #007bff;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.3s ease;
}
.submit-button:hover {
    background-color: #0056b3;
}
"""

# Create the FastHTML app with styling and session support
app, rt = fast_app(
    hdrs=(Style(css),),
    secret_key="company-address-app-secret"  # Required for session support
)

@rt
def index():
    """Main page with form for company name input and results display"""
    input_section = Div(
        Form(
            Div(
                Label("Enter company names (one per line):", 
                      Textarea(id="companies", name="companies", rows=10, cols=50,
                              placeholder="Example:\nApple Inc\nGoogle\nMicrosoft")),
                cls="form-group"
            ),
            Button("Get Addresses", type="submit", cls="submit-button", disabled="true",
                  hx_swap_oob="true",
                  hx_swap="outerHTML",
                  hx_indicator="#loading"),
            Div("Processing...", id="loading", cls="htmx-indicator"),
            hx_post="/process", 
            hx_target="#results",
            hx_indicator="#loading"
        ),
        A("Download CSV", 
          id="download-btn", 
          cls="download-btn",
          href="/download",
          download="company_addresses.csv"),
        cls="input-section"
    )

    results_container = Div(
        H2("Results"),
        Div(id="results"),
        cls="results-container"
    )

    main_container = Div(
        input_section,
        results_container,
        cls="main-container"
    )
    
    # Add script to enable button only when textarea has content
    init_script = Script("""
        document.querySelector('textarea').addEventListener('input', function() {
            const submitButton = document.querySelector('.submit-button');
            submitButton.disabled = !this.value.trim();
            submitButton.textContent = 'Get Addresses';
        });

        document.querySelector('form').addEventListener('htmx:beforeRequest', function() {
            const submitButton = document.querySelector('.submit-button');
            submitButton.textContent = 'Searching...';
            submitButton.disabled = true;
        });

        document.querySelector('form').addEventListener('htmx:afterRequest', function() {
            const submitButton = document.querySelector('.submit-button');
            submitButton.textContent = 'Get Addresses';
            submitButton.disabled = false;
        });
    """)
    
    return Div(
        H4("Company Address Lookup", cls="page-title"),
        P("Output format: company_name, street_address, city, state, zip, country, source_url", cls="format-example"),
        main_container,
        init_script,
        cls="page-container")

@rt
def process(companies: str, session):
    """Process the list of companies and return addresses in CSV format"""
    company_list = companies.strip().split('\n')
    
    # Process each company to get its address
    results = []
    for company in company_list:
        company = company.strip()
        if company:
            address, url = get_company_address(company)
            if address is None:
                results.append((company, "Address not found", None))
            else:
                results.append((company, address or "Address not found", url))
    
    # Store results in session for download
    session['csv_data'] = results
    
    # Create CSV string
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Company", "Address", "Source URL"])
    writer.writerows(results)
    csv_str = output.getvalue()
    model_name = "claude-3-7-sonnet-latest"
    agent = Agent(model=Claude(id=model_name))
    prompt = f"""This CSV string contains columns: company_name, address_text, source_url. 
    The 'address_text' column contains an english sentence that describes the address of the company.  
    Please extract the street address, city, state, zip, and country from the address_text.
    Return only the modified CSV string, do not include any other text.
    The output should be in the following format:
    company_name,street_address,city,state,zip,country,source_url

    <ORIGINAL_CSV>
    {csv_str}
    </ORIGINAL_CSV>
    """
    response = agent.run(prompt)
    csv_str = response.content
    csv_file = StringIO(csv_str)
    csv_reader = csv.reader(csv_file)

    csv_data = list(csv_reader)[1:]
    session['csv_data'] = csv_data
    # Display results in a formatted way
    return Div(
        P(f"Found addresses for {len(results)} companies."),
        Pre(csv_str, style="background-color: #f5f5f5; padding: 10px; border-radius: 4px;"),
        Script("""
            document.getElementById('download-btn').classList.add('show');
            document.getElementById('results').classList.add('show');
            document.querySelector('.results-container').scrollIntoView({ behavior: 'smooth' });
        """)
    )

@rt
def download(session):
    """Generate a downloadable CSV file"""
    results = session.get('csv_data', [])
    
    # Create CSV string
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Company", "Street Address", "City", "State", "Zip", "Country", "Source URL"])
    writer.writerows(results)
    csv_str = output.getvalue()
    
    # Clear the session data after use
    session.pop('csv_data', None)
    
    # Return a response with headers for file download
    headers = {
        'Content-Disposition': 'attachment; filename="company_addresses.csv"',
        'Content-Type': 'text/csv'
    }
    
    return Response(content=csv_str, headers=headers)

if __name__ == "__main__":
    serve() 