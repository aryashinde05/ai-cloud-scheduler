"""
Azure Pricing API Client

Integrates with Azure Retail Prices API to retrieve current pricing data.
Supports Virtual Machines, Storage, and other Azure services pricing.
"""

import asyncio
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
import aiohttp
from urllib.parse import urlencode

from app.services.pricing.base_pricing_client import BasePricingClient, PricingAPIException, RateLimitException
from app.services.pricing.pricing_models import ComputePricing, StoragePricing, NetworkPricing, DatabasePricing

logger = logging.getLogger(__name__)


class AzurePricingClient(BasePricingClient):
    """
    Azure Retail Prices API client for retrieving current Azure service pricing.
    
    Uses the Azure Retail Prices API which is publicly accessible.
    Rate limit: 100 requests per minute.
    """
    
    # Azure Retail Prices API endpoint
    BASE_URL = "https://prices.azure.com/api/retail/prices"
    
    # Azure service names
    SERVICE_NAMES = {
        'compute': 'Virtual Machines',
        'storage': 'Storage',
        'network': 'Bandwidth',
        'sql': 'SQL Database',
        'functions': 'Functions'
    }
    
    # Azure region mapping
    REGION_MAPPING = {
        'eastus': 'East US',
        'eastus2': 'East US 2',
        'westus': 'West US',
        'westus2': 'West US 2',
        'westus3': 'West US 3',
        'centralus': 'Central US',
        'northcentralus': 'North Central US',
        'southcentralus': 'South Central US',
        'westcentralus': 'West Central US',
        'canadacentral': 'Canada Central',
        'canadaeast': 'Canada East',
        'brazilsouth': 'Brazil South',
        'northeurope': 'North Europe',
        'westeurope': 'West Europe',
        'uksouth': 'UK South',
        'ukwest': 'UK West',
        'francecentral': 'France Central',
        'francesouth': 'France South',
        'germanywestcentral': 'Germany West Central',
        'norwayeast': 'Norway East',
        'switzerlandnorth': 'Switzerland North',
        'eastasia': 'East Asia',
        'southeastasia': 'Southeast Asia',
        'japaneast': 'Japan East',
        'japanwest': 'Japan West',
        'australiaeast': 'Australia East',
        'australiasoutheast': 'Australia Southeast',
        'centralindia': 'Central India',
        'southindia': 'South India',
        'westindia': 'West India',
        'koreacentral': 'Korea Central',
        'koreasouth': 'Korea South',
        'uaenorth': 'UAE North',
        'southafricanorth': 'South Africa North'
    }
    
    def __init__(self, region: str = "eastus"):
        """Initialize Azure pricing client."""
        super().__init__("azure", region)
        self.session = None
        self._setup_rate_limiting()
    
    def _setup_rate_limiting(self):
        """Setup rate limiting for Azure API calls (100 requests per minute)."""
        self.rate_limit_delay = 0.6  # 600ms delay between requests
        self.last_request_time = 0
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make HTTP request to Azure Retail Prices API with rate limiting.
        
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
            
            logger.debug(f"Making Azure pricing API request: {url}")
            
            async with session.get(url) as response:
                if response.status == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    raise RateLimitException("azure", retry_after)
                
                if response.status != 200:
                    error_text = await response.text()
                    raise PricingAPIException(
                        f"HTTP {response.status}: {error_text}",
                        "azure",
                        response.status
                    )
                
                return await response.json()
                
        except aiohttp.ClientError as e:
            raise PricingAPIException(f"Network error: {str(e)}", "azure")
        except json.JSONDecodeError as e:
            raise PricingAPIException(f"Invalid JSON response: {str(e)}", "azure")
    
    async def _handle_rate_limiting(self):
        """Handle rate limiting with delay."""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - time_since_last)
        
        self.last_request_time = asyncio.get_event_loop().time()
    
    def _normalize_region(self, region: str) -> str:
        """Convert Azure region code to pricing API region name."""
        return self.REGION_MAPPING.get(region, region)
    
    async def get_compute_pricing(
        self, 
        region: str, 
        instance_type: Optional[str] = None,
        operating_system: str = "linux",
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ComputePricing]:
        """
        Get Virtual Machine pricing from Azure Retail Prices API.
        """
        try:
            logger.info(f"Fetching Azure VM pricing for region {region}")
            
            query_filters = [
                f"serviceName eq 'Virtual Machines'",
                f"armRegionName eq '{region}'",
                f"type eq 'Consumption'"
            ]
            
            if instance_type:
                query_filters.append(f"armSkuName eq '{instance_type}'")
                
            params = {
                "$filter": " and ".join(query_filters),
                "currencyCode": "USD"
            }
            
            data = await self._make_request(self.BASE_URL, params)
            pricing_data = []
            
            for item in data.get('Items', []):
                if item.get('unitOfMeasure') != '1 Hour':
                    continue
                
                prod_name = item.get('productName', '')
                if operating_system.lower() == 'windows':
                    if 'Windows' not in prod_name:
                        continue
                else:
                    if 'Windows' in prod_name:
                        continue
                
                sku = item.get('armSkuName', item.get('skuName', 'Unknown'))
                price = Decimal(str(item.get('retailPrice', 0)))
                
                pricing = ComputePricing(
                    instance_type=sku,
                    vcpus=0, # Azure Retail Prices API doesn't return vcpu/memory
                    memory_gb=0.0,
                    price_per_hour=price,
                    price_per_month=price * Decimal("730"),
                    operating_system=operating_system,
                    region=region,
                    currency=item.get('currencyCode', 'USD'),
                    architecture="x86_64",
                    additional_specs={
                        'productName': item.get('productName'),
                        'meterName': item.get('meterName')
                    }
                )
                pricing_data.append(pricing)
                
            return pricing_data
            
        except Exception as e:
            logger.error(f"Failed to get Azure compute pricing: {e}")
            raise PricingAPIException(f"Failed to get compute pricing: {str(e)}", "azure")
    
    async def get_storage_pricing(
        self, 
        region: str, 
        storage_type: Optional[str] = None,
        storage_class: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[StoragePricing]:
        """
        Get Azure Storage pricing from Retail Prices API.
        """
        try:
            logger.info(f"Fetching Azure storage pricing for region {region}")
            
            query_filters = [
                f"serviceFamily eq 'Storage'",
                f"armRegionName eq '{region}'"
            ]
            
            params = {
                "$filter": " and ".join(query_filters),
                "currencyCode": "USD"
            }
            
            data = await self._make_request(self.BASE_URL, params)
            pricing_data = []
            
            for item in data.get('Items', []):
                if 'GB/Month' not in item.get('unitOfMeasure', ''):
                    continue
                    
                sku = item.get('armSkuName', item.get('skuName', 'Unknown'))
                price = Decimal(str(item.get('retailPrice', 0)))
                
                # Try to infer storage type
                stype = "block" if "Disk" in item.get('productName', '') else "object"
                if storage_type and storage_type != stype:
                    continue
                    
                pricing = StoragePricing(
                    storage_type=stype,
                    price_per_gb_month=price,
                    region=region,
                    currency=item.get('currencyCode', 'USD'),
                    storage_class=sku,
                    additional_specs={
                        'productName': item.get('productName'),
                        'meterName': item.get('meterName')
                    }
                )
                pricing_data.append(pricing)
                
            return pricing_data
            
        except Exception as e:
            logger.error(f"Failed to get Azure storage pricing: {e}")
            raise PricingAPIException(f"Failed to get storage pricing: {str(e)}", "azure")
    
    async def get_network_pricing(
        self, 
        region: str,
        service_type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[NetworkPricing]:
        """
        Get Azure network service pricing.
        """
        try:
            logger.info(f"Fetching Azure network pricing for region {region}")
            
            query_filters = [
                f"serviceFamily eq 'Networking'",
                f"armRegionName eq '{region}'"
            ]
            
            params = {
                "$filter": " and ".join(query_filters),
                "currencyCode": "USD"
            }
            
            data = await self._make_request(self.BASE_URL, params)
            pricing_data = []
            
            for item in data.get('Items', []):
                sku = item.get('armSkuName', item.get('skuName', 'Unknown'))
                price = Decimal(str(item.get('retailPrice', 0)))
                unit = item.get('unitOfMeasure', '')
                
                # Simple heuristic to divide network types
                if 'GB' in unit:
                    # Data Transfer
                    if service_type and service_type != "data_transfer":
                        continue
                    pricing = NetworkPricing(
                        service_type="data_transfer",
                        price_per_gb=price,
                        region=region,
                        currency=item.get('currencyCode', 'USD'),
                        transfer_type="outbound" if "Outbound" in item.get('meterName', '') else "inbound",
                        additional_specs={'productName': item.get('productName')}
                    )
                    pricing_data.append(pricing)
                elif 'Hour' in unit:
                    # Load Balancer or similar hourly charges
                    if service_type and service_type != "load_balancer":
                        continue
                    pricing = NetworkPricing(
                        service_type="load_balancer",
                        price_per_hour=price,
                        region=region,
                        currency=item.get('currencyCode', 'USD'),
                        additional_specs={'productName': item.get('productName')}
                    )
                    pricing_data.append(pricing)
                    
            return pricing_data
            
        except Exception as e:
            logger.error(f"Failed to get Azure network pricing: {e}")
            raise PricingAPIException(f"Failed to get network pricing: {str(e)}", "azure")
    
    async def get_database_pricing(
        self, 
        region: str,
        database_type: Optional[str] = None,
        instance_class: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[DatabasePricing]:
        """
        Get Azure SQL Database pricing from Retail Prices API.
        """
        try:
            logger.info(f"Fetching Azure SQL pricing for region {region}")
            
            query_filters = [
                f"serviceFamily eq 'Databases'",
                f"armRegionName eq '{region}'"
            ]
            
            params = {
                "$filter": " and ".join(query_filters),
                "currencyCode": "USD"
            }
            
            data = await self._make_request(self.BASE_URL, params)
            pricing_data = []
            
            for item in data.get('Items', []):
                if item.get('unitOfMeasure') != '1 Hour':
                    continue
                    
                sku = item.get('armSkuName', item.get('skuName', 'Unknown'))
                price = Decimal(str(item.get('retailPrice', 0)))
                
                # Try to extract engine
                prod_name = item.get('productName', '').lower()
                engine = "sqlserver"
                if "mysql" in prod_name:
                    engine = "mysql"
                elif "postgresql" in prod_name:
                    engine = "postgresql"
                
                if database_type and engine != database_type.lower():
                    continue
                    
                pricing = DatabasePricing(
                    database_type=engine,
                    instance_class=sku,
                    price_per_hour=price,
                    storage_price_per_gb_month=Decimal("0"), # Needs separate query for storage
                    region=region,
                    currency=item.get('currencyCode', 'USD'),
                    engine_version=f"{engine}-latest",
                    multi_az=False,
                    backup_storage_price=Decimal("0"),
                    additional_specs={
                        'productName': item.get('productName'),
                        'meterName': item.get('meterName')
                    }
                )
                pricing_data.append(pricing)
                
            return pricing_data
            
        except Exception as e:
            logger.error(f"Failed to get Azure database pricing: {e}")
            raise PricingAPIException(f"Failed to get database pricing: {str(e)}", "azure")
    
    async def get_supported_regions(self) -> List[str]:
        """Get list of supported Azure regions."""
        return list(self.REGION_MAPPING.keys())
    
    async def get_supported_instance_types(self, region: str) -> List[str]:
        """Get list of supported Azure VM sizes."""
        return [
            'Standard_B1s', 'Standard_B1ms', 'Standard_B2s', 'Standard_B2ms', 'Standard_B4ms',
            'Standard_D2s_v3', 'Standard_D4s_v3', 'Standard_D8s_v3',
            'Standard_F2s_v2', 'Standard_F4s_v2',
            'Standard_E2s_v3', 'Standard_E4s_v3'
        ]
    
    async def validate_region(self, region: str) -> bool:
        """Validate if the Azure region is supported."""
        return region in self.REGION_MAPPING
    
    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
