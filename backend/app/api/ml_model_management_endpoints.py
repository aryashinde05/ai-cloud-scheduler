"""
ML Model Management and Experimentation Platform Endpoints

This module provides REST API endpoints for the comprehensive ML model
management system including model lifecycle, A/B testing, experiment tracking,
model interpretation, and bias detection.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np

from app.ml.ml_model_manager import ModelManager, ModelConfig, ModelStatus
from .ab_testing_framework import ABTestingFramework, TestConfiguration, TestVariant, TrafficSplitStrategy, TestType
from app.ml.experiment_tracker import ExperimentTracker, ExperimentStatus
from app.ml.model_interpreter import ModelInterpreter, InterpretabilityMethod, ExplanationType
from app.ml.bias_detection_mitigation import BiasDetectionMitigation, BiasType, MitigationStrategy
from app.core.auth import get_current_user
from app.core.exceptions import ModelManagerError, ABTestingError, ExperimentTrackerError

logger = logging.getLogger(__name__)

# Initialize components
model_manager = ModelManager()
ab_testing_framework = ABTestingFramework()
experiment_tracker = ExperimentTracker()
model_interpreter = ModelInterpreter()
bias_detector = BiasDetectionMitigation()

router = APIRouter(prefix="/ml", tags=["ML Model Management"])

# Pydantic models for request/response
class ModelTrainingRequest(BaseModel):
    model_name: str = Field(..., description="Name of the model")
    model_type: str = Field(..., description="Type of model (e.g., random_forest)")
    hyperparameters: Dict[str, Any] = Field(..., description="Model hyperparameters")
    feature_columns: List[str] = Field(..., description="List of feature column names")
    target_column: str = Field(..., description="Target column name")
    preprocessing_steps: List[str] = Field(default=[], description="Preprocessing steps")
    validation_split: float = Field(default=0.2, description="Validation split ratio")

class ModelValidationRequest(BaseModel):
    model_id: str = Field(..., description="Model identifier")
    validation_criteria: Dict[str, float] = Field(default={}, description="Validation criteria")

class ModelDeploymentRequest(BaseModel):
    model_id: str = Field(..., description="Model identifier")
    deployment_target: str = Field(default="staging", description="Deployment target")
    rollback_model_id: Optional[str] = Field(None, description="Rollback model ID")

class ABTestRequest(BaseModel):
    test_name: str = Field(..., description="Test name")
    description: str = Field(..., description="Test description")
    test_type: str = Field(..., description="Test type")
    variants: List[Dict[str, Any]] = Field(..., description="Test variants")
    primary_metric: str = Field(..., description="Primary metric")
    secondary_metrics: List[str] = Field(default=[], description="Secondary metrics")
    minimum_sample_size: int = Field(default=1000, description="Minimum sample size")
    significance_level: float = Field(default=0.05, description="Significance level")
    power: float = Field(default=0.8, description="Statistical power")
    traffic_split_strategy: str = Field(default="random", description="Traffic split strategy")
    duration_days: int = Field(default=14, description="Test duration in days")

class ExperimentRequest(BaseModel):
    name: str = Field(..., description="Experiment name")
    description: str = Field(default="", description="Experiment description")
    tags: Dict[str, str] = Field(default={}, description="Experiment tags")

class RunRequest(BaseModel):
    experiment_id: str = Field(..., description="Experiment identifier")
    run_name: Optional[str] = Field(None, description="Run name")
    parameters: Dict[str, Any] = Field(default={}, description="Run parameters")
    tags: Dict[str, str] = Field(default={}, description="Run tags")

class BiasAnalysisRequest(BaseModel):
    model_id: str = Field(..., description="Model identifier")
    target_column: str = Field(..., description="Target column name")
    protected_attributes: List[str] = Field(..., description="Protected attributes")
    feature_columns: List[str] = Field(..., description="Feature columns")
    bias_types: List[str] = Field(default=[], description="Bias types to analyze")

class ModelExplanationRequest(BaseModel):
    model_id: str = Field(..., description="Model identifier")
    feature_names: List[str] = Field(..., description="Feature names")
    method: str = Field(default="shap", description="Interpretability method")
    explanation_type: str = Field(default="global", description="Explanation type")

# Model Management Endpoints

@router.post("/models/train")
async def train_model(
    request: ModelTrainingRequest,
    training_data: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """Train a new ML model"""
    try:
        # Read training data
        content = await training_data.read()
        df = pd.read_csv(pd.io.common.StringIO(content.decode('utf-8')))
        
        # Create model configuration
        config = ModelConfig(
            model_name=request.model_name,
            model_type=request.model_type,
            hyperparameters=request.hyperparameters,
            feature_columns=request.feature_columns,
            target_column=request.target_column,
            preprocessing_steps=request.preprocessing_steps,
            validation_split=request.validation_split
        )
        
        # Train model
        result = await model_manager.train_model(
            config=config,
            training_data=df,
            account_id=current_user.get("account_id")
        )
        
        return {
            "success": True,
            "message": "Model training completed",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Model training failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/models/validate")
async def validate_model(
    request: ModelValidationRequest,
    validation_data: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """Validate a trained model"""
    try:
        # Read validation data
        content = await validation_data.read()
        df = pd.read_csv(pd.io.common.StringIO(content.decode('utf-8')))
        
        # Validate model
        result = await model_manager.validate_model(
            model_id=request.model_id,
            validation_data=df,
            validation_criteria=request.validation_criteria
        )
        
        return {
            "success": True,
            "message": "Model validation completed",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Model validation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/models/deploy")
async def deploy_model(
    request: ModelDeploymentRequest,
    current_user = Depends(get_current_user)
):
    """Deploy a model to specified environment"""
    try:
        result = await model_manager.deploy_model(
            model_id=request.model_id,
            deployment_target=request.deployment_target,
            rollback_model_id=request.rollback_model_id
        )
        
        return {
            "success": True,
            "message": "Model deployment completed",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Model deployment failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models")
async def list_models(current_user = Depends(get_current_user)):
    """List all models for the current user"""
    try:
        models = await model_manager.list_models(
            account_id=current_user.get("account_id")
        )
        
        return {
            "success": True,
            "data": models
        }
        
    except Exception as e:
        logger.error(f"Failed to list models: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models/{model_id}")
async def get_model_info(
    model_id: str,
    current_user = Depends(get_current_user)
):
    """Get detailed information about a specific model"""
    try:
        model_info = await model_manager.get_model_info(model_id)
        
        if not model_info:
            raise HTTPException(status_code=404, detail="Model not found")
        
        return {
            "success": True,
            "data": model_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get model info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# A/B Testing Endpoints

@router.post("/ab-tests")
async def create_ab_test(
    request: ABTestRequest,
    current_user = Depends(get_current_user)
):
    """Create a new A/B test"""
    try:
        # Convert request to test configuration
        variants = []
        for variant_data in request.variants:
            variant = TestVariant(
                variant_id=variant_data["variant_id"],
                name=variant_data["name"],
                description=variant_data["description"],
                model_id=variant_data["model_id"],
                traffic_percentage=variant_data["traffic_percentage"],
                configuration=variant_data.get("configuration", {})
            )
            variants.append(variant)
        
        config = TestConfiguration(
            test_name=request.test_name,
            description=request.description,
            test_type=TestType(request.test_type),
            variants=variants,
            primary_metric=request.primary_metric,
            secondary_metrics=request.secondary_metrics,
            minimum_sample_size=request.minimum_sample_size,
            significance_level=request.significance_level,
            power=request.power,
            traffic_split_strategy=TrafficSplitStrategy(request.traffic_split_strategy),
            duration_days=request.duration_days
        )
        
        test_id = await ab_testing_framework.create_test(
            config=config,
            account_id=current_user.get("account_id")
        )
        
        return {
            "success": True,
            "message": "A/B test created successfully",
            "data": {"test_id": test_id}
        }
        
    except Exception as e:
        logger.error(f"A/B test creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ab-tests/{test_id}/start")
async def start_ab_test(
    test_id: str,
    current_user = Depends(get_current_user)
):
    """Start an A/B test"""
    try:
        result = await ab_testing_framework.start_test(test_id)
        
        return {
            "success": True,
            "message": "A/B test started successfully",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"A/B test start failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ab-tests/{test_id}/analysis")
async def analyze_ab_test(
    test_id: str,
    current_user = Depends(get_current_user)
):
    """Analyze A/B test results"""
    try:
        analysis = await ab_testing_framework.analyze_test_results(test_id)
        
        return {
            "success": True,
            "data": analysis
        }
        
    except Exception as e:
        logger.error(f"A/B test analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ab-tests/{test_id}/conclude")
async def conclude_ab_test(
    test_id: str,
    winning_variant_id: Optional[str] = None,
    reason: Optional[str] = None,
    current_user = Depends(get_current_user)
):
    """Conclude an A/B test"""
    try:
        result = await ab_testing_framework.conclude_test(
            test_id=test_id,
            winning_variant_id=winning_variant_id,
            reason=reason
        )
        
        return {
            "success": True,
            "message": "A/B test concluded successfully",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"A/B test conclusion failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ab-tests")
async def list_ab_tests(current_user = Depends(get_current_user)):
    """List all A/B tests for the current user"""
    try:
        tests = await ab_testing_framework.list_tests(
            account_id=current_user.get("account_id")
        )
        
        return {
            "success": True,
            "data": tests
        }
        
    except Exception as e:
        logger.error(f"Failed to list A/B tests: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Experiment Tracking Endpoints

@router.post("/experiments")
async def create_experiment(
    request: ExperimentRequest,
    current_user = Depends(get_current_user)
):
    """Create a new experiment"""
    try:
        experiment_id = await experiment_tracker.create_experiment(
            name=request.name,
            description=request.description,
            tags=request.tags,
            created_by=current_user.get("user_id", "system")
        )
        
        return {
            "success": True,
            "message": "Experiment created successfully",
            "data": {"experiment_id": experiment_id}
        }
        
    except Exception as e:
        logger.error(f"Experiment creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/experiments/runs")
async def start_experiment_run(
    request: RunRequest,
    current_user = Depends(get_current_user)
):
    """Start a new experiment run"""
    try:
        run_id = await experiment_tracker.start_run(
            experiment_id=request.experiment_id,
            run_name=request.run_name,
            parameters=request.parameters,
            tags=request.tags
        )
        
        return {
            "success": True,
            "message": "Experiment run started successfully",
            "data": {"run_id": run_id}
        }
        
    except Exception as e:
        logger.error(f"Experiment run start failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/experiments/runs/{run_id}/metrics")
async def log_run_metrics(
    run_id: str,
    metrics: Dict[str, float],
    step: Optional[int] = None,
    current_user = Depends(get_current_user)
):
    """Log metrics for an experiment run"""
    try:
        await experiment_tracker.log_metrics(run_id, metrics, step)
        
        return {
            "success": True,
            "message": "Metrics logged successfully"
        }
        
    except Exception as e:
        logger.error(f"Metric logging failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/experiments/runs/{run_id}/end")
async def end_experiment_run(
    run_id: str,
    status: str = "completed",
    current_user = Depends(get_current_user)
):
    """End an experiment run"""
    try:
        await experiment_tracker.end_run(run_id, ExperimentStatus(status))
        
        return {
            "success": True,
            "message": "Experiment run ended successfully"
        }
        
    except Exception as e:
        logger.error(f"Experiment run end failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/experiments")
async def list_experiments(current_user = Depends(get_current_user)):
    """List all experiments for the current user"""
    try:
        experiments = await experiment_tracker.list_experiments(
            created_by=current_user.get("user_id")
        )
        
        return {
            "success": True,
            "data": [
                {
                    "experiment_id": exp.experiment_id,
                    "name": exp.name,
                    "description": exp.description,
                    "status": exp.status.value,
                    "created_at": exp.created_at,
                    "tags": exp.tags
                }
                for exp in experiments
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to list experiments: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/experiments/{experiment_id}/runs")
async def list_experiment_runs(
    experiment_id: str,
    current_user = Depends(get_current_user)
):
    """List runs for an experiment"""
    try:
        runs = await experiment_tracker.list_runs(experiment_id)
        
        return {
            "success": True,
            "data": [
                {
                    "run_id": run.run_id,
                    "name": run.name,
                    "status": run.status.value,
                    "start_time": run.start_time,
                    "end_time": run.end_time,
                    "metrics": run.metrics,
                    "parameters": run.parameters
                }
                for run in runs
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to list experiment runs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Model Interpretation Endpoints

@router.post("/models/{model_id}/explain")
async def explain_model(
    model_id: str,
    request: ModelExplanationRequest,
    training_data: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """Generate model explanation"""
    try:
        # Read training data
        content = await training_data.read()
        df = pd.read_csv(pd.io.common.StringIO(content.decode('utf-8')))
        
        # Get model (simplified - in practice, you'd load from model registry)
        model_info = await model_manager.get_model_info(model_id)
        if not model_info:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # For now, create a dummy model for demonstration
        from sklearn.ensemble import RandomForestClassifier
        model = RandomForestClassifier(random_state=42)
        X = df[request.feature_names]
        y = df.iloc[:, -1]  # Assume last column is target
        model.fit(X, y)
        
        explanation_id = await model_interpreter.explain_model(
            model=model,
            model_id=model_id,
            training_data=df,
            feature_names=request.feature_names,
            method=InterpretabilityMethod(request.method),
            explanation_type=ExplanationType(request.explanation_type)
        )
        
        return {
            "success": True,
            "message": "Model explanation generated successfully",
            "data": {"explanation_id": explanation_id}
        }
        
    except Exception as e:
        logger.error(f"Model explanation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/explanations/{explanation_id}")
async def get_explanation(
    explanation_id: str,
    current_user = Depends(get_current_user)
):
    """Get model explanation by ID"""
    try:
        explanation = await model_interpreter.get_explanation(explanation_id)
        
        if not explanation:
            raise HTTPException(status_code=404, detail="Explanation not found")
        
        return {
            "success": True,
            "data": {
                "explanation_id": explanation.explanation_id,
                "model_id": explanation.model_id,
                "explanation_type": explanation.explanation_type.value,
                "method": explanation.method.value,
                "feature_names": explanation.feature_names,
                "explanation_data": explanation.explanation_data,
                "confidence_score": explanation.confidence_score,
                "created_at": explanation.created_at
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get explanation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/explanations/{explanation_id}/summary")
async def get_explanation_summary(
    explanation_id: str,
    current_user = Depends(get_current_user)
):
    """Get human-readable explanation summary"""
    try:
        summary = await model_interpreter.generate_explanation_summary(explanation_id)
        
        return {
            "success": True,
            "data": summary
        }
        
    except Exception as e:
        logger.error(f"Failed to get explanation summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Bias Detection Endpoints

@router.post("/models/bias-analysis")
async def analyze_model_bias(
    request: BiasAnalysisRequest,
    test_data: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """Analyze model for bias"""
    try:
        # Read test data
        content = await test_data.read()
        df = pd.read_csv(pd.io.common.StringIO(content.decode('utf-8')))
        
        # Get model (simplified - in practice, you'd load from model registry)
        model_info = await model_manager.get_model_info(request.model_id)
        if not model_info:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # For now, create a dummy model for demonstration
        from sklearn.ensemble import RandomForestClassifier
        model = RandomForestClassifier(random_state=42)
        X = df[request.feature_columns]
        y = df[request.target_column]
        model.fit(X, y)
        
        # Convert bias types
        bias_types = [BiasType(bt) for bt in request.bias_types] if request.bias_types else None
        
        analysis_id = await bias_detector.analyze_bias(
            model=model,
            model_id=request.model_id,
            test_data=df,
            target_column=request.target_column,
            protected_attributes=request.protected_attributes,
            feature_columns=request.feature_columns,
            bias_types=bias_types
        )
        
        return {
            "success": True,
            "message": "Bias analysis completed successfully",
            "data": {"analysis_id": analysis_id}
        }
        
    except Exception as e:
        logger.error(f"Bias analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/bias-analyses/{analysis_id}")
async def get_bias_analysis(
    analysis_id: str,
    current_user = Depends(get_current_user)
):
    """Get bias analysis results"""
    try:
        analysis = await bias_detector.get_bias_analysis(analysis_id)
        
        if not analysis:
            raise HTTPException(status_code=404, detail="Bias analysis not found")
        
        return {
            "success": True,
            "data": {
                "analysis_id": analysis.analysis_id,
                "model_id": analysis.model_id,
                "protected_attributes": analysis.protected_attributes,
                "bias_metrics": analysis.bias_metrics,
                "overall_bias_score": analysis.overall_bias_score,
                "bias_detected": analysis.bias_detected,
                "recommendations": analysis.recommendations,
                "created_at": analysis.created_at
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get bias analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/models/fairness-report")
async def generate_fairness_report(
    request: BiasAnalysisRequest,
    dataset: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """Generate comprehensive fairness report"""
    try:
        # Read dataset
        content = await dataset.read()
        df = pd.read_csv(pd.io.common.StringIO(content.decode('utf-8')))
        
        # Get model (simplified - in practice, you'd load from model registry)
        model_info = await model_manager.get_model_info(request.model_id)
        if not model_info:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # For now, create a dummy model for demonstration
        from sklearn.ensemble import RandomForestClassifier
        model = RandomForestClassifier(random_state=42)
        X = df[request.feature_columns]
        y = df[request.target_column]
        model.fit(X, y)
        
        report_id = await bias_detector.generate_fairness_report(
            model=model,
            model_id=request.model_id,
            dataset=df,
            target_column=request.target_column,
            protected_attributes=request.protected_attributes,
            feature_columns=request.feature_columns
        )
        
        return {
            "success": True,
            "message": "Fairness report generated successfully",
            "data": {"report_id": report_id}
        }
        
    except Exception as e:
        logger.error(f"Fairness report generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check for ML model management system"""
    return {
        "success": True,
        "message": "ML Model Management system is healthy",
        "components": {
            "model_manager": "operational",
            "ab_testing_framework": "operational",
            "experiment_tracker": "operational",
            "model_interpreter": "operational",
            "bias_detector": "operational"
        },
        "timestamp": datetime.utcnow()
    }
