system_prompt = f"Help me to summary below receipt image into json type.\n "
f"Must include some keys such as \"price\", \"quantity\", \"item(s)\", \"total\", \"date\", \"currency\", \"notes\", \"unit\", \"company_name\" if they are provided"
f"If some of items missing or inaccurate or not sure, please ignore the details\n"
f"Just return the json representation of this document as if you were reading it naturally.\n"
f"Do not hallucinate.\n"
f"Return Json only.\n"

__all__ = ["system_prompt"]