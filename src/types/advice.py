from pydantic import BaseModel, Field


class Citation(BaseModel):
    source: str
    excerpt: str


class AdviceRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


class AdviceResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
