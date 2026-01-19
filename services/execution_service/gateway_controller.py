"""
IB Gateway Docker Container Manager
Manages lifecycle of IB Gateway containers for IBKR accounts
"""
import docker
import logging
import time
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


class GatewayController:
    """Manages IB Gateway Docker containers (IBKR-specific)"""
    
    def __init__(self):
        """Initialize Docker client"""
        try:
            self.docker_client = docker.from_env()
            # Get network from current container's network settings
            # This way we automatically use whatever network docker-compose set up
            try:
                import socket
                hostname = socket.gethostname()
                container = self.docker_client.containers.get(hostname)
                networks = list(container.attrs['NetworkSettings']['Networks'].keys())
                self.network_name = networks[0] if networks else "tradenet"
                logger.info(f"Using Docker network: {self.network_name}")
            except:
                self.network_name = "tradenet"  # Fallback to docker-compose default
                logger.info(f"Using fallback network: {self.network_name}")
            
            logger.info("✅ Docker client initialized for gateway management")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Docker client: {e}")
            self.docker_client = None
    
    def gateway_exists(self, container_name: str) -> bool:
        """Check if gateway container already exists and is running"""
        if not self.docker_client:
            return False
        
        try:
            container = self.docker_client.containers.get(container_name)
            return container.status == 'running'
        except docker.errors.NotFound:
            return False
        except Exception as e:
            logger.error(f"Error checking gateway {container_name}: {e}")
            return False
    
    def create_gateway_for_account(self, account: Dict) -> bool:
        """
        Creates IB Gateway container for IBKR account.
        
        Args:
            account: Account document from MongoDB with authentication_details
            
        Returns:
            True if created/exists, False if failed.
            Only works for broker='IBKR'
        """
        if account['broker'] != 'IBKR':
            logger.debug(f"Account {account['account_id']} is {account['broker']} - no gateway needed")
            return True  # Not needed, but not an error
        
        if not self.docker_client:
            logger.error("❌ Docker client not available - cannot create gateway")
            return False
        
        auth = account.get('authentication_details', {})
        account_id = account['account_id']
        
        # Generate container name from account_id
        container_name = f"ib-gateway-{account_id.lower().replace('_', '-')}"
        
        # Check if already exists
        if self.gateway_exists(container_name):
            logger.info(f"✓ IB Gateway {container_name} already running")
            return True
        
        # Validate required fields
        if 'username' not in auth or 'password' not in auth:
            logger.error(f"❌ Account {account_id} missing username/password in authentication_details")
            return False
        
        # Get configuration
        username = auth['username']
        password = auth['password']
        trading_mode = auth.get('trading_mode', 'paper')
        
        # Determine ports
        if trading_mode == 'live':
            internal_port = 4003  # Live API port
        else:
            internal_port = 4004  # Paper API port
        
        logger.info(f"🚀 Creating IB Gateway for {account_id} (mode: {trading_mode})...")
        
        # Build environment variables
        env_vars = {
            'TWS_USERID': username,
            'TWS_PASSWORD': password,
            'TRADING_MODE': trading_mode,
            'TWOFA_TIMEOUT_ACTION': 'restart',  # Auto-handle 2FA by restarting
            'READ_ONLY_API': 'no',
            'IBC_AcceptIncomingConnectionAction': 'accept',
            'IBC_ExistingSessionDetectedAction': 'primary',  # Make gateway primary, web becomes read-only
            'IBC_AcceptNonBrokerageAccountWarning': 'yes',  # Accept paper account warnings
            'VNC_SERVER_PASSWORD': 'ibgateway'
        }
        
        try:
            # Create container
            container = self.docker_client.containers.run(
                image="ghcr.io/gnzsnz/ib-gateway:latest",
                name=container_name,
                ports={
                    f'{internal_port}/tcp': None,  # Auto-assign host port
                    '5900/tcp': None  # VNC
                },
                environment=env_vars,
                network=self.network_name,
                detach=True,
                restart_policy={"Name": "unless-stopped"}
            )
            
            logger.info(f"✅ Created IB Gateway container: {container_name}")
            logger.info(f"   Container ID: {container.short_id}")
            
            # Wait for gateway to be ready (can take 30-60 seconds)
            logger.info(f"⏳ Waiting for IB Gateway to be ready (this can take 60s)...")
            time.sleep(5)  # Give it a moment to start
            
            # Update authentication_details with gateway host
            # (This should be saved back to MongoDB by caller)
            auth['host'] = container_name  # Docker service name
            auth['port'] = internal_port
            
            return True
            
        except docker.errors.ImageNotFound:
            logger.error(f"❌ IB Gateway image not found. Run: docker pull ghcr.io/gnzsnz/ib-gateway:latest")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to create IB Gateway {container_name}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def stop_gateway(self, container_name: str) -> bool:
        """Stop and remove gateway container"""
        if not self.docker_client:
            return False
        
        try:
            container = self.docker_client.containers.get(container_name)
            container.stop(timeout=10)
            container.remove()
            logger.info(f"✅ Stopped and removed gateway: {container_name}")
            return True
        except docker.errors.NotFound:
            logger.warning(f"Gateway {container_name} not found")
            return False
        except Exception as e:
            logger.error(f"Failed to stop gateway {container_name}: {e}")
            return False
    
    def get_running_gateways(self) -> List[str]:
        """Get list of running IB Gateway containers"""
        if not self.docker_client:
            return []
        
        try:
            containers = self.docker_client.containers.list(filters={"name": "ib-gateway-"})
            return [c.name for c in containers]
        except Exception as e:
            logger.error(f"Failed to list gateways: {e}")
            return []
