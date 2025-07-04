import streamlit as st
import openai
from fpdf import FPDF

# Set your OpenAI API key
openai.api_key = "YOUR_API_KEY"

def generate_resume(name, role, skills, experience):
    prompt = f"""
    Create a professional resume summary for:
    Name: {name}
    Role: {role}
    Skills: {skills}
    Experience: {experience}
    Format it in a structured resume style.
    """

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that writes resumes."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

def export_as_pdf(resume_text, filename="resume.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)

    for line in resume_text.split('\n'):
        pdf.multi_cell(0, 10, line)
    
    pdf.output(filename)

# Streamlit UI
st.title("🧠 AI Resume Generator")
st.markdown("Fill in the details below to generate your resume")

name = st.text_input("Your Name")
role = st.text_input("Job Role")
skills = st.text_area("Skills (comma separated)")
experience = st.text_area("Experience")

if st.button("Generate Resume"):
    if name and role and skills and experience:
        resume = generate_resume(name, role, skills, experience)
        st.subheader("Generated Resume")
        st.text_area("", resume, height=400)

        export_as_pdf(resume)
        with open("resume.pdf", "rb") as file:
            st.download_button(
                label="Download PDF",
                data=file,
                file_name="resume.pdf",
                mime="application/pdf"
            )
    else:
        st.error("Please fill all fields.")
