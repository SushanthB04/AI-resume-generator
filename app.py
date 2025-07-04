import streamlit as st
import httpx
from fpdf import FPDF
import json
import re
from datetime import datetime
from typing import Dict, List, Optional

# Custom CSS for enhanced dark theme
def load_css():
    st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
    }
    .stSelectbox > div > div {
        background-color: #262730;
        color: #fafafa;
        border-radius: 8px;
    }
    .stTextInput > div > div > input {
        background-color: #262730;
        color: #fafafa;
        border: 1px solid #4a4a4a;
        border-radius: 6px;
    }
    .stTextArea > div > div > textarea {
        background-color: #262730;
        color: #fafafa;
        border: 1px solid #4a4a4a;
        border-radius: 6px;
    }
    .stButton > button {
        background-color: #ff4b4b;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        background-color: #ff6b6b;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(255, 75, 75, 0.3);
    }
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #fafafa;
    }
    .stSuccess {
        background-color: #1a4d3a;
        color: #fafafa;
        border-radius: 8px;
    }
    .stError {
        background-color: #4d1a1a;
        color: #fafafa;
        border-radius: 8px;
    }
    .stInfo {
        background-color: #1a3d4d;
        color: #fafafa;
        border-radius: 8px;
    }
    .stWarning {
        background-color: #4d3a1a;
        color: #fafafa;
        border-radius: 8px;
    }
    .stForm {
        background-color: #1a1a1a;
        border: 1px solid #333;
        border-radius: 12px;
        padding: 24px;
    }
    .stSlider > div > div {
        background-color: #262730;
    }
    .resume-preview {
        background-color: #1a1a1a;
        border: 1px solid #333;
        border-radius: 8px;
        padding: 20px;
        margin: 10px 0;
    }
    .section-header {
        color: #ff4b4b;
        font-weight: bold;
        margin-bottom: 10px;
    }
    .help-text {
        color: #888;
        font-size: 0.9em;
        font-style: italic;
    }
    </style>
    """, unsafe_allow_html=True)

# Configuration constants
@st.cache_data
def get_config():
    return {
        "AVAILABLE_MODELS": {
            "Mistral Large": "mistralai/mistral-large",
            "Meta Llama 3 405B Instruct": "meta-llama/llama-3-405b-instruct",
            "IBM Granite 13B Instruct": "ibm/granite-13b-instruct-v2",
            "IBM Granite 20B Instruct": "ibm/granite-20b-instruct-v1"
        },
        "AVAILABLE_FONTS": {
            "Arial": "Arial",
            "Times New Roman": "Times", 
            "Helvetica": "Helvetica",
            "Calibri": "Arial"  # Fallback to Arial
        },
        "RESUME_TEMPLATES": {
            "Professional": "professional",
            "Creative": "creative",
            "Technical": "technical",
            "Academic": "academic"
        },
        "WATSONX_URL": "https://us-south.ml.cloud.ibm.com",
        "API_VERSION": "2023-05-29"
    }

# Input validation functions
def validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone: str) -> bool:
    # Allow various phone formats
    pattern = r'^[\+]?[1-9][\d\s\-\(\)]{7,15}$'
    return re.match(pattern, phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')) is not None

def validate_linkedin(linkedin: str) -> bool:
    if not linkedin:
        return True  # Optional field
    pattern = r'^(https?://)?(www\.)?linkedin\.com/in/[a-zA-Z0-9-]+/?$'
    return re.match(pattern, linkedin) is not None

def validate_github(github: str) -> bool:
    if not github:
        return True  # Optional field
    pattern = r'^(https?://)?(www\.)?github\.com/[a-zA-Z0-9-]+/?$'
    return re.match(pattern, github) is not None

# Enhanced error handling and logging
class ResumeGeneratorError(Exception):
    pass

def safe_api_call(func, *args, **kwargs):
    """Wrapper for API calls with enhanced error handling"""
    try:
        return func(*args, **kwargs)
    except httpx.TimeoutException:
        raise ResumeGeneratorError("⏰ Request timed out. Please try again.")
    except httpx.ConnectError:
        raise ResumeGeneratorError("🌐 Connection error. Please check your internet connection.")
    except Exception as e:
        raise ResumeGeneratorError(f"❌ Unexpected error: {str(e)}")

# Get IAM Access Token with enhanced error handling
def get_iam_token(api_key: str) -> str:
    def _get_token():
        resp = httpx.post(
            "https://iam.cloud.ibm.com/identity/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "apikey": api_key,
                "grant_type": "urn:ibm:params:oauth:grant-type:apikey"
            },
            timeout=30.0
        )
        
        if resp.status_code != 200:
            if resp.status_code == 400:
                raise ResumeGeneratorError("❌ Invalid API key format")
            elif resp.status_code == 401:
                raise ResumeGeneratorError("❌ API key authentication failed")
            elif resp.status_code == 403:
                raise ResumeGeneratorError("❌ API key access denied")
            else:
                raise ResumeGeneratorError(f"❌ IAM token error [{resp.status_code}]: {resp.text}")
        
        return resp.json()["access_token"]
    
    return safe_api_call(_get_token)

# Enhanced resume generation with templates
def generate_resume(user_data: Dict, model_id: str, template_style: str) -> str:
    """Generate resume with enhanced prompting and template support"""
    
    # Validate required fields
    required_fields = ['name', 'role', 'skills', 'experience', 'education', 'phone', 'email']
    missing_fields = [field for field in required_fields if not user_data.get(field, '').strip()]
    
    if missing_fields:
        raise ResumeGeneratorError(f"❌ Missing required fields: {', '.join(missing_fields)}")
    
    # Validate email and phone
    if not validate_email(user_data['email']):
        raise ResumeGeneratorError("❌ Invalid email format")
    
    if not validate_phone(user_data['phone']):
        raise ResumeGeneratorError("❌ Invalid phone number format")
    
    # Generate template-specific prompt
    prompt = create_resume_prompt(user_data, template_style)
    
    # Get token and make API call
    api_key = st.secrets["ibm"]["api_key"]
    project_id = st.secrets["ibm"]["project_id"]
    
    token = get_iam_token(api_key)
    
    config = get_config()
    
    body = {
        "model_id": model_id,
        "input": prompt,
        "parameters": {
            "decoding_method": "greedy",
            "max_new_tokens": 1200,
            "temperature": 0.3,
            "top_p": 0.9,
            "repetition_penalty": 1.1
        },
        "project_id": project_id
    }
    
    def _generate():
        resp = httpx.post(
            f"{config['WATSONX_URL']}/ml/v1/text/generation?version={config['API_VERSION']}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=body,
            timeout=60.0
        )
        
        if resp.status_code == 404:
            raise ResumeGeneratorError("❌ Model not available. Try a different model.")
        elif resp.status_code == 403:
            raise ResumeGeneratorError("❌ Access denied. Check your project setup.")
        elif resp.status_code == 429:
            raise ResumeGeneratorError("❌ Rate limit exceeded. Please wait a moment and try again.")
        elif resp.status_code != 200:
            raise ResumeGeneratorError(f"❌ API error [{resp.status_code}]: {resp.text}")
        
        data = resp.json()
        if "results" not in data or not data["results"]:
            raise ResumeGeneratorError("❌ No response from model")
        
        generated_text = data["results"][0].get("generated_text", "").strip()
        if not generated_text:
            raise ResumeGeneratorError("❌ Empty response. Try again.")
        
        return generated_text
    
    return safe_api_call(_generate)

def create_resume_prompt(user_data: Dict, template_style: str) -> str:
    """Create template-specific resume prompts"""
    
    base_info = f"""
