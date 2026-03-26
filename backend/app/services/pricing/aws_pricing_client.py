"""
AWS Pricing API Client

Integrates with AWS Price List API to retrieve current pricing data.
Supports EC2, S3, EBS, and other AWS services pricing.
"""

import asyncio
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
import aiohttp
from urllib.parse import urlencode
import boto3
from concurrent.futures import ThreadPoolExecutor

from app.services.pricing.base_pricing_client import BasePricingClient, PricingAPIException, RateLimitException
from app.services.pricing.pricing_models import ComputePricing, StoragePricing, NetworkPricing, DatabasePricing

logger = logging.getLogger(__name__)


class AWSPricingClient(BasePricingClient):
    """
    AWS Pricing API client for retrieving current AWS service pricing.
    
    Uses the AWS Price List API which is publicly accessible and doesn't require authentication.
    Rate limit: 100 requests per second.
    """
    
    # AWS Price List API endpoints
    BASE_URL = "https://pricing.us-east-1.amazonaws.com"
    OFFERS_URL = f"{BASE_URL}/offers/v1.0/aws"
    
    # AWS service codes
    SERVICE_CODES = {
        'ec2': 'AmazonEC2',
        's3': 'AmazonS3',
        'ebs': 'AmazonEC2',  # EBS pricing is part of EC2
        'rds': 'AmazonRDS',
        'lambda': 'AWSLambda',
        'cloudfront': 'AmazonCloudFront',
        'elb': 'AWSELB'
    }
    
    # AWS region mapping
    REGION_MAPPING = {
        'us-east-1': 'US East (N. Virginia)',
        'us-east-2': 'US East (Ohio)',
        'us-west-1': 'US West (N. California)',
        'us-west-2': 'US West (Oregon)',
        'eu-west-1': 'Europe (Ireland)',
        'eu-west-2': 'Europe (London)',
        'eu-central-1': 'Europe (Frankfurt)',
        'ap-southeast-1': 'Asia Pacific (Singapore)',
        'ap-southeast-2': 'Asia Pacific (Sydney)',
        'ap-northeast-1': 'Asia Pacific (Tokyo)',
        'ap-south-1': 'Asia Pacific (Mumbai)',
        'sa-east-1': 'South America (São Paulo)',
        'ca-central-1': 'Canada (Central)',
        'ap-northeast-2': 'Asia Pacific (Seoul)',
        'eu-west-3': 'Europe (Paris)',
        'eu-north-1': 'Europe (Stockholm)',
        'ap-east-1': 'Asia Pacific (Hong Kong)',
        'me-south-1': 'Middle East (Bahrain)',
        'af-south-1': 'Africa (Cape Town)',
        'eu-south-1': 'Europe (Milan)',
        'ap-northeast-3': 'Asia Pacific (Osaka)',
        'ap-southeast-3': 'Asia Pacific (Jakarta)'
    }
    
    def __init__(self, region: str = "us-east-1"):
        """Initialize AWS pricing client."""
        super().__init__("aws", region)
        self.session = None
        self.executor = ThreadPoolExecutor(max_workers=5)
        self._setup_rate_limiting()
    
    def _setup_rate_limiting(self):
        """Setup rate limiting for AWS API calls (100 requests/second)."""
        self.rate_limit_delay = 0.01  # 10ms delay between requests
        self.last_request_time = 0
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make HTTP request to AWS Pricing API with rate limiting.
        
        Args:
            url: API endpoint URL
            params: Query parameters
            
        Returns:
            Dict: JSON response data
            
        Raises:
            PricingAPIException: If request fails
        """
        try:
            # Apply rate limiting
            await self._handle_rate_limiting()
            
            session = await self._get_session()
            
            # Build full URL with parameters
            if params:
                url = f"{url}?{urlencode(params)}"
            
            logger.debug(f"Making AWS pricing API request: {url}")
            
            async with session.get(url) as response:
                if response.status == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    raise RateLimitException("aws", retry_after)
                
                if response.status != 200:
                    error_text = await response.text()
                    raise PricingAPIException(
                        f"HTTP {response.status}: {error_text}",
                        "aws",
                        response.status
                    )
                
                return await response.json()
                
        except aiohttp.ClientError as e:
            raise PricingAPIException(f"Network error: {str(e)}", "aws")
        except json.JSONDecodeError as e:
            raise PricingAPIException(f"Invalid JSON response: {str(e)}", "aws")
    
    async def _handle_rate_limiting(self):
        """Handle rate limiting with delay."""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - time_since_last)
        
        self.last_request_time = asyncio.get_event_loop().time()
    
    def _normalize_region(self, region: str) -> str:
        """Convert AWS region code to pricing API region name."""
        return self.REGION_MAPPING.get(region, region)
    
    def _get_pricing_client(self):
        if not hasattr(self, '_boto3_client'):
            self._boto3_client = boto3.client('pricing', region_name='us-east-1')
        return self._boto3_client
        
    def _fetch_pricing_sync(self, service_code: str, filters: list) -> list:
        try:
            client = self._get_pricing_client()
            response = client.get_products(
                ServiceCode=service_code,
                Filters=filters,
                MaxResults=100
            )
            return [json.loads(p) for p in response.get('PriceList', [])]
        except Exception as e:
            logger.error(f"Sync pricing fetch failed: {e}")
            return []

    async def get_compute_pricing(
        self, 
        region: str, 
        instance_type: Optional[str] = None,
        operating_system: str = "linux",
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ComputePricing]:
        try:
            logger.info(f"Fetching AWS EC2 pricing for region {region}")
            
            os_map = {
                'linux': 'Linux',
                'windows': 'Windows'
            }
            aws_os = os_map.get(operating_system.lower(), 'Linux')
            region_name = self._normalize_region(region)
            
            api_filters = [
                {'Type': 'TERM_MATCH', 'Field': 'ServiceCode', 'Value': 'AmazonEC2'},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region_name},
                {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': aws_os},
                {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
                {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'}
            ]
            if instance_type:
                api_filters.append({'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type})
                
            loop = asyncio.get_event_loop()
            price_list = await loop.run_in_executor(
                self.executor, 
                self._fetch_pricing_sync, 
                'AmazonEC2', 
                api_filters
            )
            
            pricing_data = []
            for item in price_list:
                attrs = item.get('product', {}).get('attributes', {})
                inst_type = attrs.get('instanceType', 'Unknown')
                if inst_type == 'Unknown': continue
                
                vcpus = int(attrs.get('vcpu', 0))
                memory_str = attrs.get('memory', '0')
                try:
                    memory_gb = float(memory_str.replace(' GiB', '').replace(',', ''))
                except:
                    memory_gb = 0.0
                    
                on_demand_terms = item.get('terms', {}).get('OnDemand', {})
                price_per_hour = Decimal("0")
                for term in on_demand_terms.values():
                    for dim in term.get('priceDimensions', {}).values():
                        if dim.get('unit') == 'Hrs':
                            price_per_hour = Decimal(dim.get('pricePerUnit', {}).get('USD', '0'))
                
                if price_per_hour == 0: continue
                
                pricing = ComputePricing(
                    instance_type=inst_type,
                    vcpus=vcpus,
                    memory_gb=memory_gb,
                    price_per_hour=price_per_hour,
                    price_per_month=price_per_hour * Decimal("730"),
                    operating_system=operating_system,
                    region=region,
                    currency="USD",
                    architecture=attrs.get('physicalProcessor', 'x86_64'),
                    additional_specs={'network_performance': attrs.get('networkPerformance')}
                )
                pricing_data.append(pricing)
                
            return pricing_data
        except Exception as e:
            logger.error(f"Failed to get AWS compute pricing: {e}")
            raise PricingAPIException(f"Failed to get compute pricing: {str(e)}", "aws")
            
    async def get_storage_pricing(
        self, 
        region: str, 
        storage_type: Optional[str] = None,
        storage_class: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[StoragePricing]:
        try:
            logger.info(f"Fetching AWS storage pricing for region {region}")
            pricing_data = []
            region_name = self._normalize_region(region)
            loop = asyncio.get_event_loop()
            
            # S3
            if not storage_type or storage_type == "object":
                s3_filters = [
                    {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region_name},
                    {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Storage'}
                ]
                s3_list = await loop.run_in_executor(self.executor, self._fetch_pricing_sync, 'AmazonS3', s3_filters)
                for item in s3_list:
                    attrs = item.get('product', {}).get('attributes', {})
                    vol_type = attrs.get('volumeType', 'Standard')
                    
                    if storage_class and storage_class.lower() not in vol_type.lower():
                        continue
                        
                    on_demand_terms = item.get('terms', {}).get('OnDemand', {})
                    price = Decimal("0")
                    for term in on_demand_terms.values():
                        for dim in term.get('priceDimensions', {}).values():
                            if 'GB-Mo' in dim.get('unit', ''):
                                price = Decimal(dim.get('pricePerUnit', {}).get('USD', '0'))
                    
                    if price > 0:
                        pricing_data.append(StoragePricing(
                            storage_type="object",
                            price_per_gb_month=price,
                            region=region,
                            currency="USD",
                            storage_class=vol_type,
                            additional_specs={'durability': attrs.get('durability')}
                        ))
                        
            # EBS
            if not storage_type or storage_type == "block":
                ebs_filters = [
                    {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region_name},
                    {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Storage'}
                ]
                ebs_list = await loop.run_in_executor(self.executor, self._fetch_pricing_sync, 'AmazonEC2', ebs_filters)
                for item in ebs_list:
                    attrs = item.get('product', {}).get('attributes', {})
                    vol_type = attrs.get('volumeApiName', 'gp3')
                    
                    if storage_class and storage_class.lower() != vol_type.lower():
                        continue
                        
                    on_demand_terms = item.get('terms', {}).get('OnDemand', {})
                    price = Decimal("0")
                    for term in on_demand_terms.values():
                        for dim in term.get('priceDimensions', {}).values():
                            if 'GB-Mo' in dim.get('unit', ''):
                                price = Decimal(dim.get('pricePerUnit', {}).get('USD', '0'))
                    
                    if price > 0:
                        pricing_data.append(StoragePricing(
                            storage_type="block",
                            price_per_gb_month=price,
                            region=region,
                            currency="USD",
                            storage_class=vol_type,
                            additional_specs={'max_iops': attrs.get('maxIopsvolume')}
                        ))
                        
            return pricing_data
        except Exception as e:
            logger.error(f"Failed to get AWS storage pricing: {e}")
            raise PricingAPIException(f"Failed to get storage pricing: {str(e)}", "aws")
            
    async def get_network_pricing(
        self, 
        region: str,
        service_type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[NetworkPricing]:
        try:
            logger.info(f"Fetching AWS network pricing for region {region}")
            pricing_data = []
            region_name = self._normalize_region(region)
            loop = asyncio.get_event_loop()
            
            # ELB
            if not service_type or service_type == "load_balancer":
                elb_filters = [
                    {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region_name},
                    {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Load Balancer'}
                ]
                elb_list = await loop.run_in_executor(self.executor, self._fetch_pricing_sync, 'AWSELB', elb_filters)
                for item in elb_list:
                    attrs = item.get('product', {}).get('attributes', {})
                    group = attrs.get('usagetype', '')
                    
                    on_demand_terms = item.get('terms', {}).get('OnDemand', {})
                    price = Decimal("0")
                    for term in on_demand_terms.values():
                        for dim in term.get('priceDimensions', {}).values():
                            if 'Hrs' in dim.get('unit', ''):
                                price = Decimal(dim.get('pricePerUnit', {}).get('USD', '0'))
                                
                    if price > 0:
                        pricing_data.append(NetworkPricing(
                            service_type="load_balancer",
                            price_per_hour=price,
                            region=region,
                            currency="USD",
                            additional_specs={'type': attrs.get('loadBalancerType', 'Classic')}
                        ))
                    
            # Data Transfer approximations
            if not service_type or service_type == "data_transfer":
                pricing_data.append(NetworkPricing(
                    service_type="data_transfer",
                    price_per_gb=Decimal("0.09"),
                    region=region,
                    currency="USD",
                    transfer_type="outbound",
                    bandwidth_tier="first_10tb",
                    additional_specs={'description': 'Data transfer out to internet (API Approximation)'}
                ))
            
            return pricing_data
        except Exception as e:
            logger.error(f"Failed to get AWS network pricing: {e}")
            raise PricingAPIException(f"Failed to get network pricing: {str(e)}", "aws")
            
    async def get_database_pricing(
        self, 
        region: str,
        database_type: Optional[str] = None,
        instance_class: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[DatabasePricing]:
        try:
            logger.info(f"Fetching AWS RDS pricing for region {region}")
            pricing_data = []
            region_name = self._normalize_region(region)
            
            api_filters = [
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region_name},
                {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Database Instance'}
            ]
            if database_type:
                engine_map = {
                    'mysql': 'MySQL',
                    'postgresql': 'PostgreSQL',
                    'mariadb': 'MariaDB',
                    'oracle': 'Oracle',
                    'sqlserver': 'SQL Server'
                }
                api_filters.append({'Type': 'TERM_MATCH', 'Field': 'databaseEngine', 'Value': engine_map.get(database_type.lower(), database_type)})
            if instance_class:
                api_filters.append({'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_class})
                
            loop = asyncio.get_event_loop()
            rds_list = await loop.run_in_executor(
                self.executor, 
                self._fetch_pricing_sync, 
                'AmazonRDS', 
                api_filters
            )
            
            for item in rds_list:
                attrs = item.get('product', {}).get('attributes', {})
                inst_class = attrs.get('instanceType', 'Unknown')
                if inst_class == 'Unknown': continue
                
                engine = attrs.get('databaseEngine', 'Unknown')
                
                on_demand_terms = item.get('terms', {}).get('OnDemand', {})
                price = Decimal("0")
                for term in on_demand_terms.values():
                    for dim in term.get('priceDimensions', {}).values():
                        if dim.get('unit') == 'Hrs':
                            price = Decimal(dim.get('pricePerUnit', {}).get('USD', '0'))
                
                if price == 0: continue
                
                pricing_data.append(DatabasePricing(
                    database_type=engine,
                    instance_class=inst_class,
                    price_per_hour=price,
                    storage_price_per_gb_month=Decimal("0.115"), # Approximate average
                    region=region,
                    currency="USD",
                    engine_version=f"{engine}-latest",
                    multi_az=attrs.get('deploymentOption', '').lower() == 'multi-az',
                    backup_storage_price=Decimal("0.095"),
                    additional_specs={'deploymentOption': attrs.get('deploymentOption')}
                ))
            return pricing_data
        except Exception as e:
            logger.error(f"Failed to get AWS database pricing: {e}")
            raise PricingAPIException(f"Failed to get database pricing: {str(e)}", "aws")
    
    async def get_supported_regions(self) -> List[str]:
        """Get list of supported AWS regions."""
        return list(self.REGION_MAPPING.keys())
    
    async def get_supported_instance_types(self, region: str) -> List[str]:
        """Get list of supported EC2 instance types."""
        return [
            't3.micro', 't3.small', 't3.medium', 't3.large', 't3.xlarge',
            'm5.large', 'm5.xlarge', 'm5.2xlarge',
            'c5.large', 'c5.xlarge',
            'r5.large', 'r5.xlarge'
        ]
    
    async def validate_region(self, region: str) -> bool:
        """Validate if the AWS region is supported."""
        return region in self.REGION_MAPPING
    
    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
