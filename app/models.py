from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class TagSchema(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class TagCreate(BaseModel):
    name: str


class DocumentResponse(BaseModel):
    id: str
    filename: str
    storage_path: str
    mime_type: str
    file_size: int
    created_at: str
    document_date: Optional[str] = None
    document_type: Optional[str] = None
    organization: Optional[str] = None
    amount: Optional[float] = None
    person_name: Optional[str] = None
    ocr_status: str
    ocr_error: Optional[str] = None
    content: Optional[str] = None
    tags: List[str] = []
    snippet: Optional[str] = None
    raw_metadata: Optional[str] = None
    is_duplicate: bool = False

    model_config = ConfigDict(from_attributes=True)


class DocumentUpdate(BaseModel):
    filename: Optional[str] = None
    document_date: Optional[str] = None
    document_type: Optional[str] = None
    organization: Optional[str] = None
    amount: Optional[float] = None
    person_name: Optional[str] = None


class SearchResult(BaseModel):
    query: str
    total: int
    results: List[DocumentResponse]


class DocumentListResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    documents: List[DocumentResponse]