Name: {user_data['name']}
Role: {user_data['role']}
Phone: {user_data['phone']}
Email: {user_data['email']}
Location: {user_data.get('location', 'Not specified')}
Skills: {user_data['skills']}
Experience: {user_data['experience']}
Education: {user_data['education']}
Certifications: {user_data.get('certifications', 'None listed')}
"""
    
    if template_style == "professional":
        return f"""Create a professional, ATS-friendly resume with clean formatting. Use the following information:

{base_info}

Format requirements:
- Use ALL CAPS for section headers
- Use simple dashes (-) for bullet points
- Keep formatting clean and scannable
- Include sections: CONTACT INFO, EDUCATION, TECHNICAL SKILLS, EXPERIENCE, CERTIFICATIONS
- Make it concise but comprehensive
- Use action verbs and quantify achievements where possible

Generate a complete, professional resume."""

    elif template_style == "technical":
        return f"""Create a technical resume optimized for software engineering roles. Use the following information:

{base_info}

Format requirements:
- Emphasize technical skills and projects
- Use ALL CAPS for section headers
- Include sections: CONTACT INFO, TECHNICAL SKILLS, EXPERIENCE, EDUCATION, CERTIFICATIONS
- Highlight programming languages, frameworks, and tools
- Focus on technical achievements and impact
- Use metrics and numbers where possible

