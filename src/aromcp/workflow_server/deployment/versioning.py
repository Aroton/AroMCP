"""
Version management for rolling deployments.
"""

from typing import Dict, Any, Optional, List


class VersionManager:
    """Manages version compatibility and migrations."""
    
    def check_compatibility(self, old_version: Dict[str, Any], new_version: Dict[str, Any]) -> bool:
        """Check if versions are compatible for rolling deployment."""
        # Check API version compatibility
        old_api = old_version.get('api_version', 'v1')
        new_api = new_version.get('api_version', 'v2')
        
        # v2 is backward compatible with v1
        compatible_versions = {
            'v1': ['v1', 'v2'],
            'v2': ['v2']
        }
        
        if old_api in compatible_versions:
            return new_api in compatible_versions[old_api]
        
        return False
    
    def get_migration_plan(self, from_version: str, to_version: str) -> Optional[Dict[str, Any]]:
        """Get migration plan between versions."""
        migration_paths = {
            ('v1', 'v2'): {
                'steps': [
                    'Add validation field support',
                    'Update step processors',
                    'Migrate existing workflows'
                ],
                'estimated_duration': '10 minutes',
                'requires_downtime': False
            }
        }
        
        key = (from_version, to_version)
        if key in migration_paths:
            return migration_paths[key]
        
        return None