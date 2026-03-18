import sys
import os

# Ensure the app module can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from services.semantic_mapper import SemanticMapper

def main():
    mapper = SemanticMapper(data_schema_dir="app/data_schema")
    
    # Test translations
    tests = ["maximum force", "tensile strength", "time", "test duration", "temperature"]
    
    print("Semantic Dictionary Loaded.")
    print(f"Total entries parsed: {len(mapper.get_all_mappings())}\n")
    
    for t in tests:
        uuid = mapper.get_uuid_for_term(t)
        print(f"Term: '{t}' -> UUID: {uuid}")

if __name__ == "__main__":
    main()
