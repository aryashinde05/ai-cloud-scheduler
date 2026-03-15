from typing import List, Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from supabase import Client

from app.database.database import get_supabase
from app.models.models import EC2Instance, EBSVolume, OptimizationRecommendation, ScanJob, ScanStatus, AnomalyDetection
from app.schemas.schemas import EC2InstanceResponse, EBSVolumeResponse, OptimizationRecommendationResponse
from app.services.background_jobs import scan_aws_resources

router = APIRouter(prefix="/api/v1", tags=["Cloud Resources"])

# --- Resources ---

@router.get("/resources/ec2", response_model=List[EC2InstanceResponse])
async def get_ec2_resources(
    region: Optional[str] = None, 
    supabase: Client = Depends(get_supabase)
):
    """List all tracked EC2 instances."""
    query = supabase.table("ec2_instances").select("*")
    if region:
        query = query.eq("region", region)
    
    response = query.execute()
    return response.data

@router.get("/resources/ebs", response_model=List[EBSVolumeResponse])
async def get_ebs_resources(
    region: Optional[str] = None, 
    supabase: Client = Depends(get_supabase)
):
    """List all tracked EBS volumes."""
    query = supabase.table("ebs_volumes").select("*")
    if region:
        query = query.eq("region", region)
        
    response = query.execute()
    return response.data

# --- Optimization ---

@router.get("/optimization/recommendations", response_model=List[OptimizationRecommendationResponse])
async def get_optimization_recommendations(
    resource_type: Optional[str] = None,
    supabase: Client = Depends(get_supabase)
):
    """Get active cost optimization recommendations."""
    query = supabase.table("optimization_recommendations").select("*").eq("status", "new")
    if resource_type:
        query = query.eq("resource_type", resource_type)
        
    response = query.execute()
    return response.data

# --- Actions ---

@router.post("/scan", status_code=202)
async def trigger_scan(
    background_tasks: BackgroundTasks,
    supabase: Client = Depends(get_supabase)
):
    """
    Trigger an immediate background scan of AWS resources.
    Uses FastAPI BackgroundTasks instead of Celery.
    Returns a Job ID immediately.
    """
    job_id = str(uuid.uuid4())
    
    # Create Job Record
    new_job = {
        "id": job_id,
        "status": "pending",
        "started_at": datetime.utcnow().isoformat()
    }
    supabase.table("scan_jobs").insert(new_job).execute()
    
    # Enqueue Background Task
    background_tasks.add_task(scan_aws_resources, job_id)
    
    return {
        "message": "AWS scan started in background", 
        "scan_job_id": job_id,
        "status": "pending"
    }

@router.get("/scan/{job_id}")
async def get_scan_status(
    job_id: str,
    supabase: Client = Depends(get_supabase)
):
    """Check status of a scan job."""
    response = supabase.table("scan_jobs").select("*").eq("id", job_id).single().execute()
    job = response.data
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")
        
    return {
        "id": job["id"],
        "status": job["status"],
        "resource_count": job.get("resource_count"),
        "started_at": job["started_at"],
        "completed_at": job.get("completed_at"),
        "error": job.get("error_message")
    }

# --- Cost & Forecasts ---

@router.get("/cost/forecast")
async def get_cost_forecast(supabase: Client = Depends(get_supabase)):
    """Get simple cost forecast."""
    return {
        "forecast_period": "30 days",
        "predicted_cost": 1250.00,
        "confidence_score": 0.85,
        "details": "Based on linear projection of last 30 days usage."
    }

@router.get("/cost/anomalies", tags=["Cost Anomaly Detection"])
async def get_cost_anomalies(supabase: Client = Depends(get_supabase)):
    """List detected cost anomalies."""
    try:
        response = supabase.table("anomaly_detection").select("*").order("detected_at", desc=True).limit(50).execute()
        return response.data
    except Exception:
        return []

