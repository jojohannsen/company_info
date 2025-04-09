from fasthtml.common import *
import csv
import io
from typing import Optional
from starlette.responses import Response

# This is a placeholder for whatever "@z.py" actually does to get company addresses
def get_company_address(company_name: str) -> Optional[str]:
    # In a real application, this would call the actual address lookup logic
    # For demonstration, returning dummy addresses based on company name
    if not company_name.strip():
        return None
    return f"{company_name.strip().title()} HQ, 123 Business St, Industry City, CA 94000"

# Add some basic styling
css = """
.htmx-indicator {
    display: none;
}
.htmx-request .htmx-indicator {
    display: block;
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
"""

# Create the FastHTML app with styling and session support
app, rt = fast_app(
    hdrs=(Style(css),),
    secret_key="company-address-app-secret"  # Required for session support
)

@rt
def index():
    """Main page with form for company name input and results display"""
    form = Form(
        Div(
            Label("Enter company names (one per line):", 
                  Textarea(id="companies", name="companies", rows=10, cols=50,
                          placeholder="Enter each company name on a new line\nExample:\nApple Inc\nGoogle\nMicrosoft")),
            cls="form-group"
        ),
        Button("Get Addresses", type="submit"),
        hx_post="/process", 
        hx_target="#results",
        hx_indicator="#loading"
    )
    
    loading = Div("Processing...", id="loading", cls="htmx-indicator")
    
    download_btn = A("Download CSV", 
                    id="download-btn", 
                    cls="download-btn",
                    href="/download",
                    download="company_addresses.csv")

    results = Div(id="results")
    
    return Titled("Company Address Lookup", 
                  P("Enter company names and get their addresses in CSV format."),
                  form, 
                  loading,
                  H2("Results"),
                  download_btn,
                  results)

@rt
def process(companies: str, session):
    """Process the list of companies and return addresses in CSV format"""
    company_list = companies.strip().split('\n')
    
    # Process each company to get its address
    results = []
    for company in company_list:
        company = company.strip()
        if company:
            address = get_company_address(company)
            results.append((company, address or "Address not found"))
    
    # Store results in session for download
    session['csv_data'] = results
    
    # Create CSV string
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Company", "Address"])
    writer.writerows(results)
    csv_str = output.getvalue()
    
    # Display results in a formatted way
    return Div(
        P(f"Found addresses for {len(results)} companies."),
        Pre(csv_str, style="background-color: #f5f5f5; padding: 10px; border-radius: 4px;"),
        Script("document.getElementById('download-btn').classList.add('show');")
    )

@rt
def download(session):
    """Generate a downloadable CSV file"""
    results = session.get('csv_data', [])
    
    # Create CSV string
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Company", "Address"])
    writer.writerows(results)
    csv_str = output.getvalue()
    
    # Return a response with headers for file download
    headers = {
        'Content-Disposition': 'attachment; filename="company_addresses.csv"',
        'Content-Type': 'text/csv'
    }
    
    return Response(content=csv_str, headers=headers)

if __name__ == "__main__":
    serve() 