Generate a complete, technical resume."""

    elif template_style == "creative":
        return f"""Create a creative but professional resume with engaging language. Use the following information:

{base_info}

Format requirements:
- Use dynamic action words
- Show personality while maintaining professionalism
- Use ALL CAPS for section headers
- Include sections: CONTACT INFO, SUMMARY, EXPERIENCE, SKILLS, EDUCATION, CERTIFICATIONS
- Include a brief professional summary
- Highlight unique achievements and value propositions

Generate a complete, creative resume."""

    else:  # academic
        return f"""Create an academic-style resume with detailed education focus. Use the following information:

{base_info}

Format requirements:
- Emphasize education, research, and academic achievements
- Use ALL CAPS for section headers
- Include sections: CONTACT INFO, EDUCATION, RESEARCH EXPERIENCE, SKILLS, CERTIFICATIONS
- Include GPA if mentioned in education
- Focus on academic contributions and scholarly work

Generate a complete, academic resume."""

# Enhanced PDF export with better Unicode handling
def export_as_pdf(text: str, user_data: Dict, font_family: str = "Arial", font_size: int = 11) -> str:
    """Export resume to PDF with enhanced formatting and Unicode support"""
    
    class EnhancedPDF(FPDF):
        def header(self):
            # Name header
            self.set_font('Arial', 'B', 20)
            clean_name = clean_text_for_pdf(user_data['name'].upper())
            self.cell(0, 15, clean_name, 0, 1, 'C')
            
            # Contact info
            self.set_font('Arial', '', 11)
            contact_parts = []
            if user_data.get('phone'):
                contact_parts.append(clean_text_for_pdf(user_data['phone']))
            if user_data.get('email'):
                contact_parts.append(clean_text_for_pdf(user_data['email']))
            if user_data.get('location'):
                contact_parts.append(clean_text_for_pdf(user_data['location']))
            
            contact_info = ' | '.join(contact_parts)
            self.cell(0, 8, contact_info, 0, 1, 'C')
            
            # Optional social links
            social_parts = []
            if user_data.get('linkedin'):
                social_parts.append(f"LinkedIn: {clean_text_for_pdf(user_data['linkedin'])}")
            if user_data.get('github'):
                social_parts.append(f"GitHub: {clean_text_for_pdf(user_data['github'])}")
            
            if social_parts:
                self.set_font('Arial', '', 10)
                social_info = ' | '.join(social_parts)
                self.cell(0, 6, social_info, 0, 1, 'C')
            
            self.ln(10)
        
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Generated on {datetime.now().strftime("%B %d, %Y")}', 0, 0, 'C')
        
        def section_header(self, title: str):
            self.ln(5)
            self.set_font('Arial', 'B', 13)
            clean_title = clean_text_for_pdf(title)
            self.cell(0, 8, clean_title, 0, 1, 'L')
            
            # Add underline
            self.set_line_width(0.5)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.ln(5)
        
        def safe_cell(self, w, h, txt, border=0, ln=0, align='L'):
            """Cell method with text cleaning"""
            clean_txt = clean_text_for_pdf(str(txt))
            self.cell(w, h, clean_txt, border, ln, align)
        
        def safe_multi_cell(self, w, h, txt, border=0, align='L'):
            """Multi-cell method with text cleaning"""
            clean_txt = clean_text_for_pdf(str(txt))
            self.multi_cell(w, h, clean_txt, border, align)
    
    pdf = EnhancedPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)
    
    # Clean the entire text first
    text = clean_text_for_pdf(text)
    
    # Process content, skipping header info
    lines = text.split('\n')
    skip_header = True
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            pdf.ln(3)
            continue
        
        # Skip header information
        if skip_header:
            clean_name = clean_text_for_pdf(user_data['name'].upper())
            clean_phone = clean_text_for_pdf(user_data['phone'])
            clean_email = clean_text_for_pdf(user_data['email'])
            
            if any(info in line for info in [clean_name, clean_phone, clean_email]):
                continue
            if line.isupper() and len(line) < 50:
                skip_header = False
            else:
                continue
        
        # Already cleaned line
        line_clean = line
        
        # Format based on content
        if line.isupper() and len(line) < 50 and not line.startswith('-') and not line.startswith('*'):
            # Section header
            pdf.section_header(line_clean)
            current_section = line_clean
        elif line.startswith(('- ', '* ', '+ ')):
            # Bullet points - use asterisk for consistency
            pdf.set_font('Arial', '', font_size)
            pdf.safe_cell(8, 6, '* ', 0, 0, 'L')
            content = line_clean[2:].strip() if len(line_clean) > 2 else line_clean
            pdf.safe_multi_cell(0, 6, content)
            pdf.ln(1)
        else:
            # Regular content
            pdf.set_font('Arial', '', font_size)
            pdf.safe_multi_cell(0, 6, line_clean)
            pdf.ln(1)
    
    # Generate filename with safe characters
    safe_name = clean_text_for_pdf(user_data['name']).replace(' ', '_')
    safe_name = ''.join(c for c in safe_name if c.isalnum() or c in '-_')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"resume_{safe_name}_{timestamp}.pdf"
    
    try:
        pdf.output(filename)
        return filename
    except Exception as e:
        # If PDF generation fails, try with a simple filename
        simple_filename = f"resume_{timestamp}.pdf"
        pdf.output(simple_filename)
        return simple_filename

def clean_text_for_pdf(text: str) -> str:
    """Clean text for PDF compatibility - handles all Unicode characters"""
    # First, replace common Unicode characters with ASCII equivalents
    replacements = {
        '\u2022': '* ',      # bullet point -> asterisk
        '\u2013': '-',       # en dash
        '\u2014': '-',       # em dash
        '\u2019': "'",       # right single quotation mark
        '\u201c': '"',       # left double quotation mark
        '\u201d': '"',       # right double quotation mark
        '\u2026': '...',     # ellipsis
        '\u00a0': ' ',       # non-breaking space
        '\u2212': '-',       # minus sign
        '\u00b7': '* ',      # middle dot
        '\u25cf': '* ',      # black circle
        '\u25cb': '* ',      # white circle
        '\u25a0': '* ',      # black square
        '\u25a1': '* ',      # white square
        '\u2192': '->',      # right arrow
        '\u2190': '<-',      # left arrow
        '\u00ae': '(R)',     # registered trademark
        '\u00a9': '(C)',     # copyright
        '\u2122': '(TM)',    # trademark
        '─': '-',            # box drawing character
        '│': '|',            # box drawing character
        '•': '* ',           # bullet (if already present)
        '★': '*',            # star
        '☆': '*',            # star
        '●': '* ',           # black circle
        '○': '* ',           # white circle
    }
    
    # Apply replacements
    for unicode_char, replacement in replacements.items():
        text = text.replace(unicode_char, replacement)
    
    # Remove any remaining non-ASCII characters and replace with safe alternatives
    safe_text = ""
    for char in text:
        if ord(char) < 128:  # ASCII character
            safe_text += char
        elif char.isalpha():  # Non-ASCII letter
            # Try to find ASCII equivalent or skip
            if ord(char) < 256:
                safe_text += char
            else:
                safe_text += '?'  # Replace with question mark
        elif char.isdigit():  # Non-ASCII digit
            safe_text += char if ord(char) < 256 else '?'
        elif char.isspace():  # Non-ASCII whitespace
            safe_text += ' '
        else:
            # Other non-ASCII characters - try to keep if in latin-1 range
            if ord(char) < 256:
                safe_text += char
            else:
                safe_text += ''  # Remove completely
    
    return safe_text

# Main Streamlit App
def main():
    st.set_page_config(
        page_title="AI Resume Generator Pro", 
        page_icon="🚀", 
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Load styling
    load_css()
    
    # Header
    st.title("🚀 AI Resume Generator Pro")
    st.markdown("Generate professional, ATS-friendly resumes using advanced AI models")
    
    # Check for secrets
    try:
        api_key = st.secrets["ibm"]["api_key"]
        project_id = st.secrets["ibm"]["project_id"]
    except KeyError as e:
        st.error(f"❌ Missing secret configuration: {e}")
        st.info("Please configure your IBM Watsonx credentials in Streamlit secrets.")
        st.stop()
    
    config = get_config()
    
    # Configuration Section
    st.subheader("⚙️ Configuration")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        selected_model = st.selectbox(
            "🤖 AI Model",
            options=list(config["AVAILABLE_MODELS"].keys()),
            index=0,
            help="Choose the AI model for resume generation"
        )
    
    with col2:
        template_style = st.selectbox(
            "📋 Template Style",
            options=list(config["RESUME_TEMPLATES"].keys()),
            index=0,
            help="Choose the resume template style"
        )
    
    with col3:
        font_family = st.selectbox(
            "🔤 PDF Font",
            options=list(config["AVAILABLE_FONTS"].keys()),
            index=0,
            help="Choose the font for PDF export"
        )
    
    with col4:
        font_size = st.slider(
            "📏 Font Size",
            min_value=9,
            max_value=14,
            value=11,
            help="Adjust the font size for PDF export"
        )
    
    # Resume Form
    st.subheader("📝 Enter Your Information")
    
    with st.form("resume_form", clear_on_submit=False):
        # Personal Information
        st.markdown('<div class="section-header">👤 Personal Information</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input(
                "Full Name *",
                placeholder="John Doe",
                help="Enter your full name as it should appear on the resume"
            )
            
            phone = st.text_input(
                "Phone Number *",
                placeholder="+1 (555) 123-4567",
                help="Enter a valid phone number"
            )
            
            email = st.text_input(
                "Email Address *",
                placeholder="john@example.com",
                help="Enter a professional email address"
            )
        
        with col2:
            role = st.text_input(
                "Target Role *",
                placeholder="Software Engineer",
                help="Enter the job title you're targeting"
            )
            
            location = st.text_input(
                "Location",
                placeholder="City, State",
                help="Enter your city and state/country"
            )
            
            col2a, col2b = st.columns(2)
            with col2a:
                linkedin = st.text_input(
                    "LinkedIn",
                    placeholder="linkedin.com/in/johndoe",
                    help="Enter your LinkedIn profile URL"
                )
            with col2b:
                github = st.text_input(
                    "GitHub",
                    placeholder="github.com/johndoe",
                    help="Enter your GitHub profile URL"
                )
        
        # Professional Information
        st.markdown('<div class="section-header">💼 Professional Details</div>', unsafe_allow_html=True)
        
        skills = st.text_area(
            "Technical Skills *",
            placeholder="Python, JavaScript, React, Node.js, AWS, Docker, SQL, Git",
            height=100,
            help="List your technical skills separated by commas"
        )
        
        experience = st.text_area(
            "Work Experience *",
            placeholder="Software Developer at ABC Corp (2020-2023)\n- Developed web applications using React and Node.js\n- Improved system performance by 30% through optimization\n- Led a team of 3 developers on key projects",
            height=150,
            help="Describe your work experience with bullet points using dashes (-)"
        )
        
        # Education & Certifications
        st.markdown('<div class="section-header">🎓 Education & Certifications</div>', unsafe_allow_html=True)
        
        col3, col4 = st.columns(2)
        
        with col3:
            education = st.text_area(
                "Education *",
                placeholder="Bachelor of Science in Computer Science\nUniversity of Technology, 2020\nGPA: 3.8/4.0",
                height=100,
                help="Enter your educational background"
            )
        
        with col4:
            certifications = st.text_area(
                "Certifications",
                placeholder="AWS Certified Developer\nGoogle Cloud Professional\nPMP Certification",
                height=100,
                help="List any relevant certifications"
            )
        
        # Submit button
        st.markdown("---")
        st.markdown('<div class="help-text">* Required fields</div>', unsafe_allow_html=True)
        
        col_submit1, col_submit2, col_submit3 = st.columns([1, 2, 1])
        with col_submit2:
            submitted = st.form_submit_button(
                "🚀 Generate Resume",
                use_container_width=True,
                type="primary"
            )
    
    # Process form submission
    if submitted:
        # Collect user data
        user_data = {
            'name': name,
            'role': role,
            'phone': phone,
            'email': email,
            'location': location,
            'linkedin': linkedin,
            'github': github,
            'skills': skills,
            'experience': experience,
            'education': education,
            'certifications': certifications
        }
        
        try:
            # Generate resume
            with st.spinner(f"🤖 Generating resume with {selected_model}..."):
                model_id = config["AVAILABLE_MODELS"][selected_model]
                template_id = config["RESUME_TEMPLATES"][template_style]
                
                generated_text = generate_resume(user_data, model_id, template_id)
            
            st.success("✅ Resume generated successfully!")
            
            # Display resume
            st.subheader("📄 Your Resume")
            
            # Create a styled container for the resume
            st.markdown('<div class="resume-preview">', unsafe_allow_html=True)
            st.code(generated_text, language="text")
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Download section
            st.subheader("📥 Download Options")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # PDF Download
                with st.spinner("📄 Creating PDF..."):
                    font_name = config["AVAILABLE_FONTS"][font_family]
                    pdf_file = export_as_pdf(generated_text, user_data, font_name, font_size)
                
                with open(pdf_file, "rb") as f:
                    st.download_button(
                        "📥 Download PDF",
                        f,
                        file_name=f"{name.replace(' ', '_') if name else 'resume'}_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
            
            with col2:
                # Text Download
                st.download_button(
                    "📝 Download Text",
                    generated_text,
                    file_name=f"{name.replace(' ', '_') if name else 'resume'}_{datetime.now().strftime('%Y%m%d')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            
            with col3:
                # JSON Download (for backup/editing)
                resume_data = {
                    'user_data': user_data,
                    'generated_text': generated_text,
                    'settings': {
                        'model': selected_model,
                        'template': template_style,
                        'font': font_family,
                        'font_size': font_size
                    },
                    'timestamp': datetime.now().isoformat()
                }
                
                st.download_button(
                    "💾 Download Data",
                    json.dumps(resume_data, indent=2),
                    file_name=f"{name.replace(' ', '_') if name else 'resume'}_data_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json",
                    use_container_width=True
                )
            
            # Settings info
            st.info(f"💡 Generated with: {selected_model} | {template_style} template | {font_family} {font_size}pt")
            
        except ResumeGeneratorError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"❌ Unexpected error: {str(e)}")
            st.info("Please try again or contact support if the issue persists.")
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align: center; color: #888; margin-top: 20px;">
            <p><em>Built with ❤️ using Streamlit and IBM Watsonx AI</em></p>
            <p><small>Pro tip: Use action verbs and quantify your achievements for better results!</small></p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()