"""
API PRD Generator - Streamlit App
Generates API Integration PRDs using Claude AI.
Optionally tests real APIs and includes actual response examples.
"""

import streamlit as st
import anthropic
import re
import requests
import html2text
import hmac
import hashlib
import base64
import time
import json

# Page config
st.set_page_config(
    page_title="API PRD Generator",
    page_icon="📄",
    layout="wide"
)

# Styling
st.markdown("""
<style>
    .stButton > button {
        width: 100%;
        background-color: #FF6B6B;
        color: white;
    }
    .output-box {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# System prompt for PRD generation
SYSTEM_PROMPT = """You are an API documentation analyst.
When given API documentation content, you will:

1. Analyze the API documentation
2. Generate a complete Integration PRD with:
   - Executive Summary (objective, provider, complexity, key endpoints)
   - Quick Reference table (base URL, auth method, rate limits, response format)
   - Authentication details (methods, headers, tokens)
   - All endpoints with:
     - HTTP method and path
     - Purpose
     - Request parameters (table format)
     - Response schema/example
     - Endpoint-specific errors
   - Sequence Diagram (REQUIRED - must include a ```mermaid code block) showing:
     - Main request flow from application to API
     - Authentication/signature generation step
     - Rate limiting check
     - Success and error response paths (including retries for 404, backoff for 429)
   - Data models (key objects used across endpoints)
   - Error handling strategy (table of codes, meanings, actions)
   - Rate limiting strategy (limits, headers, retry approach)
   - Implementation checklist (actionable items for dev team)
   - Open questions (ambiguities or missing info)

When real API response examples are provided, use them instead of documented examples.
Clearly mark which examples are from live API testing vs documentation.

Keep the PRD concise but actionable for a development team.

Output format: Markdown"""

# Provider configurations
PROVIDERS = {
    "none": {
        "name": "None (Documentation Only)",
        "auth_type": None,
    },
    "elliptic": {
        "name": "Elliptic",
        "auth_type": "hmac",
        "base_url": "https://aml-api.elliptic.co",
        "test_endpoint": "/v2/analyses/synchronous",
    },
    "generic_bearer": {
        "name": "Generic (Bearer Token)",
        "auth_type": "bearer",
    },
    "generic_api_key": {
        "name": "Generic (API Key Header)",
        "auth_type": "api_key",
    },
}


def fetch_url_content(url: str) -> str:
    """Fetch URL and convert HTML to readable text."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; PRDGenerator/1.0)"
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.body_width = 0

    content = h.handle(response.text)

    max_chars = 100000
    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n[Content truncated due to length...]"

    return content


def elliptic_sign_request(method: str, path: str, body: str, secret: str) -> tuple:
    """Generate Elliptic API signature."""
    timestamp = int(time.time() * 1000)

    path_lower = path.lower()

    if body and body.strip():
        try:
            parsed = json.loads(body)
            str_body = json.dumps(parsed, separators=(',', ':'))
        except json.JSONDecodeError:
            str_body = '{}'
    else:
        str_body = '{}'

    text = f"{timestamp}{method.upper()}{path_lower}{str_body}"

    key = base64.b64decode(secret)
    signature = hmac.new(key, text.encode('utf-8'), hashlib.sha256)
    signature_b64 = base64.b64encode(signature.digest()).decode('utf-8')

    return signature_b64, timestamp


def test_elliptic_api(api_key: str, api_secret: str, body: str) -> dict:
    """Test Elliptic API and return response."""
    base_url = "https://aml-api.elliptic.co"
    path = "/v2/analyses/synchronous"

    # Normalize the body JSON
    try:
        parsed_body = json.loads(body)
        body = json.dumps(parsed_body, separators=(',', ':'))
    except json.JSONDecodeError:
        return {
            "status_code": 0,
            "response": "Invalid JSON body",
            "success": False
        }

    signature, timestamp = elliptic_sign_request("POST", path, body, api_secret)

    headers = {
        "Content-Type": "application/json",
        "x-access-key": api_key,
        "x-access-sign": signature,
        "x-access-timestamp": str(timestamp)
    }

    response = requests.post(f"{base_url}{path}", headers=headers, data=body, timeout=30)

    return {
        "status_code": response.status_code,
        "response": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text,
        "success": response.status_code == 200
    }


def test_generic_api(endpoint: str, method: str, auth_type: str, auth_value: str, body: str = None) -> dict:
    """Test generic API with bearer or API key auth."""
    headers = {"Content-Type": "application/json"}

    if auth_type == "bearer":
        headers["Authorization"] = f"Bearer {auth_value}"
    elif auth_type == "api_key":
        headers["x-api-key"] = auth_value

    if method.upper() == "GET":
        response = requests.get(endpoint, headers=headers, timeout=30)
    else:
        response = requests.post(endpoint, headers=headers, data=body, timeout=30)

    return {
        "status_code": response.status_code,
        "response": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text,
        "success": 200 <= response.status_code < 300
    }


def format_api_response(result: dict) -> str:
    """Format API test result for inclusion in PRD."""
    if not result["success"]:
        return f"API test failed with status {result['status_code']}: {result['response']}"

    response_json = json.dumps(result["response"], indent=2)

    # Truncate if too long
    if len(response_json) > 5000:
        response_json = response_json[:5000] + "\n... [truncated]"

    return f"""### Live API Response (Status: {result['status_code']})

```json
{response_json}
```
"""


def generate_prd(url: str, api_key: str, docs_content: str, api_test_result: str = None) -> str:
    """Generate PRD using Claude."""
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Generate a complete API Integration PRD based on the following API documentation.

Source URL: {url}

## API Documentation Content:

{docs_content}
"""

    if api_test_result:
        prompt += f"""

---

## Live API Test Results

The following is a real response from testing the API:

{api_test_result}

Please incorporate this real response into the PRD as an example, clearly marking it as "Live API Response".
"""

    prompt += """
---

Please generate a comprehensive but concise Integration PRD that includes:
- Executive summary (objective, provider, complexity)
- Quick reference table (base URL, auth, rate limits)
- Authentication details
- All key endpoints with request/response examples (use live examples where available)
- A Mermaid sequence diagram (```mermaid code block) showing the request flow, auth, rate limiting, and error handling paths
- Data models
- Error handling strategy
- Rate limiting strategy
- Implementation checklist
- Open questions

Make it actionable for a development team."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text


def validate_prd(api_key: str, prd_content: str, docs_content: str, api_test_result: str = None) -> str:
    """Validate PRD against source documentation."""
    client = anthropic.Anthropic(api_key=api_key)

    validation_prompt = f"""You are a technical reviewer validating an API Integration PRD against its source documentation.

## Generated PRD:

{prd_content}

---

## Source Documentation:

{docs_content}
"""

    if api_test_result:
        validation_prompt += f"""

---

## Live API Response (Ground Truth):

{api_test_result}
"""

    validation_prompt += """

---

## Your Task

Review the PRD for accuracy against the source documentation and live API response (if provided).

For each section of the PRD, provide:

### 1. Accuracy Check
| Section | Status | Issue (if any) |
|---------|--------|----------------|
| Base URL | ✅ Verified / ⚠️ Issue / ❓ Unverifiable | Description |
| Auth Method | ... | ... |
| Endpoints | ... | ... |
| Request Schema | ... | ... |
| Response Schema | ... | ... |
| Error Codes | ... | ... |
| Rate Limits | ... | ... |

### 2. Discrepancies Found
List any specific discrepancies between the PRD and source docs:
- [Field/Section]: PRD says X, but docs say Y

### 3. Inferred Content
List sections where the PRD contains information NOT found in the source docs (marked as inferred/assumed):
- [Section]: This appears to be inferred because...

### 4. Missing Information
List important details from the docs that are missing from the PRD:
- [Topic]: The docs mention X but PRD doesn't cover it

### 5. Live Response Validation (if applicable)
Compare PRD examples against the actual API response:
- Fields match: [list]
- Fields differ: [list with differences]
- Fields missing from PRD: [list]

### 6. Confidence Score
Overall confidence in PRD accuracy: [HIGH / MEDIUM / LOW]
Reasoning: [brief explanation]

### 7. Recommended Fixes
Prioritized list of corrections needed:
1. [Most critical fix]
2. [Next fix]
...

Be thorough and specific. Reference exact field names and values when noting discrepancies."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": validation_prompt}]
    )

    return response.content[0].text


def correct_prd(api_key: str, prd_content: str, validation_result: str, docs_content: str, api_test_result: str = None) -> str:
    """Correct PRD based on validation feedback."""
    client = anthropic.Anthropic(api_key=api_key)

    correction_prompt = f"""You are an API documentation analyst tasked with correcting a PRD based on validation feedback.

## Current PRD (needs corrections):

{prd_content}

---

## Validation Report (issues to fix):

{validation_result}

---

## Source Documentation (ground truth):

{docs_content}
"""

    if api_test_result:
        correction_prompt += f"""

---

## Live API Response (ground truth):

{api_test_result}
"""

    correction_prompt += """

---

## Your Task

Generate a CORRECTED version of the PRD that addresses ALL issues identified in the validation report.

Focus on:
1. Fix all discrepancies between the PRD and source documentation
2. Remove or correct any inferred content that was flagged as inaccurate
3. Add missing information that was identified
4. Ensure response schemas match the live API response (if provided)
5. Address every item in the "Recommended Fixes" section

Output the complete corrected PRD in markdown format. Do not include explanations about what you changed - just output the corrected PRD."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": correction_prompt}]
    )

    return response.content[0].text


