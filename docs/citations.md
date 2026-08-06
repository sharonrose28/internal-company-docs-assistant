# Citation API design

Successful `POST /chat` responses include readable source attribution in the answer and a separate machine-readable citation array:

```json
{
  "session_id": "57287037-e0ba-4467-851f-e76d8d89762b",
  "answer": "According to Employee Handbook.pdf (Page 18, Benefits), employees receive annual wellness benefits.",
  "status": "answered",
  "confidence": 0.91,
  "citations": [
    {
      "source_id": "S1",
      "document_id": "6fd77598-6d97-4d90-9a83-a77daa17fd48",
      "document_name": "Employee Handbook.pdf",
      "page_number": 18,
      "section_heading": "Benefits",
      "similarity_score": 0.87,
      "quote": "Eligible employees receive annual wellness benefits..."
    }
  ]
}
```

The LLM emits only stable source markers such as `S1`. The server validates those markers against the authorized context and replaces them with the document name, page, and section. Unknown or mismatched markers cause a refusal. This prevents model-generated citation metadata.

`page_number` and `section_heading` are nullable because Markdown and Slack sources may not have PDF pages or headings. Markdown citations use their final heading-path element; Slack citations use the channel name. For hybrid search, `similarity_score` is Qdrant's fused relevance score, not a raw cosine similarity, so clients should display it as relevance rather than a percentage.
