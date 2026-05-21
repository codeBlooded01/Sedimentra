"""
AD-GSI v4.0 — DATABASE PERSISTENCE MODELS

SQLAlchemy models for storing ML features and sample audits.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, Float, Integer, DateTime, JSON, ForeignKey, Text, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid

Base = declarative_base()

class MLAnalysisJob(Base):
    """Track individual analysis jobs."""
    __tablename__ = 'ml_analysis_jobs'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=True)
    status = Column(String, default='PROCESSING')  # PROCESSING, COMPLETE, FAILED
    domain = Column(String, default='COASTAL')  # COASTAL, SOIL, FRESHWATER
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Summary stats
    sample_count = Column(Integer, default=0)
    asv_count = Column(Integer, default=0)
    avg_confidence = Column(Float, nullable=True)
    
    # Error tracking
    errors = Column(Text, nullable=True)  # JSON-serialized
    
    # Relationships
    features = relationship('MLFeature', back_populates='job')
    audits = relationship('SampleAudit', back_populates='job')

class SampleAudit(Base):
    """Per-sample sequence audit metrics."""
    __tablename__ = 'sample_audits'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey('ml_analysis_jobs.id'), nullable=False)
    sample_id = Column(String, nullable=False)
    
    # Sequence metrics
    total_reads = Column(Integer)
    median_bp = Column(Integer)
    std_dev = Column(Float)
    asv_count = Column(Integer)
    
    # Constraint validation
    median_valid = Column(Integer, default=1)  # 0=violated, 1=valid
    std_dev_valid = Column(Integer, default=1)
    reads_valid = Column(Integer, default=1)
    
    # Confidence & signal
    conf_score = Column(Float)
    noise_loss_pct = Column(Float)
    
    # Domain signature
    domain_signature = Column(Float, nullable=True)
    
    # Violations
    violations = Column(ARRAY(String), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    job = relationship('MLAnalysisJob', back_populates='audits')

class MLFeature(Base):
    """Functional features for ML pipeline."""
    __tablename__ = 'ml_features'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey('ml_analysis_jobs.id'), nullable=False)
    sample_id = Column(String, nullable=False)
    
    # Feature data
    function = Column(String, nullable=False)
    rel_abundance = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    
    # Contributors (ASV IDs)
    contributors = Column(ARRAY(String), nullable=False)
    
    # Biomarker classification
    is_coastal_marker = Column(Integer, default=0)
    is_soil_marker = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Composite index for fast sample lookups
    job = relationship('MLAnalysisJob', back_populates='features')
    
    def to_dict(self):
        """Convert to API response format."""
        return {
            'function': self.function,
            'rel_abundance': round(self.rel_abundance, 6),
            'confidence': round(self.confidence, 3),
            'contributors': self.contributors,
            'markers': {
                'coastal': bool(self.is_coastal_marker),
                'soil': bool(self.is_soil_marker),
            }
        }

class FAProTAXEntry(Base):
    """FAPROTAX database entries for functional mapping."""
    __tablename__ = 'faprotax_entries'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Taxonomy hierarchy
    kingdom = Column(String)
    phylum = Column(String)
    clazz = Column(String)
    order = Column(String)
    family = Column(String)
    genus = Column(String)
    species = Column(String)
    
    # Functional profile
    functions = Column(ARRAY(String), nullable=False)
    
    # Priority level (1=exact match, 5=fallback)
    priority = Column(Integer, default=3)
    
    # Domain association
    domains = Column(ARRAY(String), nullable=False)  # e.g., ['COASTAL', 'SOIL']
    
    confidence = Column(Float, default=1.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)

class DomainBiomarker(Base):
    """Domain-specific biomarker definitions."""
    __tablename__ = 'domain_biomarkers'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    domain = Column(String, nullable=False)  # COASTAL, SOIL, FRESHWATER
    
    # Taxonomy identifying the biomarker
    phylum = Column(String)
    order = Column(String)
    family = Column(String)
    genus = Column(String)
    
    # Biomarker properties
    name = Column(String, nullable=False)
    description = Column(Text)
    weight = Column(Float, default=1.0)  # Relative weight in domain signature
    
    is_primary = Column(Integer, default=1)  # 0=secondary, 1=primary
    
    created_at = Column(DateTime, default=datetime.utcnow)
