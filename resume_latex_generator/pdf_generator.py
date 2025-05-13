def generate_pdf(resume_data, output_path, timeout=30):
    """Generate a PDF from resume data using LaTeX."""
    # Create the LaTeX content from the resume data
    try:
        from resume_latex_generator.templates.classic_template import generate_latex_document
        latex_content, section_log = generate_latex_document(resume_data)
        
        for log_entry in section_log:
            print(f"LaTeX Generation: {log_entry}")
            
        # Create a temporary directory for LaTeX compilation
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save the LaTeX content to a file
            tex_file_path = os.path.join(temp_dir, "resume.tex")
            with open(tex_file_path, 'w', encoding='utf-8') as tex_file:
                tex_file.write(latex_content)
            
            # Compile the LaTeX file to generate the PDF
            pdf_file_path = compile_latex(tex_file_path, output_path, timeout)
            
            return pdf_file_path
    except Exception as e:
        print(f"Error in generate_pdf: {str(e)}")
        traceback.print_exc()
        raise PDFGenerationError(f"Failed to generate PDF: {str(e)}") 