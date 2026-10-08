from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    confirm_password: str

class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sku: str
    name: str
    category: str
    current_stock: float
    lead_time_days: int
    safety_stock: float

class ForecastRequest(BaseModel):
    product_id: int
    horizon: int = 30
    models: List[str] = ["ARIMA", "LSTM"]

class ScenarioRequest(BaseModel):
    product_id: int
    horizon: int = 30
    demand_change_percent: float = 0
    stock_change_percent: float = 0
    safety_stock_change_percent: float = 0
    lead_time_days: Optional[int] = None

class CopilotMessage(BaseModel):
    role: str
    content: str

class CopilotRequest(BaseModel):
    question: str
    history: List[CopilotMessage] = Field(default_factory=list)
