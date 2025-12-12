from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal
from enum import Enum

# --- Shared Models ---

class WidgetType(str, Enum):
    BAR_CHART = "bar_chart"
    LINE_CHART = "line_chart"
    PIE_CHART = "pie_chart"
    TRANSACTION_LIST = "transaction_list"
    STAT_CARD = "stat_card"
    FORM = "form"
    NONE = "none"

class WidgetModel(BaseModel):
    type: WidgetType
    data: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        extra = "allow" # Allow extra fields in data for flexibility

class ResponseModel(BaseModel):
    text: str
    widget: WidgetModel

# --- Reasoning Engine State ---

class ReasoningState(BaseModel):
    messages: List[Dict[str, str]] = Field(default_factory=list) # Chat history
    user_query: str
    intent: Optional[Literal["SQL", "GRAPH", "CHAT", "VISION"]] = None
    tool_args: Optional[Any] = None
    context_data: Optional[Any] = None
    final_response: Optional[ResponseModel] = None

# --- Enrichment Agent State ---

class EnrichmentStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETE = "COMPLETE"
    NEEDS_USER = "NEEDS_USER"

class TransactionModel(BaseModel):
    txn_id: str
    merchant_name: str
    amount: float
    date: str
    current_category: Optional[str] = None
    
class EnrichmentState(BaseModel):
    transaction: TransactionModel
    similar_transactions: List[Dict] = Field(default_factory=list)
    rules_context: str = ""
    suggested_category: Optional[str] = None
    confidence: float = 0.0
    status: EnrichmentStatus = EnrichmentStatus.PENDING
    clarification_question: Optional[str] = None
    suggested_options: List[str] = Field(default_factory=list)

# --- Onboarding Agent State ---

class SpendingRule(BaseModel):
    merchant: str
    total_spend: float
    question: str
    options: List[str]

class OnboardingState(BaseModel):
    check_limit: int = 500
    transactions: List[Dict] = Field(default_factory=list)
    generated_questions: List[SpendingRule] = Field(default_factory=list)