def parse_confidence_score(validation_result: str) -> str:
    """Extract confidence score (HIGH/MEDIUM/LOW) from validation result."""
    match = re.search(r'confidence[^:]*:\s*\*?\*?(HIGH|MEDIUM|LOW)\*?\*?', validation_result, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return "LOW"


def get_api_key():
    """Get API key from secrets or user input."""
    if "ANTHROPIC_API_KEY" in st.secrets:
        return st.secrets["ANTHROPIC_API_KEY"], True
    import os
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"], True
    return None, False


def main():
    st.title("📄 API PRD Generator")
    st.markdown("Generate Integration PRDs with optional live API testing")

    team_api_key, has_team_key = get_api_key()

    # Sidebar for settings
    with st.sidebar:
        st.header("Settings")

        if has_team_key:
            st.success("✓ Claude API key configured")
            claude_api_key = team_api_key
        else:
            claude_api_key = st.text_input(
                "Claude API Key",
                type="password",
                help="Get your API key from console.anthropic.com"
            )

        st.markdown("---")

        enable_validation = st.checkbox(
            "Enable PRD Validation",
            value=True,
            help="Run a second pass to validate PRD accuracy against source docs"
        )

        enable_correction = st.checkbox(
            "Enable Auto-Correction",
            value=True,
            help="Automatically correct PRD if validation finds issues"
        )

        max_correction_attempts = st.number_input(
            "Max Correction Attempts",
            min_value=1,
            max_value=5,
            value=2,
            help="Maximum correction iterations before stopping"
        )

        st.markdown("---")
        st.markdown("### About")
        st.markdown(
            "This tool generates API Integration PRDs "
            "using Claude AI. Optionally test the real API "
            "to include live response examples."
        )

    # Main content - two columns
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("API Documentation")

        url = st.text_input(
            "Documentation URL",
            placeholder="https://developers.example.com/api/reference",
            help="URL to the API documentation"
        )

        with st.expander("Example URLs"):
            st.markdown("""
            - `https://developers.elliptic.co/reference/analysissync`
            - `https://stripe.com/docs/api`
            - `https://docs.github.com/en/rest`
            """)

    with col2:
        st.subheader("API Testing (Optional)")

        provider = st.selectbox(
            "API Provider",
            options=list(PROVIDERS.keys()),
            format_func=lambda x: PROVIDERS[x]["name"],
            help="Select provider for live API testing"
        )

        api_test_config = {}

        if provider == "elliptic":
            api_test_config["api_key"] = st.text_input(
                "Elliptic API Key",
                type="password",
                help="x-access-key header value"
            )
            api_test_config["api_secret"] = st.text_input(
                "Elliptic API Secret",
                type="password",
                help="Base64-encoded secret for HMAC signing"
            )

            default_body = '''{
  "subject": {
    "asset": "holistic",
    "blockchain": "holistic",
    "type": "transaction",
    "hash": "f4184fc596403b9d638783cf57adfe4c75c605f6356fbc91338530e9831e9e16",
    "output_type": "address",
    "output_address": "1Q2TWHE3GMdB6BZKafqwxXtWAWgFt5Jvm3"
  },
  "type": "source_of_funds",
  "customer_reference": "prd-generator-test"
}'''
            with st.expander("Request Body", expanded=True):
                api_test_config["body"] = st.text_area(
                    "JSON Body",
                    value=default_body,
                    height=250,
                    help="Edit the JSON body for the API test request"
                )

        elif provider in ["generic_bearer", "generic_api_key"]:
            api_test_config["endpoint"] = st.text_input(
                "Test Endpoint URL",
                placeholder="https://api.example.com/endpoint",
            )
            api_test_config["method"] = st.selectbox(
                "HTTP Method",
                options=["GET", "POST"]
            )
            api_test_config["auth_value"] = st.text_input(
                "API Key / Token",
                type="password",
            )
            if api_test_config["method"] == "POST":
                api_test_config["body"] = st.text_area(
                    "Request Body (JSON)",
                    placeholder='{"key": "value"}'
                )

    st.markdown("---")

    generate_btn = st.button("Generate PRD", type="primary", use_container_width=True)

    if generate_btn:
        if not claude_api_key:
            st.error("Please enter your Claude API key in the sidebar")
            return

        if not url:
            st.error("Please enter an API documentation URL")
            return

        if not url.startswith(("http://", "https://")):
            st.error("Please enter a valid URL starting with http:// or https://")
            return

        try:
            # Step 1: Fetch documentation
            with st.spinner("Fetching API documentation..."):
                docs_content = fetch_url_content(url)
            st.success("✓ Documentation fetched")

            # Step 2: Test API (if configured)
            api_test_result = None

            if provider == "elliptic" and api_test_config.get("api_key") and api_test_config.get("api_secret"):
                with st.spinner("Testing Elliptic API..."):
                    result = test_elliptic_api(
                        api_test_config["api_key"],
                        api_test_config["api_secret"],
                        api_test_config.get("body", "{}")
                    )
                    if result["success"]:
                        st.success(f"✓ API test successful (Risk Score: {result['response'].get('risk_score', 'N/A')})")
                        api_test_result = format_api_response(result)
                    else:
                        st.warning(f"API test failed: {result['status_code']}")

            elif provider in ["generic_bearer", "generic_api_key"] and api_test_config.get("endpoint") and api_test_config.get("auth_value"):
                with st.spinner("Testing API..."):
                    result = test_generic_api(
                        api_test_config["endpoint"],
                        api_test_config.get("method", "GET"),
                        "bearer" if provider == "generic_bearer" else "api_key",
                        api_test_config["auth_value"],
                        api_test_config.get("body")
                    )
                    if result["success"]:
                        st.success("✓ API test successful")
                        api_test_result = format_api_response(result)
                    else:
                        st.warning(f"API test failed: {result['status_code']}")

            # Step 3: Generate PRD
            with st.spinner("Generating PRD with Claude..."):
                prd_content = generate_prd(url, claude_api_key, docs_content, api_test_result)

            st.success("✓ PRD generated successfully!")

            # Step 4: Validate and correct PRD (if enabled)
            validation_result = None
            correction_count = 0

            if enable_validation:
                with st.spinner("Validating PRD accuracy..."):
                    validation_result = validate_prd(claude_api_key, prd_content, docs_content, api_test_result)

                # Auto-correction loop
                if enable_correction:
                    confidence = parse_confidence_score(validation_result)

                    while confidence != "HIGH" and correction_count < max_correction_attempts:
                        correction_count += 1
                        with st.spinner(f"Correcting PRD (attempt {correction_count}/{max_correction_attempts})..."):
                            prd_content = correct_prd(
                                claude_api_key,
                                prd_content,
                                validation_result,
                                docs_content,
                                api_test_result
                            )

                        with st.spinner("Re-validating PRD..."):
                            validation_result = validate_prd(claude_api_key, prd_content, docs_content, api_test_result)

                        confidence = parse_confidence_score(validation_result)

                if correction_count > 0:
                    st.success(f"✓ Validation complete after {correction_count} correction(s)! (Confidence: {parse_confidence_score(validation_result)})")
                else:
                    st.success(f"✓ Validation complete! (Confidence: {parse_confidence_score(validation_result)})")

            # Display tabs
            if validation_result:
                tab1, tab2, tab3 = st.tabs(["📄 PRD Document", "✅ Validation Report", "📋 Raw Markdown"])
            else:
                tab1, tab2, tab3 = st.tabs(["📄 PRD Document", "✅ Validation Report", "📋 Raw Markdown"])

            with tab1:
                st.markdown(prd_content)

            with tab2:
                if validation_result:
                    st.markdown(validation_result)
                else:
                    st.info("Validation was skipped. Enable it in the sidebar to validate PRD accuracy.")

            with tab3:
                st.code(prd_content, language="markdown")

            # Download buttons
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button(
                    label="Download PRD",
                    data=prd_content,
                    file_name=f"PRD-{re.sub(r'[^a-zA-Z0-9]', '-', url)[:30]}.md",
                    mime="text/markdown"
                )
            with col_dl2:
                if validation_result:
                    st.download_button(
                        label="Download Validation Report",
                        data=validation_result,
                        file_name=f"Validation-{re.sub(r'[^a-zA-Z0-9]', '-', url)[:30]}.md",
                        mime="text/markdown"
                    )

        except requests.exceptions.RequestException as e:
            st.error(f"Failed to fetch URL: {str(e)}")
        except anthropic.AuthenticationError:
            st.error("Invalid Claude API key. Please check your key.")
        except anthropic.RateLimitError:
            st.error("Rate limit exceeded. Please wait and try again.")
        except Exception as e:
            st.error(f"Error: {str(e)}")


if __name__ == "__main__":
    main()
