#!/usr/bin/env python3
"""
Migration Knowledge Base for LangChain Chatbot
Contains cloud migration best practices, cost data, and expert knowledge
"""

import os
from typing import List, Dict, Any
from langchain.vectorstores import Chroma
from langchain.embeddings import SentenceTransformerEmbeddings
from langchain.schema import Document
import logging

logger = logging.getLogger(__name__)

class MigrationKnowledgeBase:
    """Knowledge base for cloud migration expertise"""
    
    def __init__(self, persist_directory: str = "./migration_kb"):
        self.persist_directory = persist_directory
        self.embeddings = SentenceTransformerEmbeddings(
            model_name="all-MiniLM-L6-v2"
        )
        self.vector_store = None
        
    def setup_knowledge_base(self) -> Chroma:
        """Initialize or load the knowledge base"""
        
        # Check if knowledge base already exists
        if os.path.exists(self.persist_directory):
            logger.info("Loading existing knowledge base...")
            self.vector_store = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings
            )
        else:
            logger.info("Creating new knowledge base...")
            documents = self.create_migration_documents()
            self.vector_store = Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings,
                persist_directory=self.persist_directory
            )
            
        return self.vector_store
    
    def create_migration_documents(self) -> List[Document]:
        """Create comprehensive migration knowledge documents"""
        
        documents = []
        
        # AWS Migration Best Practices
        documents.extend(self._create_aws_documents())
        
        # GCP Migration Strategies
        documents.extend(self._create_gcp_documents())
        
        # Azure Migration Approaches
        documents.extend(self._create_azure_documents())
        
        # Startup-Specific Guidance
        documents.extend(self._create_startup_documents())
        
        # Cost Optimization
        documents.extend(self._create_cost_documents())
        
        # Security & Compliance
        documents.extend(self._create_security_documents())
        
        # Migration Planning
        documents.extend(self._create_planning_documents())
        
        logger.info(f"Created {len(documents)} knowledge documents")
        return documents
    
    def _create_aws_documents(self) -> List[Document]:
        """AWS-specific migration knowledge"""
        
        return [
            Document(
                page_content="""
                AWS Migration Best Practices and Strategies:
                
                1. Discovery and Assessment:
                - Use AWS Application Discovery Service for inventory
                - AWS Migration Hub for centralized tracking
                - AWS Well-Architected Review for optimization opportunities
                
                2. Migration Strategies (6 R's):
                - Rehost (Lift and Shift): Quick migration with minimal changes
                - Replatform (Lift, Tinker, and Shift): Minor optimizations
                - Refactor/Re-architect: Redesign for cloud-native benefits
                - Repurchase: Move to SaaS solutions
                - Retain: Keep on-premises for now
                - Retire: Decommission unnecessary applications
                
                3. Key AWS Migration Services:
                - AWS Server Migration Service (SMS): Migrate on-premises servers
                - AWS Database Migration Service (DMS): Migrate databases with minimal downtime
                - AWS DataSync: Transfer large amounts of data
                - AWS Snowball: Physical data transfer for large datasets
                
                4. Cost Optimization:
                - Reserved Instances for predictable workloads (up to 75% savings)
                - Spot Instances for fault-tolerant workloads (up to 90% savings)
                - Auto Scaling to match capacity with demand
                - S3 Intelligent Tiering for automatic storage optimization
                
                5. Security Best Practices:
                - Enable AWS CloudTrail for audit logging
                - Use AWS Config for compliance monitoring
                - Implement least privilege access with IAM
                - Enable encryption at rest and in transit
                """,
                metadata={"source": "aws_migration_guide", "type": "best_practices", "provider": "aws"}
            ),
            Document(
                page_content="""
                AWS Cost Structure and Pricing Models:
                
                Compute Services:
                - EC2 On-Demand: $0.0116/hour for t3.micro (1 vCPU, 1GB RAM)
                - EC2 Reserved (1-year): 40% discount, (3-year): 60% discount
                - Lambda: $0.20 per 1M requests + $0.0000166667 per GB-second
                - Fargate: $0.04048 per vCPU per hour + $0.004445 per GB per hour
                
                Storage Services:
                - S3 Standard: $0.023 per GB/month
                - S3 Intelligent Tiering: $0.0125 per GB/month + monitoring fees
                - EBS gp3: $0.08 per GB/month (20% cheaper than gp2)
                - EFS: $0.30 per GB/month for Standard class
                
                Database Services:
                - RDS MySQL db.t3.micro: $0.017/hour
                - DynamoDB On-Demand: $0.25 per million read requests
                - Aurora Serverless: $0.000090 per ACU per second
                
                Network Costs:
                - Data Transfer Out: First 1GB free, then $0.09/GB
                - CloudFront: $0.085 per GB for first 10TB
                - VPC Endpoints: $0.01 per hour + $0.01 per GB processed
                
                Startup Benefits:
                - AWS Activate credits up to $100,000 for qualified startups
                - 12-month free tier including 750 hours of t2.micro EC2
                - Always-free services like Lambda (1M requests/month)
                """,
                metadata={"source": "aws_pricing", "type": "cost_analysis", "provider": "aws"}
            )
        ]
    
    def _create_gcp_documents(self) -> List[Document]:
        """GCP-specific migration knowledge"""
        
        return [
            Document(
                page_content="""
                Google Cloud Platform Migration Strategies:
                
                1. Migration Approaches:
                - Lift and Shift: Use Migrate for Compute Engine
                - Improve and Move: Optimize during migration
                - Rip and Replace: Complete modernization with cloud-native services
                
                2. Key GCP Migration Tools:
                - Migrate for Compute Engine: Automated VM migration
                - Database Migration Service: Migrate to Cloud SQL with minimal downtime
                - Transfer Service: Move data from on-premises or other clouds
                - BigQuery Data Transfer Service: Migrate analytics workloads
                
                3. GCP Strengths:
                - Kubernetes-native platform (GKE is industry-leading)
                - Advanced AI/ML services (Vertex AI, AutoML)
                - Competitive pricing with sustained use discounts
                - Strong data analytics capabilities (BigQuery, Dataflow)
                - Excellent network infrastructure and global presence
                
                4. Container and Kubernetes Migration:
                - Google Kubernetes Engine (GKE) for container orchestration
                - Anthos for hybrid and multi-cloud management
                - Cloud Run for serverless containers
                - Migrate for Anthos to containerize existing applications
                
                5. Data and Analytics Migration:
                - BigQuery for data warehousing (serverless, petabyte-scale)
                - Dataflow for stream and batch processing
                - Pub/Sub for real-time messaging
                - Cloud Composer for workflow orchestration
                """,
                metadata={"source": "gcp_migration_guide", "type": "strategies", "provider": "gcp"}
            ),
            Document(
                page_content="""
                GCP Pricing and Cost Optimization:
                
                Compute Pricing:
                - Compute Engine e2-micro: $0.008/hour (1 vCPU, 1GB RAM)
                - Sustained Use Discounts: Automatic 20-50% discounts for long-running VMs
                - Committed Use Discounts: Up to 70% savings with 1-3 year commitments
                - Preemptible VMs: Up to 80% savings for fault-tolerant workloads
                
                Storage Pricing:
                - Cloud Storage Standard: $0.020 per GB/month
                - Persistent Disk SSD: $0.17 per GB/month
                - Cloud SQL MySQL db-n1-standard-1: $0.0825/hour
                
                Kubernetes and Containers:
                - GKE cluster management: $0.10 per cluster per hour
                - Cloud Run: $0.000024 per vCPU-second, $0.0000025 per GB-second
                - No charge for GKE cluster management with Autopilot mode
                
                Data and Analytics:
                - BigQuery: $5 per TB processed, $0.020 per GB stored
                - Pub/Sub: $0.40 per million messages
                - Cloud Functions: 2 million invocations free per month
                
                Network Costs:
                - Egress within same region: Free
                - Egress to other GCP regions: $0.01 per GB
                - Internet egress: $0.12 per GB (first 1GB free per month)
                
                Startup Benefits:
                - Google for Startups Cloud Program: Up to $100,000 in credits
                - Always Free tier: f1-micro instance, 30GB storage
                - $300 free trial credit for new accounts
                """,
                metadata={"source": "gcp_pricing", "type": "cost_analysis", "provider": "gcp"}
            )
        ]
    
    def _create_azure_documents(self) -> List[Document]:
        """Azure-specific migration knowledge"""
        
        return [
            Document(
                page_content="""
                Microsoft Azure Migration Strategies:
                
                1. Azure Migration Framework:
                - Assess: Use Azure Migrate for discovery and assessment
                - Migrate: Use Azure Site Recovery and Database Migration Service
                - Optimize: Implement Azure Advisor recommendations
                - Monitor: Use Azure Monitor and Security Center
                
                2. Key Azure Migration Services:
                - Azure Migrate: Unified migration platform
                - Azure Site Recovery: Disaster recovery and migration
                - Azure Database Migration Service: Migrate databases with minimal downtime
                - Azure Data Box: Physical data transfer service
                
                3. Azure Strengths:
                - Hybrid cloud capabilities with Azure Arc
                - Strong integration with Microsoft ecosystem (Office 365, Active Directory)
                - Comprehensive compliance and security offerings
                - Windows Server and SQL Server licensing benefits
                - Global presence with 60+ regions
                
                4. Hybrid and Multi-Cloud:
                - Azure Arc for managing resources across environments
                - Azure Stack for on-premises Azure services
                - Azure Kubernetes Service (AKS) for container orchestration
                - Azure Functions for serverless computing
                
                5. Enterprise Integration:
                - Active Directory integration for identity management
                - Microsoft 365 integration for productivity
                - Power Platform for low-code development
                - Dynamics 365 for business applications
                """,
                metadata={"source": "azure_migration_guide", "type": "approaches", "provider": "azure"}
            ),
            Document(
                page_content="""
                Azure Pricing and Cost Management:
                
                Compute Pricing:
                - Virtual Machines B1s: $0.0104/hour (1 vCPU, 1GB RAM)
                - Azure Reserved VM Instances: Up to 72% savings with 3-year commitment
                - Spot VMs: Up to 90% savings for interruptible workloads
                - Azure Functions: 1 million executions free per month
                
                Storage Pricing:
                - Blob Storage Hot tier: $0.0184 per GB/month
                - Managed Disks Standard SSD: $0.075 per GB/month
                - Azure SQL Database Basic: $4.90/month
                
                Platform Services:
                - App Service Basic B1: $0.075/hour
                - Azure Kubernetes Service: Free cluster management
                - Logic Apps: $0.000025 per action execution
                
                Data Services:
                - Azure Synapse Analytics: Pay-per-query model available
                - Cosmos DB: $0.25 per million request units
                - Event Hubs: $0.028 per million events
                
                Network Costs:
                - Bandwidth within same region: Free
                - Outbound data transfer: First 5GB free, then $0.087/GB
                - VPN Gateway: $0.04/hour for Basic SKU
                
                Cost Management Tools:
                - Azure Cost Management + Billing for cost analysis
                - Azure Advisor for optimization recommendations
                - Budgets and alerts for cost control
                
                Startup Benefits:
                - Microsoft for Startups: Up to $120,000 in Azure credits
                - 12-month free services including 750 hours of B1S VM
                - Always-free services like App Service and Functions
                """,
                metadata={"source": "azure_pricing", "type": "cost_analysis", "provider": "azure"}
            )
        ]
    
    def _create_startup_documents(self) -> List[Document]:
        """Startup-specific migration considerations"""
        
        return [
            Document(
                page_content="""
                Cloud Migration Considerations for Startups:
                
                1. Budget Constraints and Cost Management:
                - Start with free tiers and credits from cloud providers
                - Use auto-scaling to avoid over-provisioning
                - Implement cost monitoring and alerts from day one
                - Consider spot/preemptible instances for development environments
                - Plan for growth but avoid premature optimization
                
                2. Limited Technical Resources:
                - Prioritize managed services over self-managed infrastructure
                - Use Platform-as-a-Service (PaaS) offerings when possible
                - Leverage cloud provider support and documentation
                - Consider hiring cloud consultants for critical decisions
                - Invest in team training and certification
                
                3. Rapid Scaling Requirements:
                - Design for horizontal scaling from the beginning
                - Use containerization for consistent deployments
                - Implement CI/CD pipelines for rapid iteration
                - Choose services that can scale automatically
                - Plan database architecture for growth
                
                4. Time to Market Pressure:
                - Use cloud-native services to accelerate development
                - Leverage existing solutions (SaaS) where possible
                - Focus on core business logic, not infrastructure
                - Use infrastructure-as-code for reproducible deployments
                - Implement monitoring and observability early
                
                5. Compliance and Security on a Budget:
                - Use cloud provider security tools and best practices
                - Implement security by design, not as an afterthought
                - Leverage compliance certifications from cloud providers
                - Use managed identity and access management services
                - Regular security audits and penetration testing
                
                6. Technology Stack Decisions:
                - Choose technologies with strong cloud support
                - Consider serverless architectures for cost efficiency
                - Use microservices for scalability and team autonomy
                - Implement proper logging and monitoring
                - Plan for disaster recovery and business continuity
                """,
                metadata={"source": "startup_migration_guide", "type": "startup_specific", "category": "planning"}
            ),
            Document(
                page_content="""
                Startup Cloud Migration Timeline and Phases:
                
                Phase 1: Foundation (Weeks 1-2)
                - Cloud account setup and initial security configuration
                - Team training on cloud fundamentals
                - Development environment setup
                - CI/CD pipeline implementation
                - Basic monitoring and logging setup
                
                Phase 2: Core Infrastructure (Weeks 3-4)
                - Production environment setup
                - Database migration planning and testing
                - Network configuration and security groups
                - Load balancer and auto-scaling configuration
                - Backup and disaster recovery setup
                
                Phase 3: Application Migration (Weeks 5-8)
                - Gradual application migration with blue-green deployments
                - Database migration with minimal downtime
                - DNS cutover and traffic routing
                - Performance testing and optimization
                - User acceptance testing
                
                Phase 4: Optimization (Weeks 9-10)
                - Cost optimization and right-sizing
                - Performance tuning and monitoring setup
                - Security hardening and compliance validation
                - Documentation and knowledge transfer
                - Post-migration support and maintenance planning
                
                Success Factors:
                - Executive sponsorship and clear communication
                - Dedicated migration team with cloud expertise
                - Comprehensive testing at each phase
                - Rollback plans for each migration step
                - Regular stakeholder updates and feedback
                
                Common Pitfalls to Avoid:
                - Underestimating data migration complexity
                - Insufficient testing of integrated systems
                - Neglecting security and compliance requirements
                - Poor change management and user communication
                - Inadequate post-migration monitoring and support
                """,
                metadata={"source": "startup_timeline", "type": "planning", "category": "timeline"}
            )
        ]
    
    def _create_cost_documents(self) -> List[Document]:
        """Cost optimization knowledge"""
        
        return [
            Document(
                page_content="""
                Cloud Cost Optimization Strategies:
                
                1. Right-Sizing Resources:
                - Monitor CPU, memory, and network utilization
                - Use cloud provider recommendations for instance sizing
                - Implement auto-scaling to match demand
                - Regular review and adjustment of resource allocations
                - Consider burstable instances for variable workloads
                
                2. Storage Optimization:
                - Use appropriate storage classes (hot, cool, archive)
                - Implement lifecycle policies for automatic tiering
                - Compress and deduplicate data where possible
                - Regular cleanup of unused snapshots and backups
                - Use block storage only when necessary
                
                3. Network Cost Management:
                - Minimize data transfer between regions
                - Use content delivery networks (CDNs) for global content
                - Implement data compression for transfers
                - Choose regions strategically based on user location
                - Use private networks for internal communication
                
                4. Reserved Capacity and Commitments:
                - Purchase reserved instances for predictable workloads
                - Use savings plans for flexible compute commitments
                - Analyze usage patterns before making commitments
                - Consider convertible reservations for flexibility
                - Monitor and optimize reservation utilization
                
                5. Serverless and Managed Services:
                - Use serverless functions for event-driven workloads
                - Leverage managed databases to reduce operational overhead
                - Implement auto-scaling for managed services
                - Use managed container services for orchestration
                - Consider serverless data processing for batch jobs
                
                6. Cost Monitoring and Governance:
                - Implement cost allocation tags for chargeback
                - Set up budget alerts and spending limits
                - Regular cost reviews and optimization sessions
                - Use cost management tools and dashboards
                - Establish cost optimization as part of development process
                """,
                metadata={"source": "cost_optimization", "type": "cost_strategies", "category": "optimization"}
            )
        ]
    
    def _create_security_documents(self) -> List[Document]:
        """Security and compliance knowledge"""
        
        return [
            Document(
                page_content="""
                Cloud Security Best Practices for Migration:
                
                1. Identity and Access Management:
                - Implement multi-factor authentication (MFA) for all users
                - Use role-based access control (RBAC) with least privilege
                - Regular access reviews and deprovisioning
                - Service accounts with minimal permissions
                - Centralized identity management with SSO
                
                2. Data Protection:
                - Encrypt data at rest using cloud-managed keys
                - Encrypt data in transit with TLS/SSL
                - Implement proper key management and rotation
                - Data classification and handling procedures
                - Regular data backup and recovery testing
                
                3. Network Security:
                - Use virtual private clouds (VPCs) for network isolation
                - Implement security groups and network ACLs
                - Deploy web application firewalls (WAF)
                - Network monitoring and intrusion detection
                - Secure VPN or private connectivity for hybrid setups
                
                4. Compliance Requirements:
                - GDPR: Data residency, consent management, right to be forgotten
                - HIPAA: PHI protection, business associate agreements, audit logs
                - PCI DSS: Secure payment processing, network segmentation
                - SOC 2: Security controls, availability, confidentiality
                - ISO 27001: Information security management system
                
                5. Monitoring and Incident Response:
                - Centralized logging and security information management
                - Real-time security monitoring and alerting
                - Incident response procedures and playbooks
                - Regular security assessments and penetration testing
                - Vulnerability management and patch procedures
                
                6. Cloud Provider Security:
                - Understand shared responsibility model
                - Use cloud-native security services
                - Enable security features by default
                - Regular security configuration reviews
                - Leverage cloud provider compliance certifications
                """,
                metadata={"source": "security_compliance", "type": "security", "category": "compliance"}
            )
        ]
    
    def _create_planning_documents(self) -> List[Document]:
        """Migration planning and project management"""
        
        return [
            Document(
                page_content="""
                Cloud Migration Project Planning and Risk Management:
                
                1. Migration Assessment and Planning:
                - Comprehensive inventory of current infrastructure
                - Application dependency mapping and analysis
                - Performance baseline establishment
                - Cost-benefit analysis and ROI calculation
                - Risk assessment and mitigation planning
                
                2. Migration Strategy Selection:
                - Rehost (Lift and Shift): 6-8 weeks, low risk, minimal optimization
                - Replatform: 8-12 weeks, medium risk, some optimization
                - Refactor: 12-24 weeks, high risk, maximum optimization
                - Hybrid approach: Phased migration with different strategies
                
                3. Team Structure and Roles:
                - Migration project manager for coordination
                - Cloud architect for technical design
                - DevOps engineers for implementation
                - Security specialist for compliance
                - Business stakeholders for requirements
                
                4. Risk Mitigation Strategies:
                - Comprehensive backup and recovery procedures
                - Pilot migrations with non-critical applications
                - Rollback plans for each migration phase
                - Performance and security testing at each stage
                - Change management and user communication
                
                5. Success Metrics and KPIs:
                - Migration timeline adherence
                - Cost reduction achievements
                - Performance improvement metrics
                - Security and compliance validation
                - User satisfaction and adoption rates
                
                6. Post-Migration Optimization:
                - Continuous monitoring and performance tuning
                - Cost optimization and right-sizing
                - Security hardening and compliance validation
                - Team training and knowledge transfer
                - Documentation and process improvement
                """,
                metadata={"source": "migration_planning", "type": "project_management", "category": "planning"}
            )
        ]
    
    def search_knowledge(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search the knowledge base for relevant information"""
        
        if not self.vector_store:
            self.setup_knowledge_base()
        
        try:
            # Perform similarity search
            results = self.vector_store.similarity_search_with_score(query, k=k)
            
            # Format results
            formatted_results = []
            for doc, score in results:
                formatted_results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "relevance_score": score
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Knowledge search error: {e}")
            return []
    
    def get_provider_specific_info(self, provider: str, topic: str = None) -> List[Dict[str, Any]]:
        """Get provider-specific information"""
        
        if not self.vector_store:
            self.setup_knowledge_base()
        
        # Create provider-specific query
        query = f"{provider} cloud migration"
        if topic:
            query += f" {topic}"
        
        # Search with provider filter
        try:
            results = self.vector_store.similarity_search(
                query, 
                k=3,
                filter={"provider": provider.lower()}
            )
            
            return [{"content": doc.page_content, "metadata": doc.metadata} for doc in results]
            
        except Exception as e:
            logger.error(f"Provider search error: {e}")
            return []


# Test function
def test_knowledge_base():
    """Test the knowledge base functionality"""
    
    kb = MigrationKnowledgeBase()
    kb.setup_knowledge_base()
    
    # Test queries
    test_queries = [
        "AWS cost optimization strategies",
        "GCP Kubernetes migration",
        "Azure security best practices",
        "startup cloud migration timeline",
        "database migration with minimal downtime"
    ]
    
    for query in test_queries:
        print(f"\n=== Query: {query} ===")
        results = kb.search_knowledge(query, k=2)
        
        for i, result in enumerate(results):
            print(f"\nResult {i+1} (Score: {result.get('relevance_score', 'N/A')}):")
            print(f"Source: {result['metadata'].get('source', 'Unknown')}")
            print(f"Content: {result['content'][:200]}...")


if __name__ == "__main__":
    test_knowledge_base()

