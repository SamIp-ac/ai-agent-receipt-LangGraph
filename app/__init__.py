system_prompt = f"Help me to summary below receipt image into json type.\n "
f"Must include some keys such as \"price\", \"quantity\", \"item(s)\", \"total\", \"date\", \"currency\", \"notes\", \"unit\", \"company_name\" if they are provided"
f"If some of items missing or inaccurate or not sure, please ignore the details\n"
f"Just return the json representation of this document as if you were reading it naturally.\n"
f"Do not hallucinate.\n"

handwritten_prompt = f"Below is the image of one page of a document, as well as some raw textual content that was previously extracted for it. "
f"Just return the plain text representation of this document as if you were reading it naturally.\n"
f"Do not hallucinate.\n"

__all__ = ["system_prompt", "handwritten_prompt"]