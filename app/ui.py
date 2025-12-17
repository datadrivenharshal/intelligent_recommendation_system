import streamlit as st
import requests
import pandas as pd
import json

# Configure page
st.set_page_config(
    page_title="SHL Assessment Recommender",
    layout="wide"
)

# Title and description
st.title("SHL Intelligent Assessment Recommender")
st.markdown("""
Enter a job description or natural language query to get recommended SHL assessments.
The system uses AI to understand your requirements and suggest the most relevant tests.
""")

# Sidebar for API configuration
with st.sidebar:
    st.header("Configuration")
    api_url = st.text_input(
        "API URL",
        value="http://localhost:8000",
        help="URL of the recommendation API"
    )
    
    st.divider()
    st.markdown("### Example Queries")
    example_queries = [
        "I need to hire Java developers who can collaborate with business teams",
        "Looking for Python developers with SQL and JavaScript skills",
        "Hiring an analyst - need cognitive and personality tests"
    ]
    
    for i, query in enumerate(example_queries):
        if st.button(f"Example {i+1}", key=f"example_{i}"):
            st.session_state.query = query

# Main input area
col1, col2 = st.columns([3, 1])

with col1:
    query = st.text_area(
        "Enter Job Description or Query:",
        value=st.session_state.get("query", ""),
        height=150,
        placeholder="e.g., 'Need a Java developer who is good in collaborating with external teams and stakeholders.'"
    )

with col2:
    st.markdown("### Settings")
    max_results = st.slider("Max results", 5, 10, 8)
    st.divider()
    submit = st.button("Get Recommendations", type="primary", use_container_width=True)

# Display results
if submit and query:
    with st.spinner("Finding the best assessments for your needs..."):
        try:
            # Call API
            response = requests.post(
                f"{api_url}/recommend",
                json={"query": query},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                assessments = data.get("recommended_assessments", [])
                
                if assessments:
                    st.success(f"Found {len(assessments)} relevant assessments")
                    
                    # Convert to DataFrame for display
                    df_data = []
                    for i, assessment in enumerate(assessments[:max_results], 1):
                        df_data.append({
                            "#": i,
                            "Assessment Name": assessment["name"],
                            "Description": assessment["description"][:100] + "..." if len(assessment["description"]) > 100 else assessment["description"],
                            "Test Types": ", ".join(assessment["test_type"]),
                            "Duration": f"{assessment['duration']} min",
                            "Adaptive": assessment["adaptive_support"],
                            "Remote": assessment["remote_support"],
                            "URL": assessment["url"]
                        })
                    
                    df = pd.DataFrame(df_data)
                    
                    # Display table
                    st.dataframe(
                        df,
                        column_config={
                            "URL": st.column_config.LinkColumn("URL", display_text="🔗 Open")
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # Download button
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Results as CSV",
                        data=csv,
                        file_name="shl_recommendations.csv",
                        mime="text/csv"
                    )
                    
                    # Show raw JSON
                    with st.expander("View Raw API Response"):
                        st.json(data)
                
                else:
                    st.warning("No assessments found. Try refining your query.")
            
            else:
                st.error(f"API Error: {response.status_code}")
                st.json(response.json())
        
        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to API. Make sure the API is running.")
            st.info(f"API URL: {api_url}")
        
        except Exception as e:
            st.error(f"Error: {str(e)}")

# Health check
with st.expander("🔧 API Status"):
    if st.button("Check API Health"):
        try:
            health_response = requests.get(f"{api_url}/health", timeout=5)
            if health_response.status_code == 200:
                st.success("API is healthy and running")
            else:
                st.error("API is not responding properly")
        except:
            st.error("Cannot connect to API")

# Footer
st.divider()
st.markdown("""
---
**About this system:**
- Uses hybrid retrieval (semantic + keyword search)
- Balances technical and behavioral assessments
- Reranks results using AI for better relevance
- Based on SHL's catalog of individual test solutions
""")