from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
import json
import uuid
import os
from datetime import datetime, date

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Application model with validation
class ApplicationIn(BaseModel):
    name: str
    dateOfBirth: str
    address: str
    driverLicense: str
    employmentStatus: str
    income: float
    carValue: float
    depositAmount: float
    loanAmount: float

    @validator('dateOfBirth')
    def validate_age(cls, dob):
        try:
            birthdate = datetime.strptime(dob, "%Y-%m-%d").date()
            today = date.today()
            age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
            
            if age < 18:
                raise ValueError("Applicant must be at least 18 years old")
            return dob
        except ValueError as e:
            raise ValueError(f"Invalid date format or {str(e)}")
    
    # @validator('income')
    # def validate_income(cls, v):
    #     if v <= 0:
    #         raise ValueError("Income must be greater than zero")
    #     return v
    
    @validator('loanAmount')
    def validate_loan_amount(cls, v, values):
        if 'carValue' in values and 'depositAmount' in values:
            expected = max(0, values['carValue'] - values['depositAmount'])
            if abs(v - expected) > 0.01:  # Allow small floating point differences
                raise ValueError(f"Loan amount must equal car value minus deposit")
        return v

# Application output model
class ApplicationOut(ApplicationIn):
    id: str
    status: str
    decisionCode: Optional[str] = None
    createdAt: str
    
class ApplicationSummary(BaseModel):
    id: str
    name: str
    employmentStatus: str
    income: float
    loanAmount: float
    decisionCode: Optional[str] = None
    status: str
    createdAt: str

# Decision result model
class DecisionResult(BaseModel):
    status: str
    decisionCode: Optional[str] = None
    message: str

APPLICATIONS_FILE = "applications.json"

# Helper functions
def load_applications() -> List[Dict[str, Any]]:
    try:
        if os.path.exists(APPLICATIONS_FILE):
            with open(APPLICATIONS_FILE, "r") as f:
                return json.load(f)
        return []
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading applications: {e}")
        return []

def save_applications(applications: List[Dict[str, Any]]) -> None:
    try:
        with open(APPLICATIONS_FILE, "w") as f:
            json.dump(applications, f, indent=4)
    except Exception as e:
        print(f"Error saving applications: {e}")
        # In a real app, you might want to raise an exception here
        # but for now we'll just log the error to help with debugging

def calculate_lvr(loan_amount: float, income: float) -> float:
    """Calculate Loan to Value Ratio"""
    return (loan_amount / income) * 100 if income > 0 else float('inf')

def process_application(application: ApplicationIn) -> DecisionResult:
    """Process loan application according to business rules"""
    lvr = calculate_lvr(application.loanAmount, application.income)

    if application.employmentStatus == "unemployed":
        return DecisionResult(
            status="rejected",  
            decisionCode="D_017",
            message="Application declined due to unemployment status."
        )
    elif lvr > 150:
        return DecisionResult(
            status="rejected",  
            decisionCode="R_040",
            message="Application declined due to high LVR ratio."
        )
    else:
        return DecisionResult(
            status="approved",
            message="Application has been approved!"
        )

@app.post("/create/applications", response_model=ApplicationOut, status_code=201)
def create_application(app_in: ApplicationIn):  
    try:
        # Process application
        result = process_application(app_in)

        # Create new application record
        new_app = app_in.dict()
        new_app["id"] = str(uuid.uuid4())
        new_app["status"] = result.status
        new_app["decisionCode"] = result.decisionCode
        new_app["createdAt"] = datetime.utcnow().isoformat()

        # Load existing apps and append new
        apps = load_applications()
        apps.append(new_app)
        save_applications(apps)

        return new_app
    except Exception as e:
       
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process application: {str(e)}"
        )

@app.get("/applicationList", response_model=List[ApplicationSummary])
def get_applications(): 
    """Get all applications with summary information"""
    try:
        apps = load_applications()
        summary_list = []
        
        for app_item in apps:
            summary_list.append({
                "id": app_item.get("id", ""),
                "name": app_item.get("name", ""),
                "employmentStatus": app_item.get("employmentStatus", ""),
                "income": app_item.get("income", 0),
                "loanAmount": app_item.get("loanAmount", 0),
                "decisionCode": app_item.get("decisionCode"),
                "status": app_item.get("status", ""),
                "createdAt": app_item.get("createdAt", datetime.utcnow().isoformat()),
            })
        
        return summary_list
    except Exception as e:
        print(f"Error retrieving applications: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to retrieve applications: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)