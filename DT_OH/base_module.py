"""
Base module abstract class for all pipeline processing modules.
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd


class BaseModule(ABC):
    """
    Abstract base class for all processing modules in the pipeline.
    
    Each module must implement:
    - process(): Main processing logic
    - get_output_columns(): List of columns produced by this module
    - validate_inputs(): Check if input data has required columns
    - get_required_columns(): List of columns required by this module
    """
    
    def __init__(
        self, 
        name: str, 
        config: Dict[str, Any], 
        output_dir: Path,
        logs_dir: Optional[Path] = None,
        checkpoints_dir: Optional[Path] = None
    ):
        """
        Initialize the module.
        
        Args:
            name: Module name for logging and output organization
            config: Module-specific configuration dictionary
            output_dir: Directory for this module's results
            logs_dir: Directory for logs (defaults to output_dir/logs if not provided)
            checkpoints_dir: Directory for checkpoints (defaults to output_dir/checkpoints if not provided)
        """
        self.name = name
        self.config = config
        self.output_dir = Path(output_dir)
        
        # Use provided directories or default to subdirectories of output_dir
        self.results_dir = self.output_dir
        self.logs_dir = Path(logs_dir) if logs_dir else self.output_dir / "logs"
        self.checkpoints_dir = Path(checkpoints_dir) if checkpoints_dir else self.output_dir / "checkpoints"
        
        self._ensure_directories()
        self._setup_logging()
    
    def _ensure_directories(self):
        """Create necessary output directories."""
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
    
    def _setup_logging(self):
        """Setup module-specific logging."""
        log_file = self.logs_dir / "processing.log"
        
        self.logger = logging.getLogger(f"pipeline.{self.name}")
        self.logger.setLevel(logging.DEBUG)
        
        # Avoid duplicate handlers
        if not self.logger.handlers:
            # File handler
            fh = logging.FileHandler(log_file)
            fh.setLevel(logging.DEBUG)
            
            # Console handler
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            
            # Formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            fh.setFormatter(formatter)
            ch.setFormatter(formatter)
            
            self.logger.addHandler(fh)
            self.logger.addHandler(ch)
    
    @abstractmethod
    def process(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Process the input data and return enhanced dataframe.
        
        Args:
            data: Input pandas DataFrame
            
        Returns:
            DataFrame with original columns plus new columns from processing
        """
        pass
    
    @abstractmethod
    def get_output_columns(self) -> List[str]:
        """
        Return list of column names produced by this module.
        
        Returns:
            List of output column names
        """
        pass
    
    @abstractmethod
    def get_required_columns(self) -> List[str]:
        """
        Return list of column names required by this module.
        
        Returns:
            List of required input column names
        """
        pass
    
    def validate_inputs(self, data: pd.DataFrame) -> bool:
        """
        Validate that input data has all required columns.
        
        Args:
            data: Input DataFrame to validate
            
        Returns:
            True if valid, raises ValueError otherwise
        """
        required = self.get_required_columns()
        missing = [col for col in required if col not in data.columns]
        
        if missing:
            raise ValueError(
                f"Module '{self.name}' missing required columns: {missing}"
            )
        
        self.logger.info(f"Input validation passed. Found all {len(required)} required columns.")
        return True
    
    # -----------------------
    # Checkpoint utilities
    # -----------------------
    def load_checkpoint(self) -> Dict[str, Any]:
        """Load checkpoint data if exists."""
        checkpoint_file = self.checkpoints_dir / "checkpoint.json"
        
        if checkpoint_file.exists():
            try:
                with open(checkpoint_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                self.logger.warning("Checkpoint file corrupted. Starting fresh.")
                return {"processed_indices": []}
        
        return {"processed_indices": []}
    
    def save_checkpoint(self, processed_indices: List[int]):
        """Save checkpoint with processed indices."""
        checkpoint_file = self.checkpoints_dir / "checkpoint.json"
        
        with open(checkpoint_file, 'w') as f:
            json.dump({"processed_indices": sorted(processed_indices)}, f)
    
    def clear_checkpoint(self):
        """Clear checkpoint file to start fresh."""
        checkpoint_file = self.checkpoints_dir / "checkpoint.json"
        if checkpoint_file.exists():
            checkpoint_file.unlink()
            self.logger.info("Checkpoint cleared.")
    
    # -----------------------
    # Logging utilities
    # -----------------------
    def log_missing_data(self, missing_df: pd.DataFrame):
        """Log rows with missing data to CSV."""
        missing_log = self.logs_dir / "missing_data.csv"
        header = not missing_log.exists()
        missing_df.to_csv(missing_log, mode='a', header=header, index=False)
        self.logger.info(f"Logged {len(missing_df)} rows with missing data.")
    
    def log_error(self, error_info: Dict[str, Any]):
        """Log processing errors."""
        error_log = self.logs_dir / "errors.csv"
        error_df = pd.DataFrame([error_info])
        header = not error_log.exists()
        error_df.to_csv(error_log, mode='a', header=header, index=False)
    
    # -----------------------
    # Results utilities
    # -----------------------
    def save_results(self, results_df: pd.DataFrame, filename: str = "results.csv"):
        """Save results to CSV."""
        output_path = self.results_dir / filename
        results_df.to_csv(output_path, index=False)
        self.logger.info(f"Saved {len(results_df)} rows to {output_path}")
        return output_path
    
    def append_results(self, results_df: pd.DataFrame, filename: str = "results.csv"):
        """Append results to existing CSV."""
        output_path = self.results_dir / filename
        header = not output_path.exists()
        results_df.to_csv(output_path, mode='a', header=header, index=False)
    
    def get_module_metadata(self) -> Dict[str, Any]:
        """Return metadata about this module's execution."""
        return {
            "module_name": self.name,
            "output_columns": self.get_output_columns(),
            "required_columns": self.get_required_columns(),
            "output_dir": str(self.output_dir),
            "config": self.config
        }

