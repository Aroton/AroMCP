"""
Configuration management for workflow server.
"""

import os
import yaml
import asyncio
from typing import Dict, Any, List
from pathlib import Path


class ConfigValidator:
    """Validates configuration schemas."""
    
    def validate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration against schema."""
        errors = []
        
        # Check workflow server config
        if 'workflow_server' in config:
            ws_config = config['workflow_server']
            
            # Validate numeric values
            if 'max_concurrent_workflows' in ws_config:
                if ws_config['max_concurrent_workflows'] < 0:
                    errors.append('max_concurrent_workflows must be non-negative')
            
            # Validate monitoring config
            if 'monitoring' in ws_config:
                mon_config = ws_config['monitoring']
                if 'export_format' in mon_config:
                    valid_formats = ['prometheus', 'json', 'csv']
                    if mon_config['export_format'] not in valid_formats:
                        errors.append(f'Invalid export_format: {mon_config["export_format"]}')
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }


class ConfigLoader:
    """Loads configuration with environment variable overrides."""
    
    def load_with_overrides(self, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """Load configuration with environment overrides."""
        config = base_config.copy()
        
        # Apply environment overrides
        if 'WORKFLOW_MAX_CONCURRENT' in os.environ:
            config.setdefault('workflow_server', {})['max_concurrent_workflows'] = int(os.environ['WORKFLOW_MAX_CONCURRENT'])
        
        if 'WORKFLOW_TIMEOUT' in os.environ:
            config.setdefault('workflow_server', {})['default_timeout'] = int(os.environ['WORKFLOW_TIMEOUT'])
        
        if 'WORKFLOW_MONITORING_ENABLED' in os.environ:
            config.setdefault('workflow_server', {})['enable_monitoring'] = os.environ['WORKFLOW_MONITORING_ENABLED'].lower() == 'true'
        
        return config


class ConfigManager:
    """Manages configuration with hot-reload support."""
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = {}
        self.watching = False
        self._load_config()
    
    def _load_config(self):
        """Load configuration from file."""
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        return self.config.copy()
    
    def start_watching(self):
        """Start watching for configuration changes."""
        self.watching = True
        asyncio.create_task(self._watch_config())
    
    def stop_watching(self):
        """Stop watching for configuration changes."""
        self.watching = False
    
    async def _watch_config(self):
        """Watch configuration file for changes."""
        last_mtime = self.config_path.stat().st_mtime
        
        while self.watching:
            await asyncio.sleep(0.5)
            
            try:
                current_mtime = self.config_path.stat().st_mtime
                if current_mtime > last_mtime:
                    self._load_config()
                    last_mtime = current_mtime
            except Exception:
                pass