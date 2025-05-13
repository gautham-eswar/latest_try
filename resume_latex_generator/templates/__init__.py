import os
import glob
import importlib
from typing import List, Any

TEMPLATES_DIR_NAME = "templates" # Relative to the main script or where this __init__ is
TEMPLATE_FILE_SUFFIX = "_template.py"

def get_available_templates() -> List[str]:
    """
    Discovers available template modules in the templates directory.
    Templates are expected to be Python files ending with '_template.py'.
    Returns a list of template names (without the '_template.py' suffix).
    """
    # Construct the path to the templates directory relative to this __init__.py file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    search_pattern = os.path.join(current_dir, f"*{TEMPLATE_FILE_SUFFIX}")
    
    template_files = glob.glob(search_pattern)
    
    available_templates = []
    for t_file in template_files:
        base_name = os.path.basename(t_file)
        if base_name == "__init__.py":
            continue
        template_name = base_name.replace(TEMPLATE_FILE_SUFFIX, "")
        available_templates.append(template_name)
        
    return sorted(available_templates)

def load_template(template_name: str) -> Any:
    """
    Loads a template module dynamically.
    Args:
        template_name: The name of the template (e.g., 'classic').
    Returns:
        The loaded template module.
    Raises:
        ImportError: If the template module cannot be found or loaded.
    """
    module_name = f".{template_name}{TEMPLATE_FILE_SUFFIX[:-3]}" # Relative import from current package
    try:
        # The package is the current package 'resume_latex_generator.templates'
        template_module = importlib.import_module(module_name, package=__name__)
        
        # Check if the required function exists
        if not hasattr(template_module, 'generate_latex_content'):
            raise ImportError(
                f"Template '{template_name}' loaded, but missing required function "
                f"'generate_latex_content(data, page_height)'."
            )
        return template_module
    except ImportError as e:
        raise ImportError(f"Could not load template '{template_name}'. Error: {e}")

# Example usage (for testing within this file, not typical)
if __name__ == '__main__':
    print("Discovering templates...")
    # To test this, you'd need a dummy templates/test_template.py file
    # and run this __init__.py directly, which is not its primary use.
    # For now, assume the structure and paths are correct for when resume_generator.py calls these.
    
    # Create a dummy template directory and file for testing get_available_templates
    test_templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".") # current dir
    if not os.path.exists(os.path.join(test_templates_dir, "dummy_template.py")):
         with open(os.path.join(test_templates_dir, "dummy_template.py"), "w") as f:
             f.write("# Dummy template for testing __init__.py\n")
             f.write("def generate_latex_content(data, page_height=None): return ''\n")


    # Re-run discovery for test
    # Note: The test setup above is a bit hacky for __init__.py.
    # Proper testing would involve a test suite.
    # For now, this is just illustrative.
    
    # The template discovery will look for *_template.py
    # Let's make a compliant dummy file for testing
    compliant_dummy_path = os.path.join(test_templates_dir, "compliant_test_template.py")
    if not os.path.exists(compliant_dummy_path):
        with open(compliant_dummy_path, "w") as f:
            f.write("# Compliant dummy template\n")
            f.write("def generate_latex_content(data, page_height=None): return 'dummy latex'\n")

    print(f"Available templates: {get_available_templates()}")

    if "compliant_test" in get_available_templates():
        try:
            print("\nLoading 'compliant_test' template...")
            loaded_mod = load_template("compliant_test")
            print(f"Successfully loaded: {loaded_mod}")
            if hasattr(loaded_mod, 'generate_latex_content'):
                print("'generate_latex_content' function found.")
                print(f"Test call: {loaded_mod.generate_latex_content({}, 12.0)}")
            else:
                print("'generate_latex_content' function NOT found.")
        except ImportError as e:
            print(f"Error loading template: {e}")
    else:
        print("\n'compliant_test' template not found, skipping load test.")

    # Clean up dummy files if they were created by this test block
    if os.path.exists(os.path.join(test_templates_dir, "dummy_template.py")):
        os.remove(os.path.join(test_templates_dir, "dummy_template.py"))
    if os.path.exists(compliant_dummy_path):
        os.remove(compliant_dummy_path) 