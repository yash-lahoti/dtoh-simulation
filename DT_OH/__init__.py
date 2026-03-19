"""
Processing modules for the DT_OH retinal hemodynamics simulation.
"""

from .inference import RetinalModelModule, RetinalModelModuleWrapper

# Module registry - maps module names to their wrapper classes
MODULE_REGISTRY = {
    'RetinalModel': RetinalModelModuleWrapper,
    'retinal_model': RetinalModelModuleWrapper,  # Alternative name for compatibility
}

def get_module_class(name: str):
    """
    Get a module class by name.
    
    Args:
        name: Module name as specified in config
        
    Returns:
        Module wrapper class
        
    Raises:
        ValueError: If module name not found in registry
    """
    if name not in MODULE_REGISTRY:
        available = list(MODULE_REGISTRY.keys())
        raise ValueError(f"Unknown module '{name}'. Available: {available}")
    
    return MODULE_REGISTRY[name]


__all__ = ['RetinalModelModule', 'RetinalModelModuleWrapper', 'MODULE_REGISTRY', 'get_module_class']

