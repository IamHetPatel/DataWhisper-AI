import os
import re
import json

class SemanticMapper:
    """
    Translates human-readable engineering terms into ZwickRoell UUIDs.
    """
    def __init__(self, data_schema_dir="app/data_schema"):
        self.term_to_uuid = {}
        self._load_test_results(os.path.join(data_schema_dir, 'testResultTypes.ts'))
        self._load_channel_params(os.path.join(data_schema_dir, 'channelParameterMap.ts'))
        self._load_test_parameters(os.path.join(data_schema_dir, 'TestParameterMap.json'))

    def _load_test_parameters(self, filepath):
        if not os.path.exists(filepath):
            return
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                term = item.get("en", "").lower().strip()
                uuid_str = item.get("_id", "").strip()
                if term and uuid_str:
                    # Some UUIDs in this file have {} around them, we can strip them
                    uuid_str = uuid_str.strip('{}')
                    self.term_to_uuid[term] = uuid_str

    def _load_test_results(self, filepath):
        if not os.path.exists(filepath):
            return
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Matches: name: "...", ... uuid: "..."
        pattern = re.compile(r'name:\s*"([^"]+)",[\s\S]*?uuid:\s*"([^"]+)"')
        for match in pattern.finditer(content):
            term = match.group(1).lower().strip()
            uuid_str = match.group(2).strip()
            self.term_to_uuid[term] = uuid_str

    def _load_channel_params(self, filepath):
        if not os.path.exists(filepath):
            return
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Matches: en: `...`, _id: `{...}`
        pattern = re.compile(r'en:\s*`([^`]+)`,\s*_id:\s*`{?([^}`]+)}?`')
        for match in pattern.finditer(content):
            term = match.group(1).lower().strip()
            uuid_str = match.group(2).strip()
            self.term_to_uuid[term] = uuid_str

    def get_uuid_for_term(self, natural_language_term: str) -> str:
        """
        Example: 'maximum force' -> '9DB9C049-9B04-4bf1-BD29-A160E86DE691'
        """
        # Clean input for fuzzy matching
        term_clean = natural_language_term.lower().strip()
        
        # Direct match
        if term_clean in self.term_to_uuid:
            return self.term_to_uuid[term_clean]
            
        # Partial match fallback (simple heuristic)
        for key, value in self.term_to_uuid.items():
            if term_clean in key or key in term_clean:
                return value
                
        return None
    
    def get_all_mappings(self):
        return self.term_to_uuid
