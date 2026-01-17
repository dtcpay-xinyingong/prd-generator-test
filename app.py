"""
API PRD Generator - Streamlit App
Generates API Integration PRDs using Claude AI.
"""

import streamlit as st
import anthropic
import re

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
When given an API documentation URL, you will:

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
   - Data models (key objects used across endpoints)
   - Error handling strategy (table of codes, meanings, actions)
   - Rate limiting strategy (limits, headers, retry approach)
   - Implementation checklist (actionable items for dev team)
   - Open questions (ambiguities or missing info)

Keep the PRD concise but actionable for a development team.

Output format: Markdown"""


def generate_prd(url: str, api_key: str) -> str:
    """Fetch API docs and generate PRD using Claude."""

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Generate a complete API Integration PRD for the API documented at: {url}

Please:
1. First, analyze the API documentation at that URL
2. Then generate a comprehensive but concise Integration PRD

Include:
- Executive summary (objective, provider, complexity)
- Quick reference table (base URL, auth, rate limits)
- Authentication details
- All key endpoints with request/response examples
- Data models
- Error handling strategy
- Rate limiting strategy
- Implementation checklist
- Open questions

Make it actionable for a development team."""

    with st.spinner("Fetching API documentation and generating PRD..."):
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

    return response.content[0].text


def get_api_key():
    """Get API key from secrets (team) or user input."""
    # Check for team API key in Streamlit secrets
    if "ANTHROPIC_API_KEY" in st.secrets:
        return st.secrets["ANTHROPIC_API_KEY"], True
    # Check environment variable
    import os
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"], True
    return None, False


def main():
    st.title("📄 API PRD Generator")
    st.markdown("Generate Integration PRDs for any API documentation URL")

    # Get API key (team or user)
    team_api_key, has_team_key = get_api_key()

    # Sidebar for settings
    with st.sidebar:
        st.header("Settings")

        if has_team_key:
            st.success("✓ Team API key configured")
            api_key = team_api_key
        else:
            api_key = st.text_input(
                "Anthropic API Key",
                type="password",
                help="Get your API key from console.anthropic.com"
            )

        st.markdown("---")
        st.markdown("### About")
        st.markdown(
            "This tool generates API Integration PRDs "
            "using Claude AI. Simply paste an API documentation "
            "URL and get a complete PRD for your development team."
        )

    # Main content
    st.subheader("Enter API Documentation URL")

    url = st.text_input(
        "API Documentation URL",
        placeholder="https://developers.example.com/api/reference",
        help="Paste the URL to the API documentation"
    )

    # Example URLs
    with st.expander("Example URLs"):
        st.markdown("""
        - `https://developers.elliptic.co/reference/analysissync`
        - `https://stripe.com/docs/api`
        - `https://docs.github.com/en/rest`
        """)

    generate_btn = st.button("Generate PRD", type="primary")

    # Generate PRD
    if generate_btn:
        if not api_key:
            st.error("Please enter your Anthropic API key in the sidebar")
            return

        if not url:
            st.error("Please enter an API documentation URL")
            return

        if not url.startswith(("http://", "https://")):
            st.error("Please enter a valid URL starting with http:// or https://")
            return

        try:
            prd_content = generate_prd(url, api_key)

            st.success("PRD generated successfully!")

            # Display tabs for different views
            tab1, tab2 = st.tabs(["📄 PRD Document", "📋 Raw Markdown"])

            with tab1:
                st.markdown(prd_content)

            with tab2:
                st.code(prd_content, language="markdown")

            # Download button
            st.download_button(
                label="Download PRD as Markdown",
                data=prd_content,
                file_name=f"PRD-{re.sub(r'[^a-zA-Z0-9]', '-', url)[:30]}.md",
                mime="text/markdown"
            )

        except anthropic.AuthenticationError:
            st.error("Invalid API key. Please check your Anthropic API key.")
        except anthropic.RateLimitError:
            st.error("Rate limit exceeded. Please wait a moment and try again.")
        except Exception as e:
            st.error(f"Error generating PRD: {str(e)}")


if __name__ == "__main__":
    main()